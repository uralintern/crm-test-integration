import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from integrations.vk.services import VKAPIError, VKConfigurationError, send_vk_message
from planner.automation_defaults import create_default_planner_automation_config
from planner.models import PlannerAutomationConfig, PlannerAutomationExecutionLog, PlannerWorkspaceState
from users.models import Notification, Profile
from users.vk_profiles import refresh_profile_vk_user_id


DONE_STATUSES = {"готово", "done", "завершено"}
REVIEW_STATUSES = {"на проверке", "review"}
STARTED_STATUSES = {"в работе", "in progress", "in-progress"}
OVERLOADED_ACTIVE_TASK_LIMIT = 5
STALE_TASK_DAYS = 3


@dataclass
class PlannerAutomationEvent:
    code: str
    entity_type: str
    entity_id: str
    item: dict[str, Any]
    previous_item: dict[str, Any] | None
    team: dict[str, Any] | None
    event_id: int
    team_id: int | None
    fingerprint: str


def to_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def normalized_text(value: Any) -> str:
    return str(value or "").strip()


def lower_text(value: Any) -> str:
    return normalized_text(value).lower()


def item_id(item: dict[str, Any]) -> str:
    return normalized_text(item.get("id"))


def item_team_id(item: dict[str, Any]) -> int | None:
    return to_int(item.get("teamId", item.get("team_id")))


def item_assignee_id(item: dict[str, Any]) -> int | None:
    return to_int(item.get("assigneeId", item.get("assignee_id")))


def item_member_id(item: dict[str, Any]) -> int | None:
    return to_int(item.get("memberId", item.get("member_id")))


def item_recipient_id(item: dict[str, Any]) -> int | None:
    return item_assignee_id(item) or item_member_id(item)


def item_status(item: dict[str, Any]) -> str:
    return normalized_text(item.get("status"))


def item_end_date(item: dict[str, Any]):
    return parse_date(normalized_text(item.get("endDate", item.get("end_date"))))


def item_updated_at(item: dict[str, Any]):
    raw_value = normalized_text(item.get("updatedAt", item.get("updated_at")))
    if not raw_value:
        return None
    parsed = parse_datetime(raw_value)
    if not parsed:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def is_done_status(status_value: Any) -> bool:
    return lower_text(status_value) in DONE_STATUSES


def is_review_status(status_value: Any) -> bool:
    return lower_text(status_value) in REVIEW_STATUSES


def is_started_status(status_value: Any) -> bool:
    return lower_text(status_value) in STARTED_STATUSES


def is_active_task(item: dict[str, Any]) -> bool:
    return not is_done_status(item_status(item))


def stable_fingerprint(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def list_by_id(items: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list):
        return {}
    return {
        item_id(item): item
        for item in items
        if isinstance(item, dict) and item_id(item)
    }


def team_by_id(teams: Any) -> dict[int, dict[str, Any]]:
    if not isinstance(teams, list):
        return {}
    result = {}
    for team in teams:
        if not isinstance(team, dict):
            continue
        team_id = to_int(team.get("id"))
        if team_id is not None:
            result[team_id] = team
    return result


def team_event_id(team: dict[str, Any] | None) -> int | None:
    if not isinstance(team, dict):
        return None
    return to_int(team.get("eventId", team.get("event_id")))


def team_curator_id(team: dict[str, Any] | None) -> int | None:
    if not isinstance(team, dict):
        return None
    return to_int(team.get("curatorId", team.get("curator_id")))


def task_stage_id(item: dict[str, Any]) -> str:
    if item.get("type") == "parent":
        return "backlog"
    if lower_text(item.get("status")) == "риск по сроку":
        return "risk"
    if is_done_status(item.get("status")):
        return "done"
    if is_review_status(item.get("status")):
        return "review"
    if is_started_status(item.get("status")):
        return "in-progress"
    if bool(item.get("inSprint", item.get("in_sprint", False))):
        return "planned"
    return "backlog"


def stage_by_id(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        normalized_text(stage.get("id")): stage
        for stage in config.get("stages", [])
        if isinstance(stage, dict) and normalized_text(stage.get("id"))
    }


def target_status_for_stage(config: dict[str, Any], stage_id: str) -> str:
    stage = stage_by_id(config).get(stage_id)
    if stage and normalized_text(stage.get("title")):
        return normalized_text(stage.get("title"))
    fallback = {
        "planned": "Запланировано",
        "in-progress": "В работе",
        "review": "На проверке",
        "done": "Готово",
        "risk": "Риск по сроку",
    }
    return fallback.get(stage_id, "Запланировано")


def event_context(event: PlannerAutomationEvent) -> dict[str, Any]:
    item = event.item
    team = event.team or {}
    end_date = item_end_date(item)
    today = timezone.localdate()
    days_to_deadline = (end_date - today).days if end_date else None
    return {
        **item,
        "type": event.entity_type,
        "eventCode": event.code,
        "teamId": event.team_id,
        "eventId": event.event_id,
        "teamName": team.get("name", ""),
        "teamConfirmed": bool(team.get("confirmed", False)),
        "curatorId": team_curator_id(team),
        "assigneeId": item_recipient_id(item),
        "status": item_status(item),
        "task_status": item_status(item),
        "taskStatus": item_status(item),
        "title": item.get("title", ""),
        "task": item.get("title", ""),
        "task_type": event.entity_type,
        "taskType": event.entity_type,
        "team": team.get("name", "") or event.team_id,
        "curator": team_curator_id(team),
        "assignee": item_recipient_id(item),
        "deadline": end_date.isoformat() if end_date else "",
        "in_sprint": item.get("inSprint", item.get("in_sprint", "")),
        "inSprint": item.get("inSprint", item.get("in_sprint", "")),
        "daysToDeadline": days_to_deadline,
        "previousDeadline": (event.previous_item or {}).get("endDate", (event.previous_item or {}).get("end_date", "")),
        "deadlineChanged": bool(item.get("deadlineChanged", item.get("deadline_changed", False))),
        "memberId": item.get("memberId", item.get("member_id", "")),
        "activeTaskCount": item.get("activeTaskCount", item.get("active_task_count", "")),
        "inactiveDays": item.get("inactiveDays", item.get("inactive_days", "")),
        "isOverdue": days_to_deadline is not None and days_to_deadline < 0 and not is_done_status(item_status(item)),
    }


def condition_value(context: dict[str, Any], field: str) -> Any:
    if not field:
        return ""
    if field in context:
        return context[field]
    camel = "".join(part.capitalize() if index else part for index, part in enumerate(field.split("_")))
    return context.get(camel, "")


def compare_values(actual: Any, operator: str, expected: Any, expected_to: Any = None) -> bool:
    actual_text = normalized_text(actual)
    expected_text = normalized_text(expected)
    if operator == "equals":
        return actual_text.lower() == expected_text.lower()
    if operator == "not_equals":
        return actual_text.lower() != expected_text.lower()
    if operator == "contains":
        return expected_text.lower() in actual_text.lower()
    if operator == "not_contains":
        return expected_text.lower() not in actual_text.lower()
    if operator == "filled":
        return bool(actual_text)
    if operator == "empty":
        return not actual_text

    try:
        actual_num = float(actual_text)
        expected_num = float(expected_text)
    except (TypeError, ValueError):
        return False

    if operator == "greater_or_equal":
        return actual_num >= expected_num
    if operator == "less_or_equal":
        return actual_num <= expected_num
    if operator == "in_range":
        try:
            expected_to_num = float(normalized_text(expected_to))
        except (TypeError, ValueError):
            return False
        return expected_num <= actual_num <= expected_to_num
    return False


def conditions_match(settings: dict[str, Any] | None, event: PlannerAutomationEvent) -> bool:
    condition = (settings or {}).get("condition") or {}
    rules = condition.get("rules") if isinstance(condition, dict) else []
    if not isinstance(rules, list) or not rules:
        return True
    mode = condition.get("mode", "all")
    context = event_context(event)
    checks = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        checks.append(
            compare_values(
                condition_value(context, normalized_text(rule.get("field"))),
                normalized_text(rule.get("operator")) or "equals",
                rule.get("value", ""),
                rule.get("valueTo", ""),
            )
        )
    if not checks:
        return True
    return any(checks) if mode == "any" else all(checks)


def render_template(template: str, event: PlannerAutomationEvent) -> str:
    context = event_context(event)
    result = template or ""
    for key, value in context.items():
        result = result.replace("{" + key + "}", normalized_text(value))
    return result


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


def create_log(
    *,
    config_model: PlannerAutomationConfig,
    event: PlannerAutomationEvent,
    rule: dict[str, Any],
    rule_kind: str,
    status: str,
    message: str = "",
    scheduled_for=None,
) -> PlannerAutomationExecutionLog:
    rule_id = normalized_text(rule.get("id")) or normalized_text(rule.get("action") or rule.get("eventCode"))
    run_key = stable_fingerprint(
        {
            "config": config_model.pk,
            "rule": rule_id,
            "kind": rule_kind,
            "event": event.code,
            "entityType": event.entity_type,
            "entityId": event.entity_id,
            "fingerprint": event.fingerprint,
        }
    )
    log, created = PlannerAutomationExecutionLog.objects.get_or_create(
        run_key=run_key,
        defaults={
            "config": config_model,
            "event_id": event.event_id,
            "team_id": event.team_id,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "event_code": event.code,
            "rule_kind": rule_kind,
            "rule_id": rule_id,
            "status": status,
            "message": message,
            "context": event_context(event),
            "scheduled_for": scheduled_for,
            "executed_at": timezone.now() if status != PlannerAutomationExecutionLog.STATUS_PENDING else None,
        },
    )
    if created:
        return log
    return log


def log_exists(config_model: PlannerAutomationConfig, event: PlannerAutomationEvent, rule: dict[str, Any], rule_kind: str) -> bool:
    rule_id = normalized_text(rule.get("id")) or normalized_text(rule.get("action") or rule.get("eventCode"))
    run_key = stable_fingerprint(
        {
            "config": config_model.pk,
            "rule": rule_id,
            "kind": rule_kind,
            "event": event.code,
            "entityType": event.entity_type,
            "entityId": event.entity_id,
            "fingerprint": event.fingerprint,
        }
    )
    return PlannerAutomationExecutionLog.objects.filter(run_key=run_key).exists()


def should_delay(rule: dict[str, Any]) -> tuple[bool, Any]:
    settings = rule.get("settings") if isinstance(rule.get("settings"), dict) else {}
    delay_minutes = to_int(settings.get("delayMinutes")) or 0
    if settings.get("timing") == "delayed" and delay_minutes > 0:
        return True, timezone.now() + timedelta(minutes=delay_minutes)
    return False, None


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


def execute_pending_log(log: PlannerAutomationExecutionLog, workspace: PlannerWorkspaceState) -> bool:
    config = config_model_to_dict(log.config)
    rules = config.get("robots" if log.rule_kind == "robot" else "triggers", [])
    rule = next(
        (item for item in rules if isinstance(item, dict) and normalized_text(item.get("id")) == log.rule_id),
        None,
    )
    if not rule:
        log.status = PlannerAutomationExecutionLog.STATUS_FAILED
        log.message = "Правило для отложенного выполнения не найдено."
        log.executed_at = timezone.now()
        log.save(update_fields=["status", "message", "executed_at"])
        return False

    teams = team_by_id(workspace.teams)
    team = teams.get(to_int(log.team_id) or -1)
    items = workspace.subtasks if log.entity_type == "subtask" else workspace.parent_tasks
    current_item = None
    if log.entity_type == "team":
        current_item = {"id": log.team_id, "teamId": log.team_id, "title": (team or {}).get("name", ""), "type": "team", **(team or {})}
    elif isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and item_id(item) == log.entity_id:
                current_item = item
                break

    if not current_item:
        log.status = PlannerAutomationExecutionLog.STATUS_SKIPPED
        log.message = "Элемент для отложенного выполнения не найден."
        log.executed_at = timezone.now()
        log.save(update_fields=["status", "message", "executed_at"])
        return False

    event = PlannerAutomationEvent(
        code=log.event_code,
        entity_type=log.entity_type,
        entity_id=log.entity_id,
        item={**current_item, "type": log.entity_type},
        previous_item=None,
        team=team,
        event_id=log.event_id,
        team_id=log.team_id,
        fingerprint=stable_fingerprint({"pendingLog": log.pk}),
    )

    if not conditions_match(rule.get("settings"), event):
        log.status = PlannerAutomationExecutionLog.STATUS_SKIPPED
        log.message = "Условия отложенного правила больше не выполнены."
        log.executed_at = timezone.now()
        log.save(update_fields=["status", "message", "executed_at"])
        return False

    changed = False
    if log.rule_kind == "trigger":
        target_stage_id = normalized_text(rule.get("targetStageId")) or normalized_text(rule.get("stageId"))
        changed = update_item_status(workspace, event, target_status_for_stage(config, target_stage_id))
        run_stage_robots(workspace, log.config, config, event, target_stage_id)
    else:
        action = normalized_text(rule.get("action"))
        title = render_template(rule.get("subject") or rule.get("title", ""), event) or "Уведомление планировщика"
        message = render_template(rule.get("message") or rule.get("description", ""), event)
        if action == "notification.assignee":
            changed = create_notification(item_recipient_id(event.item), title, message)
        elif action in {"notification.curator", "notification.deadline", "task.review"}:
            changed = create_notification(team_curator_id(event.team), title, message)
        elif action == "message.vk.assignee":
            try:
                changed = send_vk_notification(item_recipient_id(event.item), message)
            except (VKConfigurationError, VKAPIError, ValueError):
                changed = False
        elif action == "message.vk.curator":
            try:
                changed = send_vk_notification(team_curator_id(event.team), message)
            except (VKConfigurationError, VKAPIError, ValueError):
                changed = False
        elif action == "task.create":
            changed = run_robot_action(workspace, log.config, config, rule, event)
        else:
            changed = False

    log.status = PlannerAutomationExecutionLog.STATUS_SUCCESS if changed else PlannerAutomationExecutionLog.STATUS_SKIPPED
    log.message = "Отложенное правило выполнено." if changed else "Отложенное правило не внесло изменений."
    log.executed_at = timezone.now()
    log.save(update_fields=["status", "message", "executed_at"])
    return changed


def run_stage_robots(
    workspace: PlannerWorkspaceState,
    config_model: PlannerAutomationConfig,
    config: dict[str, Any],
    event: PlannerAutomationEvent,
    stage_id: str,
) -> bool:
    changed = False
    robots = config.get("robots") if isinstance(config.get("robots"), list) else []
    for robot in robots:
        if not isinstance(robot, dict) or not robot.get("enabled", False) or robot.get("deleted", False):
            continue
        if normalized_text(robot.get("stageId")) != stage_id:
            continue
        if not conditions_match(robot.get("settings"), event):
            create_log(
                config_model=config_model,
                event=event,
                rule=robot,
                rule_kind="robot",
                status=PlannerAutomationExecutionLog.STATUS_SKIPPED,
                message="Условия робота не выполнены.",
            )
            continue
        changed = run_robot_action(workspace, config_model, config, robot, event) or changed
    return changed


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


def run_trigger(
    workspace: PlannerWorkspaceState,
    config_model: PlannerAutomationConfig,
    config: dict[str, Any],
    trigger: dict[str, Any],
    event: PlannerAutomationEvent,
) -> bool:
    if log_exists(config_model, event, trigger, "trigger"):
        return False
    if not conditions_match(trigger.get("settings"), event):
        create_log(
            config_model=config_model,
            event=event,
            rule=trigger,
            rule_kind="trigger",
            status=PlannerAutomationExecutionLog.STATUS_SKIPPED,
            message="Условия триггера не выполнены.",
        )
        return False

    target_stage_id = normalized_text(trigger.get("targetStageId")) or normalized_text(trigger.get("stageId"))
    target_status = target_status_for_stage(config, target_stage_id)
    current_stage_id = task_stage_id(event.item)
    target_index = [stage.get("id") for stage in config.get("stages", [])].index(target_stage_id) if target_stage_id in [stage.get("id") for stage in config.get("stages", [])] else -1
    current_index = [stage.get("id") for stage in config.get("stages", [])].index(current_stage_id) if current_stage_id in [stage.get("id") for stage in config.get("stages", [])] else -1
    if target_index >= 0 and current_index >= 0 and target_index < current_index and not trigger.get("allowBackTransition", False):
        create_log(
            config_model=config_model,
            event=event,
            rule=trigger,
            rule_kind="trigger",
            status=PlannerAutomationExecutionLog.STATUS_SKIPPED,
            message="Переход на предыдущую стадию запрещен настройкой триггера.",
        )
        return False

    delayed, scheduled_for = should_delay(trigger)
    if delayed:
        create_log(
            config_model=config_model,
            event=event,
            rule=trigger,
            rule_kind="trigger",
            status=PlannerAutomationExecutionLog.STATUS_PENDING,
            message="Запланировано отложенное выполнение триггера.",
            scheduled_for=scheduled_for,
        )
        return False

    changed = update_item_status(workspace, event, target_status)
    create_log(
        config_model=config_model,
        event=event,
        rule=trigger,
        rule_kind="trigger",
        status=PlannerAutomationExecutionLog.STATUS_SUCCESS,
        message=f"Триггер перевел элемент на стадию «{target_status}»." if changed else "Триггер обработан без изменения статуса.",
    )
    run_stage_robots(workspace, config_model, config, event, target_stage_id)
    return changed


def run_config_for_event(
    workspace: PlannerWorkspaceState,
    config_model: PlannerAutomationConfig,
    event: PlannerAutomationEvent,
) -> bool:
    config = config_model_to_dict(config_model)
    changed = False
    triggers = config.get("triggers") if isinstance(config.get("triggers"), list) else []
    for trigger in triggers:
        if not isinstance(trigger, dict) or not trigger.get("enabled", False) or trigger.get("deleted", False):
            continue
        if normalized_text(trigger.get("eventCode")) != event.code:
            continue
        trigger_changed = run_trigger(workspace, config_model, config, trigger, event)
        if (
            not trigger_changed
            and event.code == "task.sprint_added"
            and event.entity_type == "subtask"
            and conditions_match(trigger.get("settings"), event)
        ):
            target_stage_id = normalized_text(trigger.get("targetStageId")) or normalized_text(trigger.get("stageId")) or "planned"
            target_status = target_status_for_stage(config, target_stage_id)
            if item_status(event.item) != target_status:
                trigger_changed = update_item_status(workspace, event, target_status)
        changed = trigger_changed or changed

    changed = run_stage_robots(workspace, config_model, config, event, task_stage_id(event.item)) or changed
    return changed


def apply_sprint_added_fallback(previous_state: dict[str, Any], workspace: PlannerWorkspaceState) -> bool:
    current_state = workspace_state_dict(workspace)
    previous_subtasks = list_by_id(previous_state.get("subtasks"))
    current_subtasks = list_by_id(current_state.get("subtasks"))
    teams = team_by_id(current_state.get("teams"))
    changed = False

    for entity_id, current in current_subtasks.items():
        if not isinstance(current, dict):
            continue
        previous = previous_subtasks.get(entity_id)
        previous_in_sprint = bool(previous.get("inSprint", previous.get("in_sprint", False))) if isinstance(previous, dict) else False
        current_in_sprint = bool(current.get("inSprint", current.get("in_sprint", False)))
        if previous_in_sprint or not current_in_sprint:
            continue

        team = teams.get(item_team_id(current) or -1)
        event_id = team_event_id(team)
        if event_id is None:
            continue

        event = PlannerAutomationEvent(
            code="task.sprint_added",
            entity_type="subtask",
            entity_id=item_id(current),
            item={**current, "type": "subtask"},
            previous_item={**previous, "type": "subtask"} if isinstance(previous, dict) else None,
            team=team,
            event_id=event_id,
            team_id=item_team_id(current),
            fingerprint=stable_fingerprint({"inSprint": True}),
        )
        config_model = get_or_create_config(event_id)
        config = config_model_to_dict(config_model)
        triggers = config.get("triggers") if isinstance(config.get("triggers"), list) else []
        for trigger in triggers:
            if not isinstance(trigger, dict) or not trigger.get("enabled", False) or trigger.get("deleted", False):
                continue
            if normalized_text(trigger.get("eventCode")) != "task.sprint_added":
                continue
            if not conditions_match(trigger.get("settings"), event):
                continue

            target_stage_id = normalized_text(trigger.get("targetStageId")) or normalized_text(trigger.get("stageId")) or "planned"
            target_status = target_status_for_stage(config, target_stage_id)
            if update_item_status(workspace, event, target_status):
                create_log(
                    config_model=config_model,
                    event=event,
                    rule=trigger,
                    rule_kind="trigger",
                    status=PlannerAutomationExecutionLog.STATUS_SUCCESS,
                    message=f"Триггер перевел элемент на стадию «{target_status}».",
                )
                run_stage_robots(workspace, config_model, config, event, target_stage_id)
                changed = True
            break

    return changed


def config_model_to_dict(config_model: PlannerAutomationConfig) -> dict[str, Any]:
    if not config_model.stages and not config_model.triggers and not config_model.robots:
        return create_default_planner_automation_config(config_model.event_id)
    return {
        "scope": config_model.scope,
        "eventId": config_model.event_id,
        "updatedAt": config_model.updated_at.isoformat(),
        "stages": config_model.stages,
        "triggers": config_model.triggers,
        "robots": config_model.robots,
    }


def has_task_data_changed(item: dict[str, Any], previous: dict[str, Any] | None) -> bool:
    if not previous:
        return False
    fields = (
        ("title",),
        ("role",),
        ("assigneeId", "assignee_id"),
        ("startDate", "start_date"),
        ("endDate", "end_date"),
        ("inSprint", "in_sprint"),
        ("parentTaskId", "parent_task_id"),
    )
    for keys in fields:
        current_value = next((item.get(key) for key in keys if key in item), None)
        previous_value = next((previous.get(key) for key in keys if key in previous), None)
        if normalized_text(current_value) != normalized_text(previous_value):
            return True
    return False


def deadline_changed(item: dict[str, Any], previous: dict[str, Any] | None) -> bool:
    if not previous:
        return False
    return normalized_text(item.get("endDate", item.get("end_date"))) != normalized_text(
        previous.get("endDate", previous.get("end_date"))
    )


def detect_planner_events(previous_state: dict[str, Any], current_state: dict[str, Any]) -> list[PlannerAutomationEvent]:
    events: list[PlannerAutomationEvent] = []
    previous_teams = team_by_id(previous_state.get("teams"))
    current_teams = team_by_id(current_state.get("teams"))

    def build_event(code, entity_type, item, previous_item=None, fingerprint_payload=None):
        team = current_teams.get(item_team_id(item) or -1)
        event_id = team_event_id(team)
        if event_id is None:
            return
        payload = fingerprint_payload if fingerprint_payload is not None else item
        events.append(
            PlannerAutomationEvent(
                code=code,
                entity_type=entity_type,
                entity_id=item_id(item),
                item=item,
                previous_item=previous_item,
                team=team,
                event_id=event_id,
                team_id=item_team_id(item),
                fingerprint=stable_fingerprint(payload),
            )
        )

    previous_parents = list_by_id(previous_state.get("parent_tasks"))
    current_parents = list_by_id(current_state.get("parent_tasks"))
    for entity_id, item in current_parents.items():
        item = {**item, "type": "parent"}
        previous = previous_parents.get(entity_id)
        previous = {**previous, "type": "parent"} if previous else None
        if previous is None:
            build_event("task.created", "parent_task", item)
        elif item_assignee_id(item) != item_assignee_id(previous):
            build_event("task.assignee_changed", "parent_task", item, previous, {"assignee": item_assignee_id(item)})
        if previous is None or item_assignee_id(item) != item_assignee_id(previous):
            if item_assignee_id(item) is None and is_active_task(item):
                build_event("task.unassigned", "parent_task", item, previous, {"assignee": None})
        if previous is not None and deadline_changed(item, previous):
            build_event(
                "task.deadline_changed",
                "parent_task",
                {**item, "deadlineChanged": True},
                previous,
                {"deadline": item.get("endDate", item.get("end_date"))},
            )

    previous_subtasks = list_by_id(previous_state.get("subtasks"))
    current_subtasks = list_by_id(current_state.get("subtasks"))
    for entity_id, item in current_subtasks.items():
        item = {**item, "type": "subtask"}
        previous = previous_subtasks.get(entity_id)
        previous = {**previous, "type": "subtask"} if previous else None
        if previous is None:
            build_event("task.created", "subtask", item)
            if bool(item.get("inSprint", item.get("in_sprint", False))):
                build_event("task.sprint_added", "subtask", item, None, {"inSprint": True})
        else:
            if not bool(previous.get("inSprint", previous.get("in_sprint", False))) and bool(item.get("inSprint", item.get("in_sprint", False))):
                build_event("task.sprint_added", "subtask", item, previous, {"inSprint": True})
            if item_assignee_id(item) != item_assignee_id(previous):
                build_event("task.assignee_changed", "subtask", item, previous, {"assignee": item_assignee_id(item)})
            if item_status(item) != item_status(previous):
                build_event("task.status_changed", "subtask", item, previous, {"status": item_status(item)})
            if has_task_data_changed(item, previous):
                build_event("task.subtask_changed", "subtask", item, previous, {"item": item, "previous": previous})
            if deadline_changed(item, previous):
                build_event(
                    "task.deadline_changed",
                    "subtask",
                    {**item, "deadlineChanged": True},
                    previous,
                    {"deadline": item.get("endDate", item.get("end_date"))},
                )

        if previous is None or item_assignee_id(item) != item_assignee_id(previous):
            if item_assignee_id(item) is None and is_active_task(item):
                build_event("task.unassigned", "subtask", item, previous, {"assignee": None})

        if previous is None or item_status(item) != item_status(previous):
            if is_started_status(item_status(item)):
                build_event("task.status_started", "subtask", item, previous, {"status": item_status(item)})
            if is_review_status(item_status(item)):
                build_event("task.review_requested", "subtask", item, previous, {"status": item_status(item)})
            if is_done_status(item_status(item)):
                build_event("task.status_done", "subtask", item, previous, {"status": item_status(item)})

    today = timezone.localdate()
    for item in current_subtasks.values():
        item = {**item, "type": "subtask"}
        end_date = item_end_date(item)
        if not end_date or is_done_status(item_status(item)):
            continue
        days_left = (end_date - today).days
        if days_left == 1:
            build_event("task.deadline_soon", "subtask", item, current_subtasks.get(item_id(item)), {"date": today.isoformat(), "deadline": item.get("endDate")})
        elif days_left < 0:
            build_event("task.overdue", "subtask", item, current_subtasks.get(item_id(item)), {"date": today.isoformat(), "deadline": item.get("endDate")})

    for team_id, team in current_teams.items():
        previous = previous_teams.get(team_id)
        event_id = team_event_id(team)
        if event_id is None:
            continue
        team_item = {"id": team_id, "teamId": team_id, "title": team.get("name", ""), "type": "team", **team}
        if previous is None:
            if team.get("confirmed", False):
                events.append(PlannerAutomationEvent("team.confirmed", "team", str(team_id), team_item, None, team, event_id, team_id, stable_fingerprint({"confirmed": True})))
        else:
            if not previous.get("confirmed", False) and team.get("confirmed", False):
                events.append(PlannerAutomationEvent("team.confirmed", "team", str(team_id), team_item, previous, team, event_id, team_id, stable_fingerprint({"confirmed": True})))
            if team_curator_id(previous) != team_curator_id(team) and team_curator_id(team):
                events.append(PlannerAutomationEvent("team.curator_assigned", "team", str(team_id), team_item, previous, team, event_id, team_id, stable_fingerprint({"curatorId": team_curator_id(team)})))

    return events


def detect_planner_scan_events(current_state: dict[str, Any]) -> list[PlannerAutomationEvent]:
    events: list[PlannerAutomationEvent] = []
    teams = team_by_id(current_state.get("teams"))
    today = timezone.localdate()

    def append_event(code: str, entity_type: str, item: dict[str, Any], team: dict[str, Any] | None, fingerprint_payload: dict[str, Any]):
        event_id = team_event_id(team)
        team_id = item_team_id(item) or to_int((team or {}).get("id"))
        if event_id is None:
            return
        events.append(
            PlannerAutomationEvent(
                code=code,
                entity_type=entity_type,
                entity_id=item_id(item),
                item=item,
                previous_item=None,
                team=team,
                event_id=event_id,
                team_id=team_id,
                fingerprint=stable_fingerprint({"date": today.isoformat(), **fingerprint_payload}),
            )
        )

    tasks: list[tuple[str, dict[str, Any]]] = []
    for item in current_state.get("parent_tasks", []):
        if isinstance(item, dict):
            tasks.append(("parent_task", {**item, "type": "parent"}))
    for item in current_state.get("subtasks", []):
        if isinstance(item, dict):
            tasks.append(("subtask", {**item, "type": "subtask"}))

    active_by_user: dict[int, list[dict[str, Any]]] = {}
    active_by_team_user: dict[tuple[int, int], list[dict[str, Any]]] = {}

    for entity_type, item in tasks:
        team = teams.get(item_team_id(item) or -1)
        if not is_active_task(item):
            continue

        assignee_id = item_assignee_id(item)
        if assignee_id is None:
            append_event("task.unassigned", entity_type, item, team, {"code": "task.unassigned", "entity": item_id(item)})
        else:
            active_by_user.setdefault(assignee_id, []).append(item)
            team_id = item_team_id(item)
            if team_id is not None:
                active_by_team_user.setdefault((team_id, assignee_id), []).append(item)

        updated_at = item_updated_at(item)
        if updated_at:
            inactive_days = (timezone.now() - updated_at).days
            if inactive_days >= STALE_TASK_DAYS:
                append_event(
                    "task.stale",
                    entity_type,
                    {**item, "inactiveDays": inactive_days},
                    team,
                    {"code": "task.stale", "entity": item_id(item), "inactiveDays": inactive_days},
                )

    for member_id, items in active_by_user.items():
        if len(items) < OVERLOADED_ACTIVE_TASK_LIMIT:
            continue
        source_item = items[0]
        team = teams.get(item_team_id(source_item) or -1)
        append_event(
            "member.overloaded",
            "member",
            {
                "id": f"member-{member_id}-overloaded",
                "teamId": item_team_id(source_item),
                "memberId": member_id,
                "activeTaskCount": len(items),
                "title": "Участник перегружен",
                "type": "member",
            },
            team,
            {"code": "member.overloaded", "memberId": member_id, "count": len(items)},
        )

    for team_id, team in teams.items():
        if not isinstance(team, dict) or not team.get("confirmed", False):
            continue
        for member_id in _member_ids_from_team_like(team):
            if not active_by_team_user.get((team_id, member_id)):
                append_event(
                    "member.idle",
                    "member",
                    {
                        "id": f"team-{team_id}-member-{member_id}-idle",
                        "teamId": team_id,
                        "memberId": member_id,
                        "activeTaskCount": 0,
                        "title": "Участник без задач",
                        "type": "member",
                    },
                    team,
                    {"code": "member.idle", "teamId": team_id, "memberId": member_id},
                )

    return events


def _member_ids_from_team_like(team: dict[str, Any]) -> list[int]:
    member_ids = team.get("memberIds", team.get("member_ids", []))
    if not isinstance(member_ids, list):
        return []
    return [member_id for member_id in (to_int(value) for value in member_ids) if member_id is not None]


def workspace_state_dict(workspace: PlannerWorkspaceState) -> dict[str, Any]:
    return {
        "teams": workspace.teams if isinstance(workspace.teams, list) else [],
        "parent_tasks": workspace.parent_tasks if isinstance(workspace.parent_tasks, list) else [],
        "subtasks": workspace.subtasks if isinstance(workspace.subtasks, list) else [],
        "columns": workspace.columns if isinstance(workspace.columns, list) else [],
    }


def get_or_create_config(event_id: int) -> PlannerAutomationConfig:
    defaults = create_default_planner_automation_config(event_id)
    config, created = PlannerAutomationConfig.objects.get_or_create(
        scope=PlannerAutomationConfig.SCOPE_PLANNER,
        event_id=event_id,
        defaults={
            "stages": defaults["stages"],
            "triggers": defaults["triggers"],
            "robots": defaults["robots"],
        },
    )
    return config


@transaction.atomic
def run_planner_automation(previous_state: dict[str, Any], workspace: PlannerWorkspaceState) -> dict[str, int]:
    current_state = workspace_state_dict(workspace)
    events = detect_planner_events(previous_state, current_state) + detect_planner_scan_events(current_state)
    result = {"events": len(events), "changed": 0}
    for event in events:
        config = get_or_create_config(event.event_id)
        if run_config_for_event(workspace, config, event):
            result["changed"] += 1
    if apply_sprint_added_fallback(previous_state, workspace):
        result["changed"] += 1
    return result


def scan_planner_deadlines() -> dict[str, int]:
    workspace = PlannerWorkspaceState.objects.order_by("id").first()
    if not workspace:
        return {"events": 0, "changed": 0}
    current = workspace_state_dict(workspace)
    return run_planner_automation(current, workspace)


def run_due_planner_automation() -> dict[str, int]:
    workspace = PlannerWorkspaceState.objects.order_by("id").first()
    if not workspace:
        return {"processed": 0, "changed": 0}
    logs = PlannerAutomationExecutionLog.objects.filter(
        status=PlannerAutomationExecutionLog.STATUS_PENDING,
        scheduled_for__lte=timezone.now(),
    ).select_related("config").order_by("scheduled_for", "id")
    result = {"processed": 0, "changed": 0}
    for log in logs:
        result["processed"] += 1
        if execute_pending_log(log, workspace):
            result["changed"] += 1
    return result
