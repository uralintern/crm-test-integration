"""Действия роботов: уведомления, VK, смена статуса задачи."""

from typing import Any
from django.contrib.auth import get_user_model
from django.utils import timezone
from integrations.vk.services import VKAPIError, VKConfigurationError, send_vk_message
from planner.models import (
    PlannerAutomationConfig,
    PlannerAutomationExecutionLog,
    PlannerWorkspaceState,
)
from users.models import Notification, Profile
from users.vk_profiles import refresh_profile_vk_user_id
from .utils import normalized_text, to_int
from .events import PlannerAutomationEvent
from .items import item_id, item_recipient_id, item_status, team_curator_id
from .conditions import render_template
from .logs import create_log, log_exists, should_delay


def create_notification(user_id: int | None, title: str, message: str, link: str = "/planner") -> bool:
    if not user_id:
        return False
    user_model = get_user_model()
    if not user_model.objects.filter(pk=user_id).exists():
        return False
    Notification.objects.create(user_id=user_id, title=title[:255], message=message, link=link)
    return True


def send_vk_notification(user_id: int | None, message: str) -> bool:
    if not user_id:
        return False
    profile = Profile.objects.filter(user_id=user_id).only("vk", "vk_user_id", "vk_confirmed_at").first()
    vk_user_id = refresh_profile_vk_user_id(profile) if profile else None
    if not vk_user_id:
        raise ValueError("у пользователя не указан корректный VK")
    if profile and not profile.vk_confirmed_at:
        raise ValueError("пользователь не подтвердил VK-бота")
    send_vk_message(user_id=vk_user_id, message=message)
    return True


def run_robot_action(
    workspace: PlannerWorkspaceState,
    config_model: PlannerAutomationConfig,
    config: dict[str, Any],
    robot: dict[str, Any],
    event: PlannerAutomationEvent,
) -> bool:
    if log_exists(config_model, event, robot, "robot"):
        return False

    delayed, scheduled_for = should_delay(robot)
    if delayed:
        create_log(
            config_model=config_model,
            event=event,
            rule=robot,
            rule_kind="robot",
            status=PlannerAutomationExecutionLog.STATUS_PENDING,
            message="Запланировано отложенное выполнение робота.",
            scheduled_for=scheduled_for,
        )
        return False

    action = normalized_text(robot.get("action"))
    title = render_template(robot.get("subject") or robot.get("title", ""), event) or "Уведомление планировщика"
    message = render_template(robot.get("message") or robot.get("description", ""), event)
    success = False
    log_message = ""

    if action == "notification.assignee":
        success = create_notification(item_recipient_id(event.item), title, message)
        log_message = "Уведомление отправлено исполнителю." if success else "Исполнитель не найден."
    elif action in {"notification.curator", "notification.deadline", "task.review"}:
        success = create_notification(team_curator_id(event.team), title, message)
        log_message = "Уведомление отправлено куратору." if success else "Куратор команды не найден."
    elif action == "message.vk.assignee":
        try:
            success = send_vk_notification(item_recipient_id(event.item), message)
            log_message = "VK-сообщение отправлено исполнителю."
        except (VKConfigurationError, VKAPIError, ValueError) as exc:
            log_message = str(exc)
    elif action == "message.vk.curator":
        try:
            success = send_vk_notification(team_curator_id(event.team), message)
            log_message = "VK-сообщение отправлено куратору."
        except (VKConfigurationError, VKAPIError, ValueError) as exc:
            log_message = str(exc)
    elif action == "task.create":
        parent_tasks = workspace.parent_tasks if isinstance(workspace.parent_tasks, list) else []
        next_id = max([to_int(task.get("id")) or 0 for task in parent_tasks if isinstance(task, dict)] + [0]) + 1
        parent_tasks.append(
            {
                "id": next_id,
                "teamId": event.team_id,
                "title": title,
                "description": message,
                "assigneeId": team_curator_id(event.team),
                "startDate": timezone.localdate().isoformat(),
                "endDate": event.item.get("endDate", timezone.localdate().isoformat()),
                "automationRuleId": robot.get("id"),
                "sourceTaskId": event.entity_id,
            }
        )
        workspace.parent_tasks = parent_tasks
        workspace.save(update_fields=["parent_tasks", "updated_at"])
        success = True
        log_message = "Создана задача автоматизации."
    else:
        log_message = f"Действие робота {action} пока не поддерживается."

    create_log(
        config_model=config_model,
        event=event,
        rule=robot,
        rule_kind="robot",
        status=PlannerAutomationExecutionLog.STATUS_SUCCESS if success else PlannerAutomationExecutionLog.STATUS_SKIPPED,
        message=log_message,
    )
    return success


def update_item_status(workspace: PlannerWorkspaceState, event: PlannerAutomationEvent, status_value: str) -> bool:
    if event.entity_type != "subtask":
        return False
    subtasks = workspace.subtasks if isinstance(workspace.subtasks, list) else []
    changed = False
    for subtask in subtasks:
        if isinstance(subtask, dict) and item_id(subtask) == event.entity_id:
            if item_status(subtask) != status_value:
                subtask["status"] = status_value
                subtask["inSprint"] = True
                changed = True
            event.item = subtask
            break
    if changed:
        workspace.subtasks = subtasks
        columns = workspace.columns if isinstance(workspace.columns, list) else []
        if status_value and status_value not in columns:
            columns.append(status_value)
            workspace.columns = columns
        workspace.save(update_fields=["subtasks", "columns", "updated_at"])
    return changed
