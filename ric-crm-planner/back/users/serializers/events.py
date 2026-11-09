"""Мероприятия, направления, проекты, статусы и специализации."""

from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer
from ..models import CRMRole, ROLE_CURATOR, ROLE_ADMIN
from ..models import Direction, Event, EventSpecialization, Project, Specialization, Status
from .common import build_user_display_name


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

    def _request_user(self):
        request = self.context.get("request")
        return getattr(request, "user", None)

    def _can_manage_owner_fields(self):
        user = self._request_user()
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
            return True
        return CRMRole.objects.filter(user=user, role_type__in=(ROLE_CURATOR, ROLE_ADMIN)).exists()

    def _reject_scoped_owner_changes(self, validated_data, organizers):
        user = self._request_user()
        if not user or not getattr(user, "is_authenticated", False):
            return
        if self._can_manage_owner_fields():
            return

        errors = {}
        if organizers is not None or "leader" in validated_data:
            errors["organizerIds"] = "Менять организаторов может только главный организатор."
        if "is_archived" in validated_data or "archived_at" in validated_data:
            errors["archived"] = "Архивировать мероприятие может только главный организатор."
        if errors:
            raise serializers.ValidationError(errors)

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
        self._reject_scoped_owner_changes(validated_data, organizers)
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
        self._reject_scoped_owner_changes(validated_data, organizers)
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


class StatusSerializer(ModelSerializer):
    class Meta:
        model = Status
        fields = ("id", "name", "description", "is_positive")


class SpecializationSerializer(ModelSerializer):
    title = serializers.CharField(source="name", read_only=True)

    class Meta:
        model = Specialization
        fields = ("id", "name", "title", "description")
