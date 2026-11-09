"""Представление объектов бэклога в ответах API (snake_case)."""

from rest_framework import serializers

from users.serializers.common import build_user_display_name

from .selectors import StageNode, SubtaskNode, TaskNode
from .statuses import BacklogStatus

_datetime_field = serializers.DateTimeField()


def _date(value):
    return value.isoformat() if value else None


def _datetime(value):
    return _datetime_field.to_representation(value) if value else None


def user_ref(user):
    if user is None:
        return None
    return {"id": user.id, "name": build_user_display_name(user)}


def sprint_ref(sprint):
    if sprint is None:
        return None
    return {
        "id": sprint.id,
        "title": sprint.title,
        "start_date": _date(sprint.start_date),
        "end_date": _date(sprint.end_date),
    }


def _code_ref(obj):
    return {"id": obj.id, "code": obj.code} if obj is not None else None


def _status(value):
    return {"status": value, "status_label": BacklogStatus(value).label}


def subtask_row(node: SubtaskNode) -> dict:
    subtask = node.subtask
    return {
        "id": subtask.id,
        "type": "subtask",
        "code": subtask.code,
        "title": subtask.title,
        "description": subtask.description,
        "team_id": subtask.team_id,
        "task_id": subtask.task_id,
        "executor": user_ref(subtask.executor),
        "created_by": user_ref(subtask.created_by),
        **_status(subtask.status),
        "start_date": _date(subtask.start_date),
        "end_date": _date(subtask.end_date),
        "sprint": sprint_ref(subtask.sprint),
        "rework_of": _code_ref(subtask.rework_of),
        "progress": node.progress,
        "is_overdue": node.is_overdue,
        "position": subtask.position,
        "version": subtask.version,
        "created_at": _datetime(subtask.created_at),
        "updated_at": _datetime(subtask.updated_at),
    }


def task_row(node: TaskNode, subtask_nodes=None) -> dict:
    task = node.task
    subtask_nodes = node.visible_subtasks if subtask_nodes is None else subtask_nodes
    return {
        "id": task.id,
        "type": "task",
        "code": task.code,
        "title": task.title,
        "description": task.description,
        "team_id": task.team_id,
        "stage_id": task.stage_id,
        "responsible": user_ref(task.responsible),
        "created_by": user_ref(task.created_by),
        **_status(task.status),
        "start_date": _date(node.start_date),
        "end_date": _date(node.end_date),
        "planned_start_date": _date(task.start_date),
        "planned_end_date": _date(task.end_date),
        "start_date_is_auto": node.start_date_is_auto,
        "end_date_is_auto": node.end_date_is_auto,
        "sprint": sprint_ref(task.sprint),
        "rework_of": _code_ref(task.rework_of),
        "executors": [user_ref(user) for user in node.executors],
        "progress": node.progress,
        "is_overdue": node.is_overdue,
        "position": task.position,
        "version": task.version,
        "created_at": _datetime(task.created_at),
        "updated_at": _datetime(task.updated_at),
        "subtasks": [subtask_row(sub) for sub in subtask_nodes],
    }


def stage_row(node: StageNode) -> dict:
    stage = node.stage
    return {
        "id": stage.id,
        "type": "stage",
        "title": stage.title,
        "description": stage.description,
        "team_id": stage.team_id,
        "position": stage.position,
        "start_date": _date(stage.start_date),
        "end_date": _date(stage.end_date),
        "created_by": user_ref(stage.created_by),
        "version": stage.version,
        "created_at": _datetime(stage.created_at),
        "updated_at": _datetime(stage.updated_at),
        "tasks": [task_row(task) for task in node.tasks],
    }


def task_detail(node: TaskNode) -> dict:
    data = task_row(node, subtask_nodes=node.subtasks)
    data["stage"] = {"id": node.task.stage_id, "title": node.task.stage.title}
    return data


def work_item_row(item) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "is_done": item.is_done,
        "due_date": _date(item.due_date),
        "position": item.position,
    }


def sprint_row(sprint, is_current: bool) -> dict:
    return {
        **sprint_ref(sprint),
        "team_id": sprint.team_id,
        "is_current": is_current,
        "created_by": user_ref(sprint.created_by),
        "created_at": _datetime(sprint.created_at),
        "updated_at": _datetime(sprint.updated_at),
    }


def comment_row(comment) -> dict:
    return {
        "id": comment.id,
        "author": user_ref(comment.author),
        "text": comment.text,
        "created_at": _datetime(comment.created_at),
    }


def kanban_columns(columns) -> list[dict]:
    return [
        {
            "status": column.status,
            "label": BacklogStatus(column.status).label,
            "items": [task_row(node, subtask_nodes=[]) for node in column.tasks]
            + [subtask_row(node) for node in column.subtasks],
        }
        for column in columns
    ]


def subtask_detail(node: SubtaskNode) -> dict:
    subtask = node.subtask
    data = subtask_row(node)
    data["task"] = {
        "id": subtask.task_id,
        "code": subtask.task.code,
        "title": subtask.task.title,
        "responsible": user_ref(subtask.task.responsible),
    }
    data["work_items"] = [work_item_row(item) for item in subtask.work_items.all()]
    return data
