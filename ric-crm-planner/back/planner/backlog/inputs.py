"""Схемы входных данных API записи бэклога.

Только форма и типы данных; бизнес-правила (участник команды, переходы статусов,
спринт своей команды) проверяются в services.py.
"""

from rest_framework import serializers

from .statuses import BacklogStatus

DATE_ORDER_ERROR = "Дата окончания не может быть раньше даты начала."

# Ограничения размеров: защищают базу от слишком больших запросов.
MAX_DESCRIPTION_LENGTH = 10_000
MAX_COMMENT_LENGTH = 5_000
MAX_BULK_SUBTASKS = 100
MAX_REORDER_IDS = 500


def check_date_order(attrs, start_field="start_date", end_field="end_date"):
    start, end = attrs.get(start_field), attrs.get(end_field)
    if start and end and end < start:
        raise serializers.ValidationError({end_field: DATE_ORDER_ERROR})
    return attrs


class TitleField(serializers.CharField):
    def __init__(self, **kwargs):
        super().__init__(max_length=255, trim_whitespace=True, allow_blank=False, **kwargs)


class VersionedInput(serializers.Serializer):
    # Версия объекта, которую видел клиент; при расхождении — 409.
    version = serializers.IntegerField(required=False, min_value=1)


class StageCreateInput(serializers.Serializer):
    title = TitleField()
    description = serializers.CharField(required=False, allow_blank=True, default="", max_length=MAX_DESCRIPTION_LENGTH)
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)

    def validate(self, attrs):
        return check_date_order(attrs)


class StageUpdateInput(VersionedInput):
    title = TitleField(required=False)
    description = serializers.CharField(required=False, allow_blank=True, max_length=MAX_DESCRIPTION_LENGTH)
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)


class TaskCreateInput(serializers.Serializer):
    title = TitleField()
    description = serializers.CharField(required=False, allow_blank=True, default="", max_length=MAX_DESCRIPTION_LENGTH)
    responsible_id = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()

    def validate(self, attrs):
        return check_date_order(attrs)


class _WorkflowUpdateFields(VersionedInput):
    title = TitleField(required=False)
    description = serializers.CharField(required=False, allow_blank=True, max_length=MAX_DESCRIPTION_LENGTH)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    status = serializers.ChoiceField(choices=BacklogStatus.choices, required=False)
    sprint_id = serializers.IntegerField(required=False, allow_null=True)


class TaskUpdateInput(_WorkflowUpdateFields):
    responsible_id = serializers.IntegerField(required=False)


class SubtaskCreateInput(serializers.Serializer):
    title = TitleField()
    description = serializers.CharField(required=False, allow_blank=True, default="", max_length=MAX_DESCRIPTION_LENGTH)
    executor_id = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()

    def validate(self, attrs):
        return check_date_order(attrs)


class SubtaskUpdateInput(_WorkflowUpdateFields):
    executor_id = serializers.IntegerField(required=False)


class SubtaskBulkInput(serializers.Serializer):
    titles = serializers.ListField(
        child=serializers.CharField(allow_blank=True, max_length=255), max_length=MAX_BULK_SUBTASKS
    )
    executor_id = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()

    def validate_titles(self, titles):
        cleaned = [title.strip() for title in titles if title.strip()]
        if not cleaned:
            raise serializers.ValidationError("Нужен хотя бы один непустой пункт.")
        return cleaned

    def validate(self, attrs):
        return check_date_order(attrs)


class WorkCreateInput(serializers.Serializer):
    title = TitleField()
    due_date = serializers.DateField(required=False, allow_null=True)


class WorkUpdateInput(serializers.Serializer):
    title = TitleField(required=False)
    is_done = serializers.BooleanField(required=False)
    due_date = serializers.DateField(required=False, allow_null=True)


class ReorderInput(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False, max_length=MAX_REORDER_IDS)


class TaskReworkInput(TaskCreateInput):
    comment = serializers.CharField(trim_whitespace=True, allow_blank=False, max_length=MAX_COMMENT_LENGTH)


class SubtaskReworkInput(SubtaskCreateInput):
    comment = serializers.CharField(trim_whitespace=True, allow_blank=False, max_length=MAX_COMMENT_LENGTH)


class CommentInput(serializers.Serializer):
    text = serializers.CharField(trim_whitespace=True, allow_blank=False, max_length=MAX_COMMENT_LENGTH)


class SprintCreateInput(serializers.Serializer):
    title = TitleField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()

    def validate(self, attrs):
        return check_date_order(attrs)


class SprintUpdateInput(serializers.Serializer):
    title = TitleField(required=False)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
