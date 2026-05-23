import json
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth import password_validation
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.urls import reverse
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer, Serializer

from integrations.vk.crm_notifications import notify_application_testing_started

from users.automation_defaults import create_default_crm_automation_config
from users.vk_profiles import get_vk_bot_url, refresh_profile_vk_user_id, reset_profile_vk_confirmation_if_changed

from .models import CRMRole, ROLE_PROJECTANT, ROLE_CURATOR, ROLE_ADMIN
from .models import (
    Answer,
    Application,
    CRMAutomationConfig,
    CRMAutomationExecutionLog,
    Direction,
    Event,
    EventSpecialization,
    Notification,
    Profile,
    Project,
    Question,
    Specialization,
    Status,
    Test,
    TestResult,
    TestSession,
    TrueAnswer,
)


DEFAULT_APPLICATION_STATUS_NAME = "Прислал заявку"
DEFAULT_APPLICATION_STATUS_NAMES = (
    "Прислал заявку",
    "Прохождение тестирования",
    "Не перешёл к тестированию",
    "Не прошел тестирование",
    "Отправлена ссылка на орг. чат",
    "Не добавился в орг чат",
    "Добавился в орг. чат",
    "Приступил к ПШ",
    "Отказался от ПШ",
    "Удален с ПШ",
)
TESTING_APPLICATION_STATUS_NAME = "Прохождение тестирования"
CHAT_LINK_SENT_APPLICATION_STATUS_NAME = "Отправлена ссылка на орг. чат"
FAILED_TESTING_APPLICATION_STATUS_NAME = "Не прошел тестирование"


def build_user_display_name(user) -> str:
    if not user:
        return ""

    parts = [getattr(user, "last_name", ""), getattr(user, "first_name", "")]
    return " ".join(part for part in parts if part).strip()


def resolve_application_status() -> Status | None:
    for status_name in DEFAULT_APPLICATION_STATUS_NAMES:
        Status.objects.get_or_create(
            name=status_name,
            defaults={"description": "", "is_positive": True},
        )

    status_obj = Status.objects.filter(name=DEFAULT_APPLICATION_STATUS_NAME).first()
    if status_obj:
        return status_obj

    status_obj, _ = Status.objects.get_or_create(
        name=DEFAULT_APPLICATION_STATUS_NAME,
        defaults={"description": "", "is_positive": True},
    )
    return status_obj


def resolve_status_by_name(
    status_name: str,
    *,
    description: str = "",
    is_positive: bool = True,
) -> Status:
    status_obj = Status.objects.filter(name=status_name).order_by("id").first()
    if status_obj:
        return status_obj

    status_obj = Status.objects.create(
        name=status_name,
        description=description,
        is_positive=is_positive,
    )
    return status_obj


def resolve_testing_status() -> Status:
    return resolve_status_by_name(TESTING_APPLICATION_STATUS_NAME)


class FlexibleSpecializationField(serializers.PrimaryKeyRelatedField):
    def to_internal_value(self, data):
        if data in (None, ""):
            return None

        if isinstance(data, str):
            normalized = data.strip()
            if not normalized:
                return None

            if not normalized.isdigit():
                specialization = self.get_queryset().filter(name__iexact=normalized).first()
                if specialization:
                    return specialization
                raise serializers.ValidationError("Unknown specialization.")

        return super().to_internal_value(data)


class FlexibleStatusField(serializers.PrimaryKeyRelatedField):
    def to_internal_value(self, data):
        if data in (None, ""):
            return None

        if isinstance(data, str):
            normalized = data.strip()
            if not normalized:
                return None

            if not normalized.isdigit():
                status_obj = self.get_queryset().filter(name__iexact=normalized).first()
                if status_obj:
                    return status_obj
                raise serializers.ValidationError("Unknown status.")

        return super().to_internal_value(data)


class UserSerializer(ModelSerializer):
    role = serializers.SerializerMethodField()
    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()
    vk = serializers.SerializerMethodField()
    vkConfirmed = serializers.SerializerMethodField()
    vkBotUrl = serializers.SerializerMethodField()
    isSuperuser = serializers.BooleanField(source="is_superuser", read_only=True)
    isStaff = serializers.BooleanField(source="is_staff", read_only=True)

    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "role",
            "vk",
            "vkConfirmed",
            "vkBotUrl",
            "isSuperuser",
            "isStaff",
        )

    def get_first_name(self, obj):
        profile = getattr(obj, "crm_profile", None)
        return getattr(obj, "first_name", "") or getattr(profile, "name", "")

    def get_last_name(self, obj):
        profile = getattr(obj, "crm_profile", None)
        return getattr(obj, "last_name", "") or getattr(profile, "surname", "")

    def get_role(self, obj):
        if getattr(obj, "is_superuser", False) or getattr(obj, "is_staff", False):
            return "organizer"

        roles = set(CRMRole.objects.filter(user=obj).values_list("role_type", flat=True))
        if roles.intersection({ROLE_CURATOR, ROLE_ADMIN}):
            return "organizer"
        if Event.objects.filter(Q(leader=obj) | Q(organizers=obj)).exists():
            return "organizer"
        if ROLE_PROJECTANT in roles:
            return "student"
        return "student"

    def get_vk(self, obj):
        profile = getattr(obj, "crm_profile", None)
        return getattr(profile, "vk", "")

    def get_vkConfirmed(self, obj):
        profile = getattr(obj, "crm_profile", None)
        return bool(getattr(profile, "vk_confirmed_at", None))

    def get_vkBotUrl(self, obj):
        return get_vk_bot_url()


class RegisterUserSerializer(ModelSerializer):
    email = serializers.EmailField(required=True)
    vk = serializers.CharField(required=True, allow_blank=False, write_only=True)
    password = serializers.CharField(write_only=True)
    password_confirmation = serializers.CharField(write_only=True)
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)

    class Meta:
        model = get_user_model()
        fields = (
            "email",
            "vk",
            "first_name",
            "last_name",
            "password",
            "password_confirmation",
        )
        extra_kwargs = {
            "password": {"write_only": True},
            "username": {"required": False},
        }

    def validate_email(self, value):
        normalized_email = value.strip().lower()
        user_model = get_user_model()

        if user_model.objects.filter(email__iexact=normalized_email).exists():
            raise serializers.ValidationError("Пользователь с таким email уже существует.")

        if user_model.objects.filter(username__iexact=normalized_email).exists():
            raise serializers.ValidationError("Пользователь с таким email уже существует.")

        return normalized_email

    def validate_vk(self, value):
        normalized_vk = value.strip()
        if not normalized_vk:
            raise serializers.ValidationError("Укажите аккаунт VK.")
        return normalized_vk

    def validate(self, attrs):
        if attrs.get("password") != attrs.get("password_confirmation"):
            raise serializers.ValidationError({"password_confirmation": "Passwords do not match."})
        if not attrs.get("username"):
            attrs["username"] = attrs["email"]

        user_candidate = get_user_model()(
            email=attrs.get("email", ""),
            username=attrs.get("username", ""),
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
        )
        password_validation.validate_password(attrs.get("password"), user=user_candidate)
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirmation", None)
        vk_value = validated_data.pop("vk", "")
        try:
            with transaction.atomic():
                user = get_user_model().objects.create_user(**validated_data, is_active=True)
                profile = user.crm_profile
                profile.vk = vk_value
                profile.vk_user_id = refresh_profile_vk_user_id(profile, force=True)
                profile.save(update_fields=["vk", "vk_user_id"])
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"email": "Пользователь с таким email уже существует."}
            ) from exc
        return user


class LoginUserSerializer(Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = str(data.get("email") or "").strip().lower()
        user = authenticate(username=email, password=data.get("password"))
        if user and user.is_active:
            return user
        raise serializers.ValidationError("Invalid credentials.")


class PasswordResetRequestSerializer(Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        try:
            user = get_user_model().objects.get(email=value)
        except get_user_model().DoesNotExist:
            raise serializers.ValidationError("User with this email was not found.")

        if not user.is_active:
            raise serializers.ValidationError("Account is not active.")

        self.context["user"] = user
        return value

    def create(self, validated_data):
        user = self.context["user"]
        token = default_token_generator.make_token(user)

        request = self.context.get("request")
        reset_path = reverse("password-reset-confirm")
        reset_link = (
            request.build_absolute_uri(f"{reset_path}?email={user.email}&token={token}")
            if request
            else f"{reset_path}?email={user.email}&token={token}"
        )

        send_mail(
            subject="Password reset",
            message=f"Use this link to reset your password: {reset_link}",
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[user.email],
            fail_silently=True,
        )

        return {"email": user.email}


class PasswordResetConfirmSerializer(Serializer):
    email = serializers.EmailField(required=True)
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(write_only=True, required=True)
    new_password_confirmation = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        try:
            user = get_user_model().objects.get(email=attrs.get("email"))
        except get_user_model().DoesNotExist:
            raise serializers.ValidationError({"email": "User with this email was not found."})

        if not default_token_generator.check_token(user, attrs.get("token")):
            raise serializers.ValidationError({"token": "Token is invalid or expired."})

        if attrs.get("new_password") != attrs.get("new_password_confirmation"):
            raise serializers.ValidationError({"new_password_confirmation": "Passwords do not match."})

        password_validation.validate_password(attrs.get("new_password"), user)

        attrs["user"] = user
        return attrs

    def save(self, **kwargs):
        user = self.validated_data["user"]
        with transaction.atomic():
            user.set_password(self.validated_data["new_password"])
            user.save(update_fields=["password"])
        return user


class EmailConfirmationSerializer(Serializer):
    email = serializers.EmailField(required=True)
    token = serializers.CharField(required=True)

    def validate(self, attrs):
        try:
            user = get_user_model().objects.get(email=attrs.get("email"))
        except get_user_model().DoesNotExist:
            raise serializers.ValidationError({"email": "User with this email was not found."})

        if user.is_active:
            raise serializers.ValidationError({"email": "Account is already active."})

        if not default_token_generator.check_token(user, attrs.get("token")):
            raise serializers.ValidationError({"token": "Token is invalid or expired."})

        attrs["user"] = user
        return attrs

    def save(self, **kwargs):
        user = self.validated_data["user"]
        user.is_active = True
        user.save(update_fields=["is_active"])
        return user


class ProfileSerializer(ModelSerializer):
    vkConfirmed = serializers.SerializerMethodField()
    vkBotUrl = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = (
            "surname",
            "name",
            "patronymic",
            "telegram",
            "email",
            "course",
            "university",
            "vk",
            "vkConfirmed",
            "vkBotUrl",
            "job",
            "workplace",
            "specialty",
            "about",
        )
        read_only_fields = ("vkConfirmed", "vkBotUrl")

    def get_vkConfirmed(self, obj):
        return bool(obj.vk_confirmed_at)

    def get_vkBotUrl(self, obj):
        return get_vk_bot_url()

    def update(self, instance, validated_data):
        old_vk = instance.vk
        profile = super().update(instance, validated_data)
        user = profile.user
        user_update_fields = []
        if "name" in validated_data and user.first_name != profile.name:
            user.first_name = profile.name
            user_update_fields.append("first_name")
        if "surname" in validated_data and user.last_name != profile.surname:
            user.last_name = profile.surname
            user_update_fields.append("last_name")
        if "email" in validated_data and profile.email and user.email != profile.email:
            user.email = profile.email
            user.username = profile.email
            user_update_fields.extend(["email", "username"])
        if user_update_fields:
            user.save(update_fields=list(dict.fromkeys(user_update_fields)))
        reset_profile_vk_confirmation_if_changed(profile, old_vk)
        return profile


class EventSerializer(ModelSerializer):
    title = serializers.CharField(source="name", read_only=True)
    startDate = serializers.DateField(source="start_date", read_only=True)
    endDate = serializers.DateField(source="end_date", read_only=True)
    applyDeadline = serializers.DateTimeField(source="end_app_date", read_only=True)
    organizer = serializers.IntegerField(source="leader_id", read_only=True)
    organizerIds = serializers.PrimaryKeyRelatedField(
        queryset=get_user_model().objects.all(),
        source="organizers",
        many=True,
        required=False,
    )
    organizerName = serializers.SerializerMethodField()
    archived = serializers.BooleanField(source="is_archived", required=False)
    archivedAt = serializers.DateTimeField(source="archived_at", read_only=True)
    orgChatUrl = serializers.URLField(source="org_chat_url", required=False, allow_blank=True)
    orgChatPeerId = serializers.IntegerField(source="org_chat_peer_id", required=False, min_value=0)
    applicationFormFields = serializers.JSONField(source="application_form_fields", required=False)
    specializations = serializers.PrimaryKeyRelatedField(
        queryset=Specialization.objects.all(),
        many=True,
        required=False,
        write_only=True,
    )

    class Meta:
        model = Event
        fields = (
            "id",
            "title",
            "specialization",
            "specializations",
            "leader",
            "organizer",
            "organizerIds",
            "organizerName",
            "name",
            "description",
            "stage",
            "startDate",
            "start_date",
            "endDate",
            "end_date",
            "applyDeadline",
            "end_app_date",
            "is_archived",
            "archived",
            "archived_at",
            "archivedAt",
            "org_chat_url",
            "orgChatUrl",
            "org_chat_peer_id",
            "orgChatPeerId",
            "application_form_fields",
            "applicationFormFields",
        )
        read_only_fields = (
            "id",
            "title",
            "startDate",
            "endDate",
            "applyDeadline",
            "organizer",
            "organizerName",
            "archivedAt",
            "archived_at",
        )

    def get_organizerName(self, obj):
        organizers = list(obj.organizers.all())
        if organizers:
            return ", ".join(filter(None, (build_user_display_name(user) for user in organizers))) or None
        return build_user_display_name(obj.leader) or None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        specializations = list(
            Specialization.objects.filter(event_specializations__event=instance).distinct()
        )
        if not specializations and instance.specialization_id:
            specializations = [instance.specialization]
        data["specializations"] = SpecializationSerializer(specializations, many=True).data
        return data

    def _resolve_specializations(self, validated_data):
        multi_value = validated_data.pop("specializations", serializers.empty)
        single_value = validated_data.get("specialization", serializers.empty)

        if multi_value is not serializers.empty:
            return list(multi_value)
        if single_value is serializers.empty:
            return None
        if single_value is None:
            return []
        return [single_value]

    def _sync_specializations(self, event, chosen_specializations):
        EventSpecialization.objects.filter(event=event).delete()
        if not chosen_specializations:
            return

        EventSpecialization.objects.bulk_create(
            [
                EventSpecialization(event=event, specialization=specialization)
                for specialization in chosen_specializations
            ],
            ignore_conflicts=True,
        )

    def create(self, validated_data):
        chosen_specializations = self._resolve_specializations(validated_data)
        organizers = validated_data.pop("organizers", None)
        if chosen_specializations:
            validated_data["specialization"] = chosen_specializations[0]
        if organizers and not validated_data.get("leader"):
            validated_data["leader"] = organizers[0]

        event = super().create(validated_data)
        if organizers is not None:
            event.organizers.set(organizers)
        if chosen_specializations is not None:
            self._sync_specializations(event, chosen_specializations)
        return event

    def update(self, instance, validated_data):
        chosen_specializations = self._resolve_specializations(validated_data)
        organizers = validated_data.pop("organizers", None)
        if chosen_specializations is not None:
            validated_data["specialization"] = chosen_specializations[0] if chosen_specializations else None
        if organizers and not validated_data.get("leader"):
            validated_data["leader"] = organizers[0]

        event = super().update(instance, validated_data)
        if organizers is not None:
            event.organizers.set(organizers)
        if chosen_specializations is not None:
            self._sync_specializations(event, chosen_specializations)
        return event


class DirectionSerializer(ModelSerializer):
    event = serializers.PrimaryKeyRelatedField(read_only=True)
    title = serializers.CharField(source="name", read_only=True)
    eventId = serializers.IntegerField(source="event_id", read_only=True)
    organizer = serializers.IntegerField(source="leader_id", read_only=True)
    organizerName = serializers.SerializerMethodField()

    class Meta:
        model = Direction
        fields = (
            "id",
            "title",
            "name",
            "description",
            "event",
            "eventId",
            "leader",
            "organizer",
            "organizerName",
        )

    def get_organizerName(self, obj):
        return build_user_display_name(obj.leader) or None

    def create(self, validated_data):
        event = self.context.get("event")
        if not event:
            raise serializers.ValidationError({"event": "Event was not found."})

        validated_data["event"] = event
        return super().create(validated_data)


class ProjectSerializer(ModelSerializer):
    direction = serializers.PrimaryKeyRelatedField(read_only=True)
    title = serializers.CharField(source="name", read_only=True)
    directionId = serializers.IntegerField(source="direction_id", read_only=True)
    curatorId = serializers.IntegerField(source="curator_id", read_only=True)
    curatorName = serializers.SerializerMethodField()
    direction_id = serializers.PrimaryKeyRelatedField(
        queryset=Direction.objects.all(), write_only=True, source="direction", required=False
    )

    class Meta:
        model = Project
        fields = (
            "id",
            "title",
            "name",
            "description",
            "direction",
            "directionId",
            "direction_id",
            "curator",
            "curatorId",
            "curatorName",
            "teams",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "direction")

    def get_curatorName(self, obj):
        return build_user_display_name(obj.curator) or None

    def create(self, validated_data):
        direction = validated_data.get("direction") or self.context.get("direction")
        if not direction:
            raise serializers.ValidationError({"direction": "Direction was not found."})

        validated_data["direction"] = direction
        return super().create(validated_data)


class ApplicationCreateSerializer(ModelSerializer):
    event_id = serializers.PrimaryKeyRelatedField(
        queryset=Event.objects.filter(is_archived=False), write_only=True, source="event", required=False
    )
    direction_id = serializers.PrimaryKeyRelatedField(
        queryset=Direction.objects.all(), write_only=True, source="direction", required=False
    )
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(), required=False, allow_null=True
    )
    project_ref = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
        source="project",
    )
    specialization = FlexibleSpecializationField(
        queryset=Specialization.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Application
        fields = (
            "id",
            "message",
            "is_link",
            "comment",
            "date_sub",
            "date_end",
            "direction",
            "direction_id",
            "event",
            "event_id",
            "project",
            "project_ref",
            "specialization",
            "custom_fields",
        )
        read_only_fields = ("id", "date_sub", "date_end", "direction", "event")

    def create(self, validated_data):
        payload = dict(validated_data)
        event = payload.get("event") or self.context.get("event")
        direction = payload.get("direction") or self.context.get("direction")
        project = payload.get("project")
        user = self.context["request"].user

        if not event:
            raise serializers.ValidationError({"event": "Event is required."})

        if project and direction is None:
            direction = project.direction

        if direction and direction.event_id != event.id:
            raise serializers.ValidationError({"direction": "Direction does not belong to event."})

        if project and project.direction.event_id != event.id:
            raise serializers.ValidationError({"project": "Project does not belong to event."})

        if project and direction and project.direction_id != direction.id:
            raise serializers.ValidationError({"project": "Project does not belong to direction."})

        if timezone.now() > event.end_app_date:
            raise serializers.ValidationError({"event": "Application deadline has expired."})

        if Application.objects.filter(user=user, event=event).exists():
            raise serializers.ValidationError({"event": "Application for this event already exists."})

        payload.pop("event", None)
        payload.pop("direction", None)

        try:
            application = Application.objects.create(
                **payload,
                user=user,
                event=event,
                direction=direction,
                date_sub=timezone.now(),
                date_end=event.end_app_date,
                status=resolve_application_status(),
            )
            return application
        except IntegrityError:
            raise serializers.ValidationError({"event": "Application for this event already exists."})

    def validate(self, attrs):
        project_input = self.initial_data.get("project")
        project_ref_input = self.initial_data.get("project_ref")

        if (
            project_input
            and project_ref_input
            and str(project_input) != str(project_ref_input)
        ):
            raise serializers.ValidationError(
                {"project": "project and project_ref must match."}
            )

        return super().validate(attrs)


class ApplicationSerializer(ModelSerializer):
    ownerId = serializers.IntegerField(source="user_id", read_only=True)
    studentName = serializers.SerializerMethodField()
    userName = serializers.SerializerMethodField()
    userEmail = serializers.EmailField(source="user.email", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    eventId = serializers.IntegerField(source="event_id", read_only=True)
    eventTitle = serializers.CharField(source="event.name", read_only=True)
    eventName = serializers.CharField(source="event.name", read_only=True)
    event_name = serializers.CharField(source="event.name", read_only=True)
    directionId = serializers.IntegerField(source="direction_id", read_only=True)
    direction_name = serializers.CharField(source="direction.name", read_only=True)
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(), required=False, allow_null=True
    )
    project_ref = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
        source="project",
    )
    specialization = FlexibleSpecializationField(
        queryset=Specialization.objects.all(),
        required=False,
        allow_null=True,
    )
    status = FlexibleStatusField(
        queryset=Status.objects.all(),
        required=False,
        allow_null=True,
    )
    specializationId = serializers.IntegerField(source="specialization_id", read_only=True)
    statusId = serializers.IntegerField(source="status_id", read_only=True)
    projectId = serializers.IntegerField(source="project.id", read_only=True)
    projectTitle = serializers.CharField(source="project.name", read_only=True)
    createdAt = serializers.DateTimeField(source="date_sub", read_only=True)
    dateSub = serializers.DateTimeField(source="date_sub", read_only=True)

    class Meta:
        model = Application
        fields = (
            "id",
            "message",
            "is_link",
            "is_approved",
            "comment",
            "date_sub",
            "dateSub",
            "createdAt",
            "date_end",
            "user",
            "ownerId",
            "studentName",
            "userName",
            "userEmail",
            "user_email",
            "direction",
            "directionId",
            "direction_name",
            "event",
            "eventId",
            "eventTitle",
            "eventName",
            "event_name",
            "project",
            "project_ref",
            "projectId",
            "projectTitle",
            "specialization",
            "specializationId",
            "status",
            "statusId",
            "team_id",
            "tests_assigned",
            "tests_assigned_at",
            "test_session_id",
            "custom_fields",
        )
        read_only_fields = ("id", "user", "direction", "event", "date_sub")

    def get_studentName(self, obj):
        return build_user_display_name(obj.user) or obj.user.email

    def get_userName(self, obj):
        return self.get_studentName(obj)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["specialization"] = (
            SpecializationSerializer(instance.specialization).data
            if instance.specialization_id
            else None
        )
        data["status"] = instance.status.name if instance.status_id else None
        return data

    def validate(self, attrs):
        project_input = self.initial_data.get("project")
        project_ref_input = self.initial_data.get("project_ref")

        if (
            project_input
            and project_ref_input
            and str(project_input) != str(project_ref_input)
        ):
            raise serializers.ValidationError(
                {"project": "project and project_ref must match."}
            )

        return super().validate(attrs)

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)


class StatusSerializer(ModelSerializer):
    class Meta:
        model = Status
        fields = ("id", "name", "description", "is_positive")


class NotificationSerializer(ModelSerializer):
    userId = serializers.IntegerField(source="user_id", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = Notification
        fields = ("id", "userId", "title", "message", "link", "read", "createdAt")
        read_only_fields = ("id", "userId", "createdAt")


class NotificationCreateSerializer(ModelSerializer):
    userId = serializers.PrimaryKeyRelatedField(
        source="user",
        queryset=get_user_model().objects.all(),
        required=False,
        write_only=True,
    )

    class Meta:
        model = Notification
        fields = ("userId", "title", "message", "link")

    def validate(self, attrs):
        request = self.context.get("request")
        current_user = getattr(request, "user", None)
        target_user = attrs.get("user") or current_user

        if target_user != current_user:
            can_notify_others = (
                getattr(current_user, "is_superuser", False)
                or getattr(current_user, "is_staff", False)
                or CRMRole.objects.filter(user=current_user, role_type__in=(ROLE_CURATOR, ROLE_ADMIN)).exists()
            )
            if not can_notify_others:
                raise serializers.ValidationError({"userId": "Недостаточно прав для создания уведомления другому пользователю."})

        attrs["user"] = target_user
        return attrs

    def create(self, validated_data):
        return Notification.objects.create(
            **validated_data,
        )


class CRMAutomationConfigSerializer(ModelSerializer):
    eventId = serializers.IntegerField(source="event_id")
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = CRMAutomationConfig
        fields = (
            "id",
            "scope",
            "eventId",
            "updatedAt",
            "stages",
            "triggers",
            "robots",
        )
        read_only_fields = ("id", "updatedAt")

    def validate_scope(self, value):
        if value != CRMAutomationConfig.SCOPE_CRM:
            raise serializers.ValidationError("Для CRM поддерживается только scope=crm.")
        return value

    def validate(self, attrs):
        attrs["scope"] = CRMAutomationConfig.SCOPE_CRM
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        from users.automation_engine import normalize_crm_automation_config_dict

        return normalize_crm_automation_config_dict(data)


class CRMAutomationConfigPayloadSerializer(Serializer):
    scope = serializers.CharField(required=False, default=CRMAutomationConfig.SCOPE_CRM)
    eventId = serializers.IntegerField(required=False)
    stages = serializers.ListField(child=serializers.DictField(), required=False)
    triggers = serializers.ListField(child=serializers.DictField(), required=False)
    robots = serializers.ListField(child=serializers.DictField(), required=False)

    def validate_scope(self, value):
        if value != CRMAutomationConfig.SCOPE_CRM:
            raise serializers.ValidationError("Для CRM поддерживается только scope=crm.")
        return value

    def to_representation(self, instance):
        if isinstance(instance, CRMAutomationConfig):
            return CRMAutomationConfigSerializer(instance).data
        return super().to_representation(instance)


class CRMAutomationExecutionLogSerializer(ModelSerializer):
    eventId = serializers.IntegerField(source="event_id", read_only=True)
    applicationId = serializers.IntegerField(source="application_id", read_only=True)
    entityType = serializers.CharField(source="entity_type", read_only=True)
    entityId = serializers.CharField(source="entity_id", read_only=True)
    eventCode = serializers.CharField(source="event_code", read_only=True)
    ruleKind = serializers.CharField(source="rule_kind", read_only=True)
    ruleId = serializers.CharField(source="rule_id", read_only=True)
    runKey = serializers.CharField(source="run_key", read_only=True)
    scheduledFor = serializers.DateTimeField(source="scheduled_for", read_only=True)
    executedAt = serializers.DateTimeField(source="executed_at", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = CRMAutomationExecutionLog
        fields = (
            "id",
            "eventId",
            "applicationId",
            "entityType",
            "entityId",
            "eventCode",
            "ruleKind",
            "ruleId",
            "runKey",
            "status",
            "message",
            "context",
            "scheduledFor",
            "executedAt",
            "createdAt",
        )
        read_only_fields = fields


def serialize_default_crm_automation_config(event_id: int) -> dict:
    return create_default_crm_automation_config(event_id)


class SpecializationSerializer(ModelSerializer):
    title = serializers.CharField(source="name", read_only=True)

    class Meta:
        model = Specialization
        fields = ("id", "name", "title", "description")


class IntegrationAnswerExportSerializer(ModelSerializer):
    class Meta:
        model = Answer
        fields = ("id", "answer", "count")


class IntegrationTrueAnswerExportSerializer(ModelSerializer):
    class Meta:
        model = TrueAnswer
        fields = ("id", "true_answer", "points")


class IntegrationQuestionExportSerializer(ModelSerializer):
    answers = IntegrationAnswerExportSerializer(many=True, read_only=True)
    true_answers = IntegrationTrueAnswerExportSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = (
            "id",
            "name",
            "count",
            "points",
            "question_type",
            "answers",
            "true_answers",
        )


class IntegrationTestSummarySerializer(ModelSerializer):
    eventId = serializers.IntegerField(source="event_id", read_only=True)
    specializationId = serializers.IntegerField(source="specialization_id", read_only=True)
    passingScore = serializers.IntegerField(source="passing_score", read_only=True)
    timeLimit = serializers.IntegerField(source="time_limit", read_only=True)
    questionCount = serializers.IntegerField(source="question_count", read_only=True)
    testType = serializers.CharField(source="test_type", read_only=True)

    class Meta:
        model = Test
        fields = (
            "id",
            "name",
            "description",
            "entry",
            "eventId",
            "specializationId",
            "passingScore",
            "timeLimit",
            "questionCount",
            "testType",
            "is_active",
        )


class IntegrationTestExportSerializer(IntegrationTestSummarySerializer):
    questions = IntegrationQuestionExportSerializer(many=True, read_only=True)

    class Meta(IntegrationTestSummarySerializer.Meta):
        fields = IntegrationTestSummarySerializer.Meta.fields + ("questions",)


class IntegrationTestSessionSerializer(ModelSerializer):
    applicationId = serializers.IntegerField(source="application_id", read_only=True)
    testId = serializers.IntegerField(source="test_id", read_only=True)
    userId = serializers.IntegerField(source="user_id", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    expiresAt = serializers.DateTimeField(source="expires_at", read_only=True)

    class Meta:
        model = TestSession
        fields = (
            "id",
            "session_id",
            "applicationId",
            "testId",
            "userId",
            "createdAt",
            "expiresAt",
            "status",
        )


class IntegrationTestResultSerializer(ModelSerializer):
    applicationId = serializers.IntegerField(source="application_id", read_only=True)
    sessionId = serializers.CharField(source="session.session_id", read_only=True)
    testId = serializers.IntegerField(source="test_id", read_only=True)
    userId = serializers.IntegerField(source="user_id", read_only=True)
    startedAt = serializers.DateTimeField(source="started_at", read_only=True)
    completedAt = serializers.DateTimeField(source="completed_at", read_only=True)
    correctAnswers = serializers.IntegerField(source="correct_answers", read_only=True)
    totalQuestions = serializers.IntegerField(source="total_questions", read_only=True)
    timeSpentSeconds = serializers.IntegerField(source="time_spent_seconds", read_only=True)
    resultStatus = serializers.CharField(source="result_status", read_only=True)
    detailedResults = serializers.SerializerMethodField()

    class Meta:
        model = TestResult
        fields = (
            "id",
            "applicationId",
            "sessionId",
            "testId",
            "userId",
            "score",
            "max_score",
            "is_passed",
            "startedAt",
            "completedAt",
            "correctAnswers",
            "totalQuestions",
            "percentage",
            "timeSpentSeconds",
            "resultStatus",
            "detailedResults",
        )

    def get_detailedResults(self, obj):
        if not obj.detailed_results:
            return None
        try:
            return json.loads(obj.detailed_results)
        except (TypeError, ValueError):
            return obj.detailed_results


class IntegrationApplicationTestingContextSerializer(Serializer):
    application = serializers.SerializerMethodField()
    applicant = serializers.SerializerMethodField()
    event = serializers.SerializerMethodField()
    direction = serializers.SerializerMethodField()
    specialization = serializers.SerializerMethodField()
    availableTests = serializers.SerializerMethodField()
    currentSession = serializers.SerializerMethodField()
    latestResult = serializers.SerializerMethodField()

    def get_application(self, obj):
        return ApplicationSerializer(obj, context=self.context).data

    def get_applicant(self, obj):
        display_name = build_user_display_name(obj.user) or obj.user.email
        return {
            "id": obj.user_id,
            "email": obj.user.email,
            "first_name": obj.user.first_name,
            "last_name": obj.user.last_name,
            "display_name": display_name,
        }

    def get_event(self, obj):
        if not obj.event_id:
            return None
        return {
            "id": obj.event_id,
            "name": obj.event.name,
            "start_date": obj.event.start_date,
            "end_date": obj.event.end_date,
            "end_app_date": obj.event.end_app_date,
        }

    def get_direction(self, obj):
        if not obj.direction_id:
            return None
        return {
            "id": obj.direction_id,
            "name": obj.direction.name,
            "leader_id": obj.direction.leader_id,
        }

    def get_specialization(self, obj):
        if not obj.specialization_id:
            return None
        return SpecializationSerializer(obj.specialization).data

    def get_availableTests(self, obj):
        tests = self.context.get("available_tests", [])
        return IntegrationTestSummarySerializer(tests, many=True).data

    def get_currentSession(self, obj):
        session = self.context.get("current_session")
        if not session:
            return None
        return IntegrationTestSessionSerializer(session).data

    def get_latestResult(self, obj):
        result = self.context.get("latest_result")
        if not result:
            return None
        return IntegrationTestResultSerializer(result).data


class IntegrationTestSessionUpsertSerializer(Serializer):
    test_id = serializers.PrimaryKeyRelatedField(queryset=Test.objects.filter(is_active=True), source="test")
    session_id = serializers.CharField(max_length=255)
    expires_at = serializers.DateTimeField()
    status = serializers.CharField(required=False, default="assigned", max_length=50)
    answers_data = serializers.JSONField(required=False)

    def validate(self, attrs):
        application: Application = self.context["application"]
        test: Test = attrs["test"]
        session_id = attrs["session_id"]

        existing_session = TestSession.objects.filter(session_id=session_id).exclude(
            application=application
        )
        if existing_session.exists():
            raise serializers.ValidationError(
                {"session_id": "Session with this id is already linked to another application."}
            )

        if test.event_id and application.event_id and test.event_id != application.event_id:
            raise serializers.ValidationError(
                {"test_id": "Test does not belong to the application event."}
            )

        if (
            test.specialization_id
            and application.specialization_id
            and test.specialization_id != application.specialization_id
        ):
            raise serializers.ValidationError(
                {"test_id": "Test does not match the application specialization."}
            )

        return attrs

    def create(self, validated_data):
        application: Application = self.context["application"]
        previous_status_id = application.status_id
        testing_status = resolve_testing_status()
        answers_data = validated_data.pop("answers_data", None)
        session_id = validated_data["session_id"]

        defaults = {
            "application": application,
            "test": validated_data["test"],
            "user": application.user,
            "expires_at": validated_data["expires_at"],
            "status": validated_data["status"],
        }
        if answers_data is not None:
            defaults["answers_data"] = json.dumps(answers_data, ensure_ascii=False)

        session, created = TestSession.objects.update_or_create(
            session_id=session_id,
            defaults=defaults,
        )

        application.tests_assigned = True
        if not application.tests_assigned_at:
            application.tests_assigned_at = timezone.now()
        application.test_session_id = session.session_id
        application.status = testing_status
        application.save(
            update_fields=[
                "tests_assigned",
                "tests_assigned_at",
                "test_session_id",
                "status",
            ]
        )
        notify_application_testing_started(application, previous_status_id=previous_status_id)

        self.context["created"] = created
        return session


class IntegrationTestResultCallbackSerializer(Serializer):
    session_id = serializers.CharField(max_length=255)
    test_id = serializers.PrimaryKeyRelatedField(
        queryset=Test.objects.all(),
        source="test",
        required=False,
        allow_null=True,
    )
    score = serializers.IntegerField()
    max_score = serializers.IntegerField()
    is_passed = serializers.BooleanField(required=False)
    completed_at = serializers.DateTimeField()
    started_at = serializers.DateTimeField()
    correct_answers = serializers.IntegerField(required=False, min_value=0)
    total_questions = serializers.IntegerField(required=False, min_value=0)
    percentage = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    time_spent_seconds = serializers.IntegerField(required=False, min_value=0, default=0)
    result_status = serializers.CharField(required=False, allow_blank=True, max_length=100)
    detailed_results = serializers.JSONField(required=False)
    answers_data = serializers.JSONField(required=False)
    session_status = serializers.CharField(required=False, default="completed", max_length=50)
    application_status = serializers.CharField(required=False, allow_blank=False)

    def validate(self, attrs):
        application: Application = self.context["application"]
        session_id = attrs["session_id"]

        try:
            session = TestSession.objects.select_related("test", "application", "user").get(
                session_id=session_id
            )
        except TestSession.DoesNotExist as exc:
            raise serializers.ValidationError(
                {"session_id": "Test session with this id was not found."}
            ) from exc

        if session.application_id != application.id:
            raise serializers.ValidationError(
                {"session_id": "Test session does not belong to this application."}
            )

        test = attrs.get("test") or session.test
        if test.id != session.test_id:
            raise serializers.ValidationError(
                {"test_id": "Test does not match the stored session test."}
            )

        if attrs["completed_at"] < attrs["started_at"]:
            raise serializers.ValidationError(
                {"completed_at": "completed_at must be greater than or equal to started_at."}
            )

        if "correct_answers" not in attrs:
            attrs["correct_answers"] = 0

        if "total_questions" not in attrs:
            attrs["total_questions"] = session.test.question_count

        if "percentage" not in attrs:
            max_score = attrs["max_score"] or 0
            attrs["percentage"] = (
                Decimal("0")
                if max_score == 0
                else Decimal(str(round((attrs["score"] / max_score) * 100, 2)))
            )

        if "is_passed" not in attrs:
            attrs["is_passed"] = attrs["score"] >= session.test.passing_score

        if not attrs.get("result_status"):
            attrs["result_status"] = "passed" if attrs["is_passed"] else "failed"

        attrs["session"] = session
        attrs["test"] = test
        return attrs

    def create(self, validated_data):
        application: Application = self.context["application"]
        previous_status = application.status.name if application.status_id else ""
        session: TestSession = validated_data.pop("session")
        test: Test = validated_data.pop("test")
        validated_data.pop("session_id", None)
        detailed_results = validated_data.pop("detailed_results", None)
        answers_data = validated_data.pop("answers_data", None)
        session_status = validated_data.pop("session_status", "completed")
        application_status_value = validated_data.pop("application_status", None)

        if detailed_results is not None:
            validated_data["detailed_results"] = json.dumps(
                detailed_results, ensure_ascii=False
            )

        result, created = TestResult.objects.update_or_create(
            session=session,
            defaults={
                **validated_data,
                "application": application,
                "test": test,
                "user": application.user,
            },
        )

        session.status = session_status
        if answers_data is not None:
            session.answers_data = json.dumps(answers_data, ensure_ascii=False)
        session.save(update_fields=["status", "answers_data"])

        application.tests_assigned = True
        if not application.tests_assigned_at:
            application.tests_assigned_at = timezone.now()
        if application.test_session_id != session.session_id:
            application.test_session_id = session.session_id

        if not application_status_value and validated_data.get("is_passed"):
            application_status_value = CHAT_LINK_SENT_APPLICATION_STATUS_NAME
        if (
            not application_status_value
            and str(validated_data.get("result_status", "")).lower()
            in {"failed_all", "failed_final"}
        ):
            application_status_value = FAILED_TESTING_APPLICATION_STATUS_NAME

        update_fields = ["tests_assigned", "tests_assigned_at", "test_session_id"]
        status_changed = False
        if application_status_value:
            status_obj = None
            if str(application_status_value).isdigit():
                status_obj = Status.objects.filter(pk=int(application_status_value)).first()
            else:
                status_obj = Status.objects.filter(
                    name__iexact=str(application_status_value).strip()
                ).first()

            if not status_obj:
                raise serializers.ValidationError(
                    {"application_status": "Application status was not found."}
                )

            application.status = status_obj
            status_changed = previous_status != status_obj.name
            update_fields.append("status")

        application.save(update_fields=update_fields)

        if status_changed:
            from users.automation_engine import run_crm_automation

            application.refresh_from_db()
            run_crm_automation(
                application,
                "request.status_changed",
                previous_status=previous_status,
                request=self.context.get("request"),
            )

        self.context["created"] = created
        return result
