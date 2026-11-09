"""Бэклог, задача 2: создание и изменение этапов, задач, подзадач, работ; порядок; удаление."""

from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import selectors, services
from .inputs import (
    ReorderInput,
    StageCreateInput,
    StageUpdateInput,
    SubtaskBulkInput,
    SubtaskCreateInput,
    TaskCreateInput,
    WorkCreateInput,
    WorkUpdateInput,
)
from .models import BacklogStage, BacklogSubtask, BacklogTask, BacklogWorkItem
from .serializers import stage_row, subtask_row, work_item_row
from .view_helpers import (
    CONFIRM_PARAMETER,
    TAG_BACKLOG,
    confirm_requested,
    load,
    require_edit_access,
    stage_response,
    subtask_response,
    task_response,
    task_rows,
    validated,
)


class BacklogStageCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(tags=[TAG_BACKLOG], operation_summary="Создать этап", request_body=StageCreateInput)
    def post(self, request, team_id):
        access = require_edit_access(request.user, team_id)
        stage = services.create_stage(access, request.user, validated(StageCreateInput, request.data))
        return stage_response(stage, status=status.HTTP_201_CREATED)


class BacklogStageDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(tags=[TAG_BACKLOG], operation_summary="Изменить этап", request_body=StageUpdateInput)
    def patch(self, request, stage_id):
        stage = load(BacklogStage, stage_id)
        require_edit_access(request.user, stage.team_id)
        stage = services.update_stage(stage.id, validated(StageUpdateInput, request.data))
        return stage_response(stage)

    @swagger_auto_schema(
        tags=[TAG_BACKLOG], operation_summary="Удалить этап", manual_parameters=[CONFIRM_PARAMETER]
    )
    def delete(self, request, stage_id):
        stage = load(BacklogStage, stage_id)
        access = require_edit_access(request.user, stage.team_id)
        services.delete_object(access, request.user, stage, confirm_requested(request))
        return Response(status=status.HTTP_204_NO_CONTENT)


class BacklogStageReorderView(APIView):
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(
        tags=[TAG_BACKLOG],
        operation_summary="Порядок этапов команды",
        operation_description="ids — все этапы команды в новом порядке.",
        request_body=ReorderInput,
    )
    def post(self, request, team_id):
        access = require_edit_access(request.user, team_id)
        services.reorder_stages(access, validated(ReorderInput, request.data)["ids"])
        stages = selectors.build_team_backlog(access.team_id, selectors.BacklogFilters())
        return Response([stage_row(stage) for stage in stages])


class BacklogTaskCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(
        tags=[TAG_BACKLOG], operation_summary="Создать задачу в этапе", request_body=TaskCreateInput
    )
    def post(self, request, stage_id):
        stage = load(BacklogStage, stage_id)
        access = require_edit_access(request.user, stage.team_id)
        task = services.create_task(access, request.user, stage, validated(TaskCreateInput, request.data))
        return task_response(task.id, status=status.HTTP_201_CREATED)


class BacklogTaskReorderView(APIView):
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(
        tags=[TAG_BACKLOG],
        operation_summary="Порядок задач этапа",
        operation_description="ids — все задачи этапа в новом порядке.",
        request_body=ReorderInput,
    )
    def post(self, request, stage_id):
        stage = load(BacklogStage, stage_id)
        require_edit_access(request.user, stage.team_id)
        services.reorder_tasks(stage, validated(ReorderInput, request.data)["ids"])
        return Response(task_rows(selectors.task_queryset().filter(stage=stage)))


class BacklogSubtaskCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(
        tags=[TAG_BACKLOG], operation_summary="Создать подзадачу в задаче", request_body=SubtaskCreateInput
    )
    def post(self, request, task_id):
        task = load(BacklogTask, task_id)
        access = require_edit_access(request.user, task.team_id)
        subtask = services.create_subtask(access, request.user, task, validated(SubtaskCreateInput, request.data))
        return subtask_response(subtask.id, status=status.HTTP_201_CREATED)


class BacklogSubtaskBulkCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(
        tags=[TAG_BACKLOG],
        operation_summary="Создать подзадачи из списка пунктов",
        operation_description="Пустые пункты пропускаются; исполнитель и сроки общие для всех.",
        request_body=SubtaskBulkInput,
    )
    def post(self, request, task_id):
        task = load(BacklogTask, task_id)
        access = require_edit_access(request.user, task.team_id)
        created = services.bulk_create_subtasks(access, request.user, task, validated(SubtaskBulkInput, request.data))
        nodes = selectors.subtask_nodes([subtask.id for subtask in created])
        return Response([subtask_row(node) for node in nodes], status=status.HTTP_201_CREATED)


class BacklogWorkCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(
        tags=[TAG_BACKLOG], operation_summary="Добавить работу в чек-лист подзадачи", request_body=WorkCreateInput
    )
    def post(self, request, subtask_id):
        subtask = load(BacklogSubtask, subtask_id)
        require_edit_access(request.user, subtask.team_id)
        work = services.create_work_item(request.user, subtask, validated(WorkCreateInput, request.data))
        return Response(work_item_row(work), status=status.HTTP_201_CREATED)


class BacklogWorkDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(
        tags=[TAG_BACKLOG], operation_summary="Изменить или отметить работу", request_body=WorkUpdateInput
    )
    def patch(self, request, work_id):
        work = load(BacklogWorkItem, work_id, "subtask")
        require_edit_access(request.user, work.subtask.team_id)
        work = services.update_work_item(work.id, validated(WorkUpdateInput, request.data))
        return Response(work_item_row(work))

    @swagger_auto_schema(tags=[TAG_BACKLOG], operation_summary="Удалить работу")
    def delete(self, request, work_id):
        work = load(BacklogWorkItem, work_id, "subtask")
        access = require_edit_access(request.user, work.subtask.team_id)
        services.delete_object(access, request.user, work, confirm=True)
        return Response(status=status.HTTP_204_NO_CONTENT)
