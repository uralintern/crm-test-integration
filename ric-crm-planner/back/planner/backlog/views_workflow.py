"""Бэклог, задача 3: завершение, доработка, комментарии, спринты, канбан."""

from django.http import Http404
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import selectors, services
from .inputs import CommentInput, SprintCreateInput, SprintUpdateInput, SubtaskReworkInput, TaskReworkInput
from .models import BacklogComment, BacklogSprint, BacklogSubtask, BacklogTask
from .serializers import comment_row, kanban_columns, sprint_ref, sprint_row
from .view_helpers import (
    TAG_BACKLOG,
    load,
    require_edit_access,
    require_team_access,
    subtask_response,
    task_response,
    validated,
)


class BacklogTaskCompleteView(APIView):
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(
        tags=[TAG_BACKLOG],
        operation_summary="Завершить задачу",
        operation_description="Куратор, организатор или администратор. Повторное завершение — 409.",
    )
    def post(self, request, task_id):
        task = load(BacklogTask, task_id)
        access = require_team_access(request.user, task.team_id)
        services.complete_task(access, task.id)
        return task_response(task.id)


class BacklogSubtaskCompleteView(APIView):
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(
        tags=[TAG_BACKLOG],
        operation_summary="Завершить подзадачу",
        operation_description="Ответственный задачи, куратор, организатор или администратор. Повторно — 409.",
    )
    def post(self, request, subtask_id):
        subtask = load(BacklogSubtask, subtask_id)
        access = require_team_access(request.user, subtask.team_id)
        services.complete_subtask(access, request.user, subtask.id)
        return subtask_response(subtask.id)


class BacklogTaskReworkView(APIView):
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(
        tags=[TAG_BACKLOG],
        operation_summary="Создать доработку задачи",
        operation_description=(
            "Только для задачи «На проверке». Создаётся новая задача в том же этапе со ссылкой на исходную "
            "и комментарием о причине; статус исходной не меняется."
        ),
        request_body=TaskReworkInput,
    )
    def post(self, request, task_id):
        task = load(BacklogTask, task_id)
        access = require_edit_access(request.user, task.team_id)
        rework = services.create_task_rework(access, request.user, task.id, validated(TaskReworkInput, request.data))
        return task_response(rework.id, status=status.HTTP_201_CREATED)


class BacklogSubtaskReworkView(APIView):
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(
        tags=[TAG_BACKLOG],
        operation_summary="Создать доработку подзадачи",
        operation_description="Как у задачи: новая подзадача в той же задаче со ссылкой на исходную.",
        request_body=SubtaskReworkInput,
    )
    def post(self, request, subtask_id):
        subtask = load(BacklogSubtask, subtask_id)
        access = require_edit_access(request.user, subtask.team_id)
        rework = services.create_subtask_rework(
            access, request.user, subtask.id, validated(SubtaskReworkInput, request.data)
        )
        return subtask_response(rework.id, status=status.HTTP_201_CREATED)


class _CommentsView(APIView):
    permission_classes = (IsAuthenticated,)
    model = None
    target = ""

    def _load(self, request, pk, for_write=False):
        obj = load(self.model, pk)
        (require_edit_access if for_write else require_team_access)(request.user, obj.team_id)
        return obj

    def get(self, request, pk):
        obj = self._load(request, pk)
        comments = BacklogComment.objects.filter(**{self.target: obj}).select_related("author__crm_profile")
        return Response([comment_row(comment) for comment in comments])

    def post(self, request, pk):
        obj = self._load(request, pk, for_write=True)
        text = validated(CommentInput, request.data)["text"]
        comment = services.add_comment(request.user, text, **{self.target: obj})
        return Response(comment_row(comment), status=status.HTTP_201_CREATED)


class BacklogTaskCommentsView(_CommentsView):
    model = BacklogTask
    target = "task"

    @swagger_auto_schema(tags=[TAG_BACKLOG], operation_summary="Комментарии задачи")
    def get(self, request, task_id):
        return super().get(request, task_id)

    @swagger_auto_schema(
        tags=[TAG_BACKLOG], operation_summary="Добавить комментарий к задаче", request_body=CommentInput
    )
    def post(self, request, task_id):
        return super().post(request, task_id)


class BacklogSubtaskCommentsView(_CommentsView):
    model = BacklogSubtask
    target = "subtask"

    @swagger_auto_schema(tags=[TAG_BACKLOG], operation_summary="Комментарии подзадачи")
    def get(self, request, subtask_id):
        return super().get(request, subtask_id)

    @swagger_auto_schema(
        tags=[TAG_BACKLOG], operation_summary="Добавить комментарий к подзадаче", request_body=CommentInput
    )
    def post(self, request, subtask_id):
        return super().post(request, subtask_id)


class BacklogSprintListView(APIView):
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(tags=[TAG_BACKLOG], operation_summary="Спринты команды")
    def get(self, request, team_id):
        access = require_team_access(request.user, team_id)
        today = timezone.localdate()
        sprints = selectors.team_sprints(access.team_id)
        return Response([sprint_row(sprint, selectors.is_current_sprint(sprint, today)) for sprint in sprints])

    @swagger_auto_schema(tags=[TAG_BACKLOG], operation_summary="Создать спринт", request_body=SprintCreateInput)
    def post(self, request, team_id):
        access = require_edit_access(request.user, team_id)
        sprint = services.create_sprint(access, request.user, validated(SprintCreateInput, request.data))
        return Response(
            sprint_row(sprint, selectors.is_current_sprint(sprint, timezone.localdate())),
            status=status.HTTP_201_CREATED,
        )


class BacklogSprintDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(tags=[TAG_BACKLOG], operation_summary="Изменить спринт", request_body=SprintUpdateInput)
    def patch(self, request, sprint_id):
        sprint = load(BacklogSprint, sprint_id)
        require_edit_access(request.user, sprint.team_id)
        sprint = services.update_sprint(sprint.id, validated(SprintUpdateInput, request.data))
        return Response(sprint_row(sprint, selectors.is_current_sprint(sprint, timezone.localdate())))

    @swagger_auto_schema(
        tags=[TAG_BACKLOG],
        operation_summary="Удалить спринт",
        operation_description="Нельзя, пока к спринту привязаны задачи, в том числе завершённые (409).",
    )
    def delete(self, request, sprint_id):
        sprint = load(BacklogSprint, sprint_id)
        access = require_edit_access(request.user, sprint.team_id)
        services.delete_sprint(access, request.user, sprint.id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class BacklogKanbanView(APIView):
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(
        tags=[TAG_BACKLOG],
        operation_summary="Канбан спринта",
        operation_description=(
            "Колонки «В спринте» и «На проверке»; завершённые задачи на доске не показываются. "
            "По умолчанию — текущий спринт (в него попадает сегодняшняя дата)."
        ),
        manual_parameters=[
            openapi.Parameter(
                "sprint", openapi.IN_QUERY, "ID спринта или current (по умолчанию)", type=openapi.TYPE_STRING
            )
        ],
    )
    def get(self, request, team_id):
        access = require_team_access(request.user, team_id)
        sprint = self._resolve_sprint(access.team_id, request.query_params.get("sprint", ""))
        return Response({"sprint": sprint_ref(sprint), "columns": kanban_columns(selectors.build_kanban(sprint))})

    @staticmethod
    def _resolve_sprint(team_id, raw):
        raw = str(raw or "").strip().lower()
        if raw in ("", "current"):
            return selectors.current_sprint(team_id)
        try:
            sprint_id = int(raw)
        except ValueError as error:
            raise ValidationError({"sprint": "Ожидается id спринта или «current»."}) from error
        sprint = BacklogSprint.objects.filter(pk=sprint_id, team_id=team_id).first()
        if sprint is None:
            raise Http404
        return sprint
