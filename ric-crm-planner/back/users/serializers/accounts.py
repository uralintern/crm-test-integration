"""Пользователи, регистрация, вход, сброс пароля, подтверждение email и профиль."""

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth import password_validation
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.urls import reverse
from django.db import IntegrityError, transaction
from django.db.models import Q
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer, Serializer
from users.vk_profiles import get_vk_bot_url, refresh_profile_vk_user_id, reset_profile_vk_confirmation_if_changed
from ..models import CRMRole, ROLE_PROJECTANT, ROLE_CURATOR, ROLE_ADMIN
from ..models import Event, Profile


class UserSerializer(ModelSerializer):
    role = serializers.SerializerMethodField()
    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()
    vk = serializers.SerializerMethodField()
    vkConfirmed = serializers.SerializerMethodField()
    vkBotUrl = serializers.SerializerMethodField()
    managedEventIds = serializers.SerializerMethodField()
    isGlobalOrganizer = serializers.SerializerMethodField()
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
            "managedEventIds",
            "isGlobalOrganizer",
            "isSuperuser",
            "isStaff",
        )

    def get_first_name(self, obj):
        profile = getattr(obj, "crm_profile", None)
        return getattr(obj, "first_name", "") or getattr(profile, "name", "")

    def get_last_name(self, obj):
        profile = getattr(obj, "crm_profile", None)
        return getattr(obj, "last_name", "") or getattr(profile, "surname", "")

    def get_isGlobalOrganizer(self, obj):
        if getattr(obj, "is_superuser", False) or getattr(obj, "is_staff", False):
            return True
        return CRMRole.objects.filter(user=obj, role_type__in=(ROLE_CURATOR, ROLE_ADMIN)).exists()

    def get_managedEventIds(self, obj):
        if not obj or not getattr(obj, "is_authenticated", True):
            return []
        return list(
            Event.objects.filter(Q(leader=obj) | Q(organizers=obj))
            .order_by("id")
            .values_list("id", flat=True)
            .distinct()
        )

    def get_role(self, obj):
        if self.get_isGlobalOrganizer(obj):
            return "organizer"

        roles = set(CRMRole.objects.filter(user=obj).values_list("role_type", flat=True))
        if self.get_managedEventIds(obj):
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
