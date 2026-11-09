"""Заявки: создание и просмотр/редактирование."""

from django.db import IntegrityError
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer
from ..models import Application, Direction, Event, Project, Specialization, Status, Test
from .common import (
    build_user_display_name,
    FlexibleSpecializationField,
    FlexibleStatusField,
    resolve_application_status,
)
from .events import SpecializationSerializer


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
    university = serializers.SerializerMethodField()
    course = serializers.SerializerMethodField()
    vk = serializers.SerializerMethodField()
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
    hasAvailableTests = serializers.SerializerMethodField()

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
            "university",
            "course",
            "vk",
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
            "hasAvailableTests",
            "custom_fields",
        )
        read_only_fields = ("id", "user", "direction", "event", "date_sub")

    def get_studentName(self, obj):
        return build_user_display_name(obj.user) or obj.user.email

    def get_userName(self, obj):
        return self.get_studentName(obj)

    def _get_profile(self, obj):
        try:
            return obj.user.crm_profile
        except Exception:
            return None

    def get_university(self, obj):
        profile = self._get_profile(obj)
        return getattr(profile, "university", "") or ""

    def get_course(self, obj):
        profile = self._get_profile(obj)
        course = getattr(profile, "course", None)
        return course or ""

    def get_vk(self, obj):
        profile = self._get_profile(obj)
        return getattr(profile, "vk", "") or ""

    def get_hasAvailableTests(self, obj):
        queryset = Test.objects.filter(is_active=True)
        if obj.event_id:
            queryset = queryset.filter(Q(event__isnull=True) | Q(event_id=obj.event_id))
        if obj.specialization_id:
            queryset = queryset.filter(Q(specialization__isnull=True) | Q(specialization_id=obj.specialization_id))
        return queryset.exists()

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
