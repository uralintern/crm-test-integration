from rest_framework import serializers

from planner.automation_defaults import create_default_planner_automation_config
from planner.models import PlannerAutomationConfig, PlannerAutomationExecutionLog, PlannerWorkspaceState, TeamPlannerDesk


class PlannerWorkspaceStateSerializer(serializers.ModelSerializer):
    prune_missing_team_desks = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = PlannerWorkspaceState
        fields = (
            "enrollment_closed",
            "participants",
            "teams",
            "parent_tasks",
            "subtasks",
            "columns",
            "prune_missing_team_desks",
        )

    def create(self, validated_data):
        validated_data.pop("prune_missing_team_desks", None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("prune_missing_team_desks", None)
        return super().update(instance, validated_data)


class TeamPlannerDeskSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamPlannerDesk
        fields = (
            "team_id",
            "team_name",
            "curator_id",
            "member_ids",
            "parent_tasks",
            "subtasks",
            "columns",
            "updated_at",
        )
        read_only_fields = ("team_id", "updated_at")


class PlannerAutomationConfigSerializer(serializers.ModelSerializer):
    eventId = serializers.IntegerField(source="event_id")
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = PlannerAutomationConfig
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
        if value != PlannerAutomationConfig.SCOPE_PLANNER:
            raise serializers.ValidationError("Для планировщика поддерживается только scope=planner.")
        return value

    def validate(self, attrs):
        attrs["scope"] = PlannerAutomationConfig.SCOPE_PLANNER
        return attrs


class PlannerAutomationConfigPayloadSerializer(serializers.Serializer):
    scope = serializers.CharField(required=False, default=PlannerAutomationConfig.SCOPE_PLANNER)
    eventId = serializers.IntegerField(required=False)
    stages = serializers.ListField(child=serializers.DictField(), required=False)
    triggers = serializers.ListField(child=serializers.DictField(), required=False)
    robots = serializers.ListField(child=serializers.DictField(), required=False)

    def validate_scope(self, value):
        if value != PlannerAutomationConfig.SCOPE_PLANNER:
            raise serializers.ValidationError("Для планировщика поддерживается только scope=planner.")
        return value

    def to_representation(self, instance):
        if isinstance(instance, PlannerAutomationConfig):
            return PlannerAutomationConfigSerializer(instance).data
        return super().to_representation(instance)


class PlannerAutomationExecutionLogSerializer(serializers.ModelSerializer):
    eventId = serializers.IntegerField(source="event_id", read_only=True)
    teamId = serializers.IntegerField(source="team_id", read_only=True)
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
        model = PlannerAutomationExecutionLog
        fields = (
            "id",
            "eventId",
            "teamId",
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


def serialize_default_planner_automation_config(event_id: int) -> dict:
    return create_default_planner_automation_config(event_id)
