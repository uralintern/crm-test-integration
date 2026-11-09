"""Запуск автоматизации: роботы стадий, триггеры, отложенные правила, скан дедлайнов."""

from typing import Any
from django.db import transaction
from django.utils import timezone
from integrations.vk.services import VKAPIError, VKConfigurationError
from planner.models import (
    PlannerAutomationConfig,
    PlannerAutomationExecutionLog,
    PlannerWorkspaceState,
)
from .utils import normalized_text, stable_fingerprint, to_int
from .events import PlannerAutomationEvent
from .items import (
    item_id,
    item_recipient_id,
    item_status,
    item_team_id,
    list_by_id,
    task_stage_id,
    team_by_id,
    team_curator_id,
    team_event_id,
)
from .config import config_model_to_dict, get_or_create_config, target_status_for_stage
from .conditions import conditions_match, render_template
from .logs import create_log, log_exists, should_delay
from .actions import create_notification, run_robot_action, send_vk_notification, update_item_status
from .detection import detect_planner_events, detect_planner_scan_events


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


def workspace_state_dict(workspace: PlannerWorkspaceState) -> dict[str, Any]:
    return {
        "teams": workspace.teams if isinstance(workspace.teams, list) else [],
        "parent_tasks": workspace.parent_tasks if isinstance(workspace.parent_tasks, list) else [],
        "subtasks": workspace.subtasks if isinstance(workspace.subtasks, list) else [],
        "columns": workspace.columns if isinstance(workspace.columns, list) else [],
    }


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
