"""Общие помощники сериализаторов: статусы заявок, отображаемое имя, гибкие поля."""

from rest_framework import serializers
from ..models import Status


DEFAULT_APPLICATION_STATUS_NAME = "Прислал заявку"
DEFAULT_APPLICATION_STATUS_NAMES = (
    "Прислал заявку",
    "Прохождение тестирования",
    "Не перешёл к тестированию",
    "Не прошел тестирование",
    "Отправлена ссылка на орг. чат",
    "Не добавился в орг чат",
    "Добавился в орг. чат",
    "Набор завершён",
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

    profile = getattr(user, "crm_profile", None)
    last_name = getattr(user, "last_name", "") or getattr(profile, "surname", "")
    first_name = getattr(user, "first_name", "") or getattr(profile, "name", "")
    display_name = " ".join(part for part in (last_name, first_name) if part).strip()
    return display_name or getattr(user, "email", "") or getattr(user, "username", "") or ""


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
