"""Журнал выполнения правил и отложенный запуск."""

from datetime import timedelta
from typing import Any
from django.utils import timezone
from users.models import CRMAutomationConfig, CRMAutomationExecutionLog
from .utils import normalized_text, stable_fingerprint, to_int
from .events import CRMAutomationEvent
from .conditions import application_status, event_context


def should_delay(rule: dict[str, Any]) -> tuple[bool, Any]:
    settings = rule.get("settings") if isinstance(rule.get("settings"), dict) else {}
    delay_minutes = to_int(settings.get("delayMinutes")) or 0
    if settings.get("timing") == "delayed" and delay_minutes > 0:
        return True, timezone.now() + timedelta(minutes=delay_minutes)
    return False, None


def rule_run_key(config_model: CRMAutomationConfig, event: CRMAutomationEvent, rule: dict[str, Any], rule_kind: str) -> str:
    rule_id = normalized_text(rule.get("id")) or normalized_text(rule.get("action") or rule.get("eventCode"))
    event_code = event.code if rule_kind == "trigger" else f"stage:{application_status(event.application)}"
    fingerprint = (
        event.fingerprint
        if rule_kind == "trigger"
        else stable_fingerprint(
            {
                "application": event.application.id,
                "status": application_status(event.application),
                "previousStatus": event.previous_status,
            }
        )
    )
    return stable_fingerprint(
        {
            "config": config_model.pk,
            "rule": rule_id,
            "kind": rule_kind,
            "event": event_code,
            "entityId": event.application.id,
            "fingerprint": fingerprint,
        }
    )


def create_log(
    *,
    config_model: CRMAutomationConfig,
    event: CRMAutomationEvent,
    rule: dict[str, Any],
    rule_kind: str,
    status: str,
    message: str = "",
    scheduled_for=None,
) -> CRMAutomationExecutionLog:
    rule_id = normalized_text(rule.get("id")) or normalized_text(rule.get("action") or rule.get("eventCode"))
    log, _ = CRMAutomationExecutionLog.objects.update_or_create(
        run_key=rule_run_key(config_model, event, rule, rule_kind),
        defaults={
            "config": config_model,
            "application": event.application,
            "event_id": event.event_id,
            "entity_type": "application",
            "entity_id": str(event.application.id),
            "event_code": event.code,
            "rule_kind": rule_kind,
            "rule_id": rule_id,
            "status": status,
            "message": message,
            "context": event_context(event),
            "scheduled_for": scheduled_for,
            "executed_at": timezone.now() if status != CRMAutomationExecutionLog.STATUS_PENDING else None,
        },
    )
    return log


def log_exists(config_model: CRMAutomationConfig, event: CRMAutomationEvent, rule: dict[str, Any], rule_kind: str) -> bool:
    return CRMAutomationExecutionLog.objects.filter(
        run_key=rule_run_key(config_model, event, rule, rule_kind),
        status__in=[
            CRMAutomationExecutionLog.STATUS_PENDING,
            CRMAutomationExecutionLog.STATUS_SUCCESS,
        ],
    ).exists()
