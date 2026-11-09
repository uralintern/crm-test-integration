"""Общие помощники представлений бэклога: доступ, загрузка объектов, ответы."""

from django.http import Http404
from django.utils import timezone
from drf_yasg import openapi
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from . import selectors
from .access import TeamAccess, get_team_access
from .serializers import stage_row, subtask_detail, task_detail, task_row

TAG_BACKLOG = "Бэклог"

CONFIRM_PARAMETER = openapi.Parameter(
    "confirm",
    openapi.IN_QUERY,
    "true — подтвердить удаление вместе с вложенными объектами",
    type=openapi.TYPE_BOOLEAN,
)


def require_team_access(user, team_id) -> TeamAccess:
    """Права в команде; чужая или несуществующая команда — 404 (BL-32)."""
    access = get_team_access(user, team_id)
    if access is None or not access.can_view:
        raise Http404
    return access


def require_edit_access(user, team_id) -> TeamAccess:
    access = require_team_access(user, team_id)
    if not access.can_edit:
        raise PermissionDenied
    return access


def load(model, pk, *related):
    obj = model.objects.select_related(*related).filter(pk=pk).first()
    if obj is None:
        raise Http404
    return obj


def validated(serializer_class, data) -> dict:
    serializer = serializer_class(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def confirm_requested(request) -> bool:
    return str(request.query_params.get("confirm", "")).lower() in {"1", "true", "yes"}


def task_response(task_id, status=200) -> Response:
    return Response(task_detail(selectors.get_task_node(task_id)), status=status)


def subtask_response(subtask_id, status=200) -> Response:
    return Response(subtask_detail(selectors.get_subtask_node(subtask_id)), status=status)


def stage_response(stage, status=200) -> Response:
    today = timezone.localdate()
    tasks = [selectors.build_task_node(task, today) for task in selectors.task_queryset().filter(stage=stage)]
    return Response(stage_row(selectors.StageNode(stage=stage, tasks=tasks)), status=status)


def task_rows(queryset) -> list[dict]:
    today = timezone.localdate()
    return [task_row(selectors.build_task_node(task, today)) for task in queryset]
