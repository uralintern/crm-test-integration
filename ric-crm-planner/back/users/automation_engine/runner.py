"""Запуск автоматизации: роботы стадий, триггеры, отложенные правила."""

from typing import Any
from django.db import transaction
from django.utils import timezone
from integrations.vk.crm_notifications import scan_chat_membership_for_sent_applications
from users.models import Application, CRMAutomationConfig, CRMAutomationExecutionLog
from .utils import normalized_text, stable_fingerprint
from .events import CRMAutomationEvent
from .config import (
    config_model_to_dict,
    get_or_create_config,
    status_stage_id,
    target_status_for_stage,
)
from .conditions import application_status, conditions_match
from .logs import create_log, log_exists, should_delay
from .actions import run_robot_action, update_application_status


def run_stage_robots(config_model: CRMAutomationConfig, config: dict[str, Any], event: CRMAutomationEvent, stage_id: str) -> bool:
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
                status=CRMAutomationExecutionLog.STATUS_SKIPPED,
                message="Условия робота не выполнены.",
            )
            continue
        changed = run_robot_action(config_model, robot, event) or changed
    return changed


def run_trigger(config_model: CRMAutomationConfig, config: dict[str, Any], trigger: dict[str, Any], event: CRMAutomationEvent) -> str:
    if log_exists(config_model, event, trigger, "trigger"):
        return ""
    if not conditions_match(trigger.get("settings"), event):
        create_log(
            config_model=config_model,
            event=event,
            rule=trigger,
            rule_kind="trigger",
            status=CRMAutomationExecutionLog.STATUS_SKIPPED,
            message="Условия триггера не выполнены.",
        )
        return ""

    source_stage_id = normalized_text(trigger.get("stageId"))
    target_stage_id = source_stage_id
    if event.code == "request.status_changed":
        source_status = target_status_for_stage(config, source_stage_id)
        if source_status and application_status(event.application) != source_status:
            create_log(
                config_model=config_model,
                event=event,
                rule=trigger,
                rule_kind="trigger",
                status=CRMAutomationExecutionLog.STATUS_SKIPPED,
                message="Триггер смены статуса пропущен: заявка находится не на стадии этого триггера.",
            )
            return ""

    current_stage_id = status_stage_id(config, application_status(event.application))
    stage_ids = [stage.get("id") for stage in config.get("stages", []) if isinstance(stage, dict)]
    target_index = stage_ids.index(target_stage_id) if target_stage_id in stage_ids else -1
    current_index = stage_ids.index(current_stage_id) if current_stage_id in stage_ids else -1
    if target_index >= 0 and current_index >= 0 and target_index < current_index and not trigger.get("allowBackTransition", False):
        create_log(
            config_model=config_model,
            event=event,
            rule=trigger,
            rule_kind="trigger",
            status=CRMAutomationExecutionLog.STATUS_SKIPPED,
            message="Переход на предыдущую стадию запрещен настройкой триггера.",
        )
        return ""

    delayed, scheduled_for = should_delay(trigger)
    if delayed:
        create_log(
            config_model=config_model,
            event=event,
            rule=trigger,
            rule_kind="trigger",
            status=CRMAutomationExecutionLog.STATUS_PENDING,
            message="Запланировано отложенное выполнение триггера.",
            scheduled_for=scheduled_for,
        )
        return ""

    target_status = target_status_for_stage(config, target_stage_id)
    changed = update_application_status(event.application, target_status)
    if changed:
        event.application.refresh_from_db()
    create_log(
        config_model=config_model,
        event=event,
        rule=trigger,
        rule_kind="trigger",
        status=CRMAutomationExecutionLog.STATUS_SUCCESS,
        message=f"Триггер перевел заявку на стадию «{target_status}»." if changed else "Триггер обработан без изменения статуса.",
    )
    return target_stage_id


@transaction.atomic
def run_crm_automation(
    application: Application,
    event_code: str,
    *,
    previous_status: str = "",
    request=None,
) -> dict[str, int]:
    if not application.event_id:
        return {"events": 0, "changed": 0}

    Application.objects.select_for_update().get(pk=application.pk)
    application = Application.objects.select_related(
        "user", "event", "event__leader", "direction", "project", "specialization", "status"
    ).prefetch_related("event__organizers").get(pk=application.pk)

    config_model = get_or_create_config(application.event_id)
    config = config_model_to_dict(config_model)
    event = CRMAutomationEvent(
        code=event_code,
        application=application,
        previous_status=previous_status,
        event_id=application.event_id,
        fingerprint=stable_fingerprint(
            {
                "code": event_code,
                "application": application.id,
                "status": application_status(application),
                "previousStatus": previous_status,
            }
        ),
        request=request,
    )

    result = {"events": 1, "changed": 0}
    entered_stage_ids: set[str] = set()

    triggers = config.get("triggers") if isinstance(config.get("triggers"), list) else []
    for trigger in triggers:
        if not isinstance(trigger, dict) or not trigger.get("enabled", False) or trigger.get("deleted", False):
            continue
        if normalized_text(trigger.get("eventCode")) != event_code:
            continue
        stage_id = run_trigger(config_model, config, trigger, event)
        if stage_id:
            entered_stage_ids.add(stage_id)
            result["changed"] += 1

    current_stage_id = status_stage_id(config, application_status(event.application))
    if current_stage_id:
        entered_stage_ids.add(current_stage_id)

    for stage_id in entered_stage_ids:
        if run_stage_robots(config_model, config, event, stage_id):
            result["changed"] += 1

    return result


def execute_pending_log(log: CRMAutomationExecutionLog) -> bool:
    application = Application.objects.select_related(
        "user", "event", "event__leader", "direction", "project", "specialization", "status"
    ).prefetch_related("event__organizers").filter(pk=log.application_id).first()
    if not application:
        log.status = CRMAutomationExecutionLog.STATUS_SKIPPED
        log.message = "Заявка для отложенного правила не найдена."
        log.executed_at = timezone.now()
        log.save(update_fields=["status", "message", "executed_at"])
        return False

    config = config_model_to_dict(log.config)
    rules = config.get("robots" if log.rule_kind == "robot" else "triggers", [])
    rule = next(
        (item for item in rules if isinstance(item, dict) and normalized_text(item.get("id")) == log.rule_id),
        None,
    )
    if not rule:
        log.status = CRMAutomationExecutionLog.STATUS_FAILED
        log.message = "Правило для отложенного выполнения не найдено."
        log.executed_at = timezone.now()
        log.save(update_fields=["status", "message", "executed_at"])
        return False

    event = CRMAutomationEvent(
        code=log.event_code,
        application=application,
        previous_status=normalized_text(log.context.get("previousStatus")),
        event_id=log.event_id,
        fingerprint=stable_fingerprint({"pendingLog": log.pk}),
    )

    if not conditions_match(rule.get("settings"), event):
        log.status = CRMAutomationExecutionLog.STATUS_SKIPPED
        log.message = "Условия отложенного правила больше не выполнены."
        log.executed_at = timezone.now()
        log.save(update_fields=["status", "message", "executed_at"])
        return False

    changed = False
    if log.rule_kind == "trigger":
        source_stage_id = normalized_text(rule.get("stageId"))
        target_stage_id = source_stage_id
        if log.event_code == "request.status_changed":
            source_status = target_status_for_stage(config, source_stage_id)
            if source_status and application_status(application) != source_status:
                log.status = CRMAutomationExecutionLog.STATUS_SKIPPED
                log.message = "Отложенный триггер смены статуса пропущен: заявка находится не на стадии этого триггера."
                log.executed_at = timezone.now()
                log.save(update_fields=["status", "message", "executed_at"])
                return False

        changed = update_application_status(application, target_status_for_stage(config, target_stage_id))
        if changed:
            application.refresh_from_db()
            event.application = application
        run_stage_robots(log.config, config, event, target_stage_id)
    else:
        changed = run_robot_action(log.config, rule, event, force_immediate=True)

    log.status = CRMAutomationExecutionLog.STATUS_SUCCESS if changed else CRMAutomationExecutionLog.STATUS_SKIPPED
    log.message = "Отложенное правило выполнено." if changed else "Отложенное правило не внесло изменений."
    log.executed_at = timezone.now()
    log.save(update_fields=["status", "message", "executed_at"])
    return changed


def run_due_crm_automation() -> dict[str, int]:
    chat_membership_result = scan_chat_membership_for_sent_applications()
    logs = CRMAutomationExecutionLog.objects.filter(
        status=CRMAutomationExecutionLog.STATUS_PENDING,
        scheduled_for__lte=timezone.now(),
    ).select_related("config").order_by("scheduled_for", "id")
    result = {
        "processed": 0,
        "changed": 0,
        "chat_membership_scanned": chat_membership_result["scanned"],
        "chat_membership_changed": chat_membership_result["changed"],
    }
    for log in logs:
        result["processed"] += 1
        if execute_pending_log(log):
            result["changed"] += 1
    return result
