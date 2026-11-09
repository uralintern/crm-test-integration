"""Бэклог: дерево команды, карточки задачи и подзадачи, поиск по коду.

Чужая или несуществующая команда — 404, чтобы не раскрывать её существование (BL-32).
"""

from django.http import Http404
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import selectors, services
from .filters import parse_backlog_filters
from .inputs import SubtaskUpdateInput, TaskUpdateInput
from .models import BacklogSubtask, BacklogTask
from .serializers import stage_row, subtask_detail, task_detail
from .view_helpers import (
    CONFIRM_PARAMETER,
    TAG_BACKLOG,
    confirm_requested,
    load,
    require_edit_access,
    require_team_access,
    subtask_response,
    task_response,
    validated,
)

FILTER_PARAMETERS = [
    openapi.Parameter("executor", openapi.IN_QUERY, "ID исполнителя подзадачи", type=openapi.TYPE_INTEGER),
    openapi.Parameter("responsible", openapi.IN_QUERY, "ID ответственного задачи", type=openapi.TYPE_INTEGER),
    openapi.Parameter(
        "status",
        openapi.IN_QUERY,
        "Коды статусов через запятую: new, in_sprint, review, done",
        type=openapi.TYPE_STRING,
    ),
    openapi.Parameter("sprint", openapi.IN_QUERY, "ID спринта или none (вне спринта)", type=openapi.TYPE_STRING),
    openapi.Parameter("date_from", openapi.IN_QUERY, "Начало диапазона дат (ГГГГ-ММ-ДД)", type=openapi.TYPE_STRING),
    openapi.Parameter("date_to", openapi.IN_QUERY, "Конец диапазона дат (ГГГГ-ММ-ДД)", type=openapi.TYPE_STRING),
    openapi.Parameter("q", openapi.IN_QUERY, "Поиск по названию, описанию и коду", type=openapi.TYPE_STRING),
]


class BacklogTeamTreeView(APIView):
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(
        tags=[TAG_BACKLOG],
        operation_summary="Бэклог команды",
        operation_description=(
            "Иерархия: этапы, в них задачи, в задачах подзадачи. Работы (чек-лист) в дерево не входят. "
            "С фильтрами возвращаются подходящие объекты вместе с их родителями."
        ),
        manual_parameters=FILTER_PARAMETERS,
    )
    def get(self, request, team_id):
        access = require_team_access(request.user, team_id)
        filters = parse_backlog_filters(request.query_params)
        stages = selectors.build_team_backlog(access.team_id, filters)
        return Response(
            {
                "team_id": access.team_id,
                "team_name": str(access.team.get("name") or ""),
                # Подсказка для интерфейса; окончательно права всегда проверяет сервер.
                "access": {
                    "role": access.role.value,
                    "is_manager": access.is_manager,
                    "user_id": request.user.id,
                },
                "stages": [stage_row(stage) for stage in stages],
            }
        )


class BacklogTaskDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(tags=[TAG_BACKLOG], operation_summary="Карточка задачи")
    def get(self, request, task_id):
        node = selectors.get_task_node(task_id)
        if node is None:
            raise Http404
        require_team_access(request.user, node.task.team_id)
        return Response(task_detail(node))

    @swagger_auto_schema(
        tags=[TAG_BACKLOG],
        operation_summary="Изменить задачу",
        operation_description=(
            "Частичное изменение. Статус — только вперёд; «Завершена» — через /complete/. "
            "sprint_id переводит новую задачу в «В спринте». version — защита от перезаписи (409)."
        ),
        request_body=TaskUpdateInput,
    )
    def patch(self, request, task_id):
        task = load(BacklogTask, task_id)
        access = require_edit_access(request.user, task.team_id)
        services.update_task(access, task.id, validated(TaskUpdateInput, request.data))
        return task_response(task.id)

    @swagger_auto_schema(
        tags=[TAG_BACKLOG], operation_summary="Удалить задачу", manual_parameters=[CONFIRM_PARAMETER]
    )
    def delete(self, request, task_id):
        task = load(BacklogTask, task_id)
        access = require_edit_access(request.user, task.team_id)
        services.delete_object(access, request.user, task, confirm_requested(request))
        return Response(status=status.HTTP_204_NO_CONTENT)


class BacklogSubtaskDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(tags=[TAG_BACKLOG], operation_summary="Карточка подзадачи с чек-листом работ")
    def get(self, request, subtask_id):
        node = selectors.get_subtask_node(subtask_id)
        if node is None:
            raise Http404
        require_team_access(request.user, node.subtask.team_id)
        return Response(subtask_detail(node))

    @swagger_auto_schema(
        tags=[TAG_BACKLOG],
        operation_summary="Изменить подзадачу",
        operation_description="Правила те же, что у задачи.",
        request_body=SubtaskUpdateInput,
    )
    def patch(self, request, subtask_id):
        subtask = load(BacklogSubtask, subtask_id)
        access = require_edit_access(request.user, subtask.team_id)
        services.update_subtask(access, subtask.id, validated(SubtaskUpdateInput, request.data))
        return subtask_response(subtask.id)

    @swagger_auto_schema(
        tags=[TAG_BACKLOG], operation_summary="Удалить подзадачу", manual_parameters=[CONFIRM_PARAMETER]
    )
    def delete(self, request, subtask_id):
        subtask = load(BacklogSubtask, subtask_id)
        access = require_edit_access(request.user, subtask.team_id)
        services.delete_object(access, request.user, subtask, confirm_requested(request))
        return Response(status=status.HTTP_204_NO_CONTENT)


class BacklogByCodeView(APIView):
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(
        tags=[TAG_BACKLOG],
        operation_summary="Найти задачу или подзадачу по коду",
        operation_description="Для постоянной ссылки: код вида T-12 или S-34, регистр не важен.",
    )
    def get(self, request, code):
        kind, obj = selectors.find_by_code(code)
        if obj is None:
            raise Http404
        require_team_access(request.user, obj.team_id)
        if kind == "task":
            item = task_detail(selectors.get_task_node(obj.id))
        else:
            item = subtask_detail(selectors.get_subtask_node(obj.id))
        return Response({"type": kind, "team_id": obj.team_id, "item": item})
