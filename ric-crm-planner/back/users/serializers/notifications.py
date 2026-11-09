"""Уведомления."""

from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer
from ..models import CRMRole, ROLE_CURATOR, ROLE_ADMIN
from ..models import Notification


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
