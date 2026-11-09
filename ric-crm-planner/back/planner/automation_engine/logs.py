"""Журнал выполнения правил и отложенный запуск."""

from datetime import timedelta
from typing import Any
from django.utils import timezone
from planner.models import PlannerAutomationConfig, PlannerAutomationExecutionLog
from .utils import normalized_text, stable_fingerprint, to_int
from .events import PlannerAutomationEvent
from .conditions import event_context


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
