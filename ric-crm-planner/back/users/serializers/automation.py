"""CRM-автоматизация: конфигурация, вложения, журнал выполнения."""

from rest_framework import serializers
from rest_framework.serializers import ModelSerializer, Serializer
from users.automation_defaults import create_default_crm_automation_config
from ..models import CRMAutomationConfig, CRMAutomationAttachment, CRMAutomationExecutionLog


class CRMAutomationAttachmentSerializer(ModelSerializer):
    name = serializers.CharField(source="file_name", read_only=True)
    contentType = serializers.CharField(source="content_type", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = CRMAutomationAttachment
        fields = ("id", "name", "size", "contentType", "createdAt")
        read_only_fields = fields


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
