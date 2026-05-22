from rest_framework import serializers


class VKSendTestSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=False)
    peer_id = serializers.IntegerField(required=False)
    message = serializers.CharField(required=True, allow_blank=False, trim_whitespace=True)

    def validate(self, attrs):
        if not attrs.get("user_id") and not attrs.get("peer_id"):
            raise serializers.ValidationError("Укажите user_id или peer_id.")
        return attrs


class VKApplicationMessageSerializer(serializers.Serializer):
    subject = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    message = serializers.CharField(required=True, allow_blank=False, trim_whitespace=True)
    include_chat_link = serializers.BooleanField(required=False, default=False)
    chat_url = serializers.URLField(required=False, allow_blank=True)

    def validate(self, attrs):
        subject = attrs.get("subject", "").strip()
        message = attrs.get("message", "").strip()
        if not subject:
            attrs["text"] = message
            return attrs

        attrs["text"] = f"{subject}\n\n{message}"
        return attrs


class VKPlannerInviteSerializer(serializers.Serializer):
    RECIPIENT_CHOICES = (
        ("joined", "joined"),
        ("all", "all"),
        ("declined", "declined"),
    )

    recipient_mode = serializers.ChoiceField(choices=RECIPIENT_CHOICES, required=False, default="joined")
    message = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
