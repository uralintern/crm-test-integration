"""Операции записи бэклога и бизнес-правила.

Правила:
- родитель объекта задаётся контекстом создания и не меняется (BR-05, W-01);
- ответственный задачи и исполнитель подзадачи — один участник команды (BL-14, BL-15);
- статусы меняются только вперёд, «Завершена» — только действием «Завершить» (BL-28–BL-30, S-07);
- изменения защищены версией объекта: устаревшая версия — 409.
"""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Max
from rest_framework import status as http_status
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError

from .access import TeamAccess, can_complete_subtask, can_complete_task, can_delete, team_member_ids
from .inputs import DATE_ORDER_ERROR
from .models import (
    BacklogComment,
    BacklogSprint,
    BacklogStage,
    BacklogSubtask,
    BacklogTask,
    BacklogWorkItem,
)
from .statuses import BacklogStatus, transition_error


class Conflict(APIException):
    """409 с телом как есть: числа (версия, количества) остаются числами, а не строками."""

    status_code = http_status.HTTP_409_CONFLICT
    default_detail = "Конфликт состояния объекта."
    default_code = "conflict"

    def __init__(self, data: dict):
        super().__init__()
        self.detail = data


# --- общие проверки --------------------------------------------------------------


def _locked(queryset, pk):
    """Объект под блокировкой; если его успели удалить — 404, а не 500."""
    obj = queryset.filter(pk=pk).first()
    if obj is None:
        raise NotFound()
    return obj


def _check_version(obj, version):
    if version is not None and version != obj.version:
        raise Conflict(
            {
                "detail": "Объект уже изменил кто-то другой. Обновите данные и повторите.",
                "current_version": obj.version,
            }
        )


def _check_date_order(start, end):
    if start and end and end < start:
        raise ValidationError({"end_date": DATE_ORDER_ERROR})


def _team_member(access: TeamAccess, user_id: int, field: str):
    if user_id not in team_member_ids(access.team):
        raise ValidationError({field: "Можно назначить только участника команды."})
    user = get_user_model().objects.filter(pk=user_id).first()
    if user is None:
        raise ValidationError({field: "Пользователь не найден."})
    return user


def _next_position(queryset) -> int:
    current = queryset.aggregate(value=Max("position"))["value"]
    return 0 if current is None else current + 1


def _apply_simple_fields(obj, data, fields):
    for field in fields:
        if field in data:
            setattr(obj, field, data[field])


def _apply_sprint_and_status(obj, data):
    """Спринт и статус задачи/подзадачи по правилам BL-26, BL-28, BL-30."""
    if obj.status == BacklogStatus.DONE and "sprint_id" in data and data["sprint_id"] != obj.sprint_id:
        raise ValidationError({"sprint_id": "Завершённую задачу нельзя переносить в спринт."})

    if "sprint_id" in data:
        sprint_id = data["sprint_id"]
        if sprint_id is None:
            if obj.sprint_id is not None:
                raise ValidationError({"sprint_id": "Убрать задачу из спринта пока нельзя."})
        else:
            # Блокировка спринта не даёт его удалить, пока в него добавляют задачу.
            sprint = BacklogSprint.objects.select_for_update().filter(pk=sprint_id, team_id=obj.team_id).first()
            if sprint is None:
                raise ValidationError({"sprint_id": "Спринт не найден в этой команде."})
            obj.sprint = sprint

    if "status" in data:
        error = transition_error(obj.status, data["status"])
        if error:
            raise ValidationError({"status": error})
        obj.status = data["status"]
    if obj.sprint_id is not None and obj.status == BacklogStatus.NEW:
        # Задача в спринте не может оставаться «Новой»: привязка к спринту переводит её в «В спринте».
        obj.status = BacklogStatus.IN_SPRINT

    if obj.status == BacklogStatus.IN_SPRINT and obj.sprint_id is None:
        raise ValidationError({"status": "Сначала выберите спринт."})


def _save_with_version(obj):
    obj.version += 1
    obj.save()
    return obj


# --- этапы -----------------------------------------------------------------------


def create_stage(access: TeamAccess, user, data) -> BacklogStage:
    return BacklogStage.objects.create(
        team_id=access.team_id,
        title=data["title"],
        description=data.get("description", ""),
        start_date=data.get("start_date"),
        end_date=data.get("end_date"),
        position=_next_position(BacklogStage.objects.filter(team_id=access.team_id)),
        created_by=user,
    )


@transaction.atomic
def update_stage(stage_id: int, data) -> BacklogStage:
    stage = _locked(BacklogStage.objects.select_for_update(), stage_id)
    _check_version(stage, data.get("version"))
    _apply_simple_fields(stage, data, ("title", "description", "start_date", "end_date"))
    _check_date_order(stage.start_date, stage.end_date)
    return _save_with_version(stage)


@transaction.atomic
def reorder_stages(access: TeamAccess, ids: list[int]):
    _reorder(BacklogStage.objects.select_for_update().filter(team_id=access.team_id), ids)


@transaction.atomic
def reorder_tasks(stage: BacklogStage, ids: list[int]):
    _reorder(BacklogTask.objects.select_for_update().filter(stage=stage), ids)


def _reorder(queryset, ids):
    objects = {obj.id: obj for obj in queryset}
    if len(ids) != len(set(ids)) or set(ids) != set(objects):
        raise ValidationError({"ids": "Нужно передать все объекты этого уровня ровно по одному разу."})
    for position, obj_id in enumerate(ids):
        obj = objects[obj_id]
        if obj.position != position:
            obj.position = position
            obj.save(update_fields=["position", "updated_at"])


# --- задачи ----------------------------------------------------------------------


def create_task(access: TeamAccess, user, stage: BacklogStage, data, rework_of=None) -> BacklogTask:
    responsible = _team_member(access, data["responsible_id"], "responsible_id")
    return BacklogTask.objects.create(
        stage=stage,
        team_id=stage.team_id,
        title=data["title"],
        description=data.get("description", ""),
        responsible=responsible,
        start_date=data["start_date"],
        end_date=data["end_date"],
        position=_next_position(BacklogTask.objects.filter(stage=stage)),
        rework_of=rework_of,
        created_by=user,
    )


@transaction.atomic
def update_task(access: TeamAccess, task_id: int, data) -> BacklogTask:
    task = _locked(BacklogTask.objects.select_for_update(), task_id)
    _check_version(task, data.get("version"))
    _apply_simple_fields(task, data, ("title", "description", "start_date", "end_date"))
    _check_date_order(task.start_date, task.end_date)
    if "responsible_id" in data:
        task.responsible = _team_member(access, data["responsible_id"], "responsible_id")
    _apply_sprint_and_status(task, data)
    return _save_with_version(task)


@transaction.atomic
def complete_task(access: TeamAccess, task_id: int) -> BacklogTask:
    if not can_complete_task(access):
        raise PermissionDenied("Задачу завершает куратор команды.")
    task = _locked(BacklogTask.objects.select_for_update(), task_id)
    return _complete(task)


@transaction.atomic
def create_task_rework(access: TeamAccess, user, task_id: int, data) -> BacklogTask:
    original = _locked(BacklogTask.objects.select_for_update(), task_id)
    _require_review(original)
    rework = create_task(access, user, original.stage, data, rework_of=original)
    BacklogComment.objects.create(task=rework, author=user, text=data["comment"])
    return rework


# --- подзадачи -------------------------------------------------------------------


def create_subtask(access: TeamAccess, user, task: BacklogTask, data, rework_of=None, executor=None) -> BacklogSubtask:
    executor = executor or _team_member(access, data["executor_id"], "executor_id")
    return BacklogSubtask.objects.create(
        task=task,
        team_id=task.team_id,
        title=data["title"],
        description=data.get("description", ""),
        executor=executor,
        start_date=data["start_date"],
        end_date=data["end_date"],
        position=_next_position(BacklogSubtask.objects.filter(task=task)),
        rework_of=rework_of,
        created_by=user,
    )


@transaction.atomic
def bulk_create_subtasks(access: TeamAccess, user, task: BacklogTask, data) -> list[BacklogSubtask]:
    # По одной через save(): bulk_create не выдал бы коды объектам.
    executor = _team_member(access, data["executor_id"], "executor_id")
    return [
        create_subtask(access, user, task, {**data, "title": title, "description": ""}, executor=executor)
        for title in data["titles"]
    ]


@transaction.atomic
def update_subtask(access: TeamAccess, subtask_id: int, data) -> BacklogSubtask:
    subtask = _locked(BacklogSubtask.objects.select_for_update(), subtask_id)
    _check_version(subtask, data.get("version"))
    _apply_simple_fields(subtask, data, ("title", "description", "start_date", "end_date"))
    _check_date_order(subtask.start_date, subtask.end_date)
    if "executor_id" in data:
        subtask.executor = _team_member(access, data["executor_id"], "executor_id")
    _apply_sprint_and_status(subtask, data)
    return _save_with_version(subtask)


@transaction.atomic
def complete_subtask(access: TeamAccess, user, subtask_id: int) -> BacklogSubtask:
    subtask = _locked(BacklogSubtask.objects.select_for_update(of=("self",)).select_related("task"), subtask_id)
    if not can_complete_subtask(access, user, subtask):
        raise PermissionDenied("Подзадачу завершает ответственный задачи или куратор команды.")
    return _complete(subtask)


@transaction.atomic
def create_subtask_rework(access: TeamAccess, user, subtask_id: int, data) -> BacklogSubtask:
    original = _locked(BacklogSubtask.objects.select_for_update(of=("self",)).select_related("task"), subtask_id)
    _require_review(original)
    rework = create_subtask(access, user, original.task, data, rework_of=original)
    BacklogComment.objects.create(subtask=rework, author=user, text=data["comment"])
    return rework


def _complete(obj):
    if obj.status == BacklogStatus.DONE:
        raise Conflict({"detail": "Уже завершена: повторное завершение недоступно."})
    obj.status = BacklogStatus.DONE
    return _save_with_version(obj)


def _require_review(obj):
    if obj.status != BacklogStatus.REVIEW:
        raise ValidationError({"status": "Доработку создают для задачи в статусе «На проверке»."})


# --- работы (чек-лист подзадачи) ----------------------------------------------------


def create_work_item(user, subtask: BacklogSubtask, data) -> BacklogWorkItem:
    return BacklogWorkItem.objects.create(
        subtask=subtask,
        title=data["title"],
        due_date=data.get("due_date"),
        position=_next_position(BacklogWorkItem.objects.filter(subtask=subtask)),
        created_by=user,
    )


@transaction.atomic
def update_work_item(work_id: int, data) -> BacklogWorkItem:
    work = _locked(BacklogWorkItem.objects.select_for_update(), work_id)
    _apply_simple_fields(work, data, ("title", "is_done", "due_date"))
    work.save()
    return work


# --- удаление --------------------------------------------------------------------


def _children(obj) -> dict:
    if isinstance(obj, BacklogStage):
        return {
            "tasks": BacklogTask.objects.filter(stage=obj).count(),
            "subtasks": BacklogSubtask.objects.filter(task__stage=obj).count(),
            "work_items": BacklogWorkItem.objects.filter(subtask__task__stage=obj).count(),
        }
    if isinstance(obj, BacklogTask):
        return {
            "subtasks": BacklogSubtask.objects.filter(task=obj).count(),
            "work_items": BacklogWorkItem.objects.filter(subtask__task=obj).count(),
        }
    if isinstance(obj, BacklogSubtask):
        return {"work_items": BacklogWorkItem.objects.filter(subtask=obj).count()}
    return {}


@transaction.atomic
def delete_object(access: TeamAccess, user, obj, confirm: bool):
    """Удаление с проверкой прав; если есть дочерние объекты — только с подтверждением (BL-22).

    Объект блокируется, поэтому пользователь подтверждает ровно то, что будет удалено.
    """
    obj = _locked(type(obj).objects.select_for_update(), obj.pk)
    if not can_delete(access, user, obj):
        raise PermissionDenied("Удалять можно только созданное вами; куратор удаляет всё в своей команде.")
    children = _children(obj)
    if any(children.values()) and not confirm:
        raise Conflict(
            {
                "detail": "Вместе с объектом удалятся вложенные элементы. Повторите запрос с ?confirm=true.",
                "children": children,
            }
        )
    obj.delete()


# --- комментарии -------------------------------------------------------------------


def add_comment(user, text: str, task=None, subtask=None) -> BacklogComment:
    return BacklogComment.objects.create(task=task, subtask=subtask, author=user, text=text)


# --- спринты ---------------------------------------------------------------------


def create_sprint(access: TeamAccess, user, data) -> BacklogSprint:
    return BacklogSprint.objects.create(
        team_id=access.team_id,
        title=data["title"],
        start_date=data["start_date"],
        end_date=data["end_date"],
        created_by=user,
    )


@transaction.atomic
def update_sprint(sprint_id: int, data) -> BacklogSprint:
    sprint = _locked(BacklogSprint.objects.select_for_update(), sprint_id)
    _apply_simple_fields(sprint, data, ("title", "start_date", "end_date"))
    _check_date_order(sprint.start_date, sprint.end_date)
    sprint.save()
    return sprint


@transaction.atomic
def delete_sprint(access: TeamAccess, user, sprint_id: int):
    # Блокировка: пока спринт удаляется, в него нельзя добавить задачу (и наоборот).
    sprint = _locked(BacklogSprint.objects.select_for_update(), sprint_id)
    if not can_delete(access, user, sprint):
        raise PermissionDenied("Удалять можно только созданное вами; куратор удаляет всё в своей команде.")
    # Спринт с задачами (в том числе завершёнными) не удаляется, чтобы не терять историю работы.
    if BacklogTask.objects.filter(sprint=sprint).exists() or BacklogSubtask.objects.filter(sprint=sprint).exists():
        raise Conflict({"detail": "К спринту привязаны задачи — удалить его нельзя."})
    sprint.delete()
