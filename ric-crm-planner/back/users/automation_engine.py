import hashlib
import json
from dataclasses import dataclass
from copy import deepcopy
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from integrations.vk.crm_notifications import (
    CHAT_LINK_PLACEHOLDER,
    inject_application_chat_link,
    mark_application_joined_chat_if_member,
    notify_organizers_about_vk_error,
    scan_chat_membership_for_sent_applications,
    send_application_vk_message,
    upload_application_vk_documents,
)
from integrations.vk.planner_invites import send_planner_invite, send_start_message
from integrations.vk.services import VKAPIError, VKConfigurationError
from users.automation_defaults import create_default_crm_automation_config
from users.models import Application, CRMAutomationAttachment, CRMAutomationConfig, CRMAutomationExecutionLog, Event, Notification, Status


@dataclass
class CRMAutomationEvent:
    code: str
    application: Application
    previous_status: str
    event_id: int
    fingerprint: str
    request: Any = None


CHAT_LINK_ROBOT_IDS = {"crm-send-chat-link", "request-send-chat-link"}
CHAT_LINK_TRIGGER_IDS = {"crm-chat-link-opened", "request-chat-link-opened"}


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


def stable_fingerprint(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def normalize_crm_automation_config_dict(config: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(config)
    defaults = create_default_crm_automation_config(to_int(normalized.get("eventId")) or 0)

    for key in ("stages", "triggers", "robots"):
        items = normalized.get(key) if isinstance(normalized.get(key), list) else []
        default_items = defaults.get(key) if isinstance(defaults.get(key), list) else []
        existing_ids = {
            normalized_text(item.get("id"))
            for item in items
            if isinstance(item, dict) and normalized_text(item.get("id"))
        }
        for default_item in default_items:
            default_id = normalized_text(default_item.get("id")) if isinstance(default_item, dict) else ""
            if default_id and default_id not in existing_ids:
                items.append(deepcopy(default_item))
        normalized[key] = items

    robots = normalized.get("robots") if isinstance(normalized.get("robots"), list) else []
    for robot in robots:
        if not isinstance(robot, dict):
            continue
        robot_id = normalized_text(robot.get("id"))
        action = normalized_text(robot.get("action"))
        stage_id = normalized_text(robot.get("stageId"))

        if robot_id in CHAT_LINK_ROBOT_IDS or (action == "chat.link.vk" and stage_id == "application-joined-chat"):
            robot["stageId"] = "application-chat-link-sent"
        if robot_id == "crm-send-planner-invite":
            robot["stageId"] = "application-enrollment-closed"
            robot["enabled"] = True

    triggers = normalized.get("triggers") if isinstance(normalized.get("triggers"), list) else []
    for trigger in triggers:
        if not isinstance(trigger, dict):
            continue
        trigger_id = normalized_text(trigger.get("id"))
        event_code = normalized_text(trigger.get("eventCode"))

        if trigger_id in CHAT_LINK_TRIGGER_IDS or event_code == "notification.chat_link_opened":
            trigger["stageId"] = "application-joined-chat"
            trigger["targetStageId"] = "application-joined-chat"
        if trigger_id == "crm-enrollment-closed" or event_code == "enrollment.closed":
            trigger["stageId"] = "application-enrollment-closed"
            trigger["targetStageId"] = "application-enrollment-closed"

    return normalized


def config_model_to_dict(config_model: CRMAutomationConfig) -> dict[str, Any]:
    if not config_model.stages and not config_model.triggers and not config_model.robots:
        return create_default_crm_automation_config(config_model.event_id)
    return normalize_crm_automation_config_dict({
        "scope": config_model.scope,
        "eventId": config_model.event_id,
        "updatedAt": config_model.updated_at.isoformat(),
        "stages": config_model.stages,
        "triggers": config_model.triggers,
        "robots": config_model.robots,
    })


def get_or_create_config(event_id: int) -> CRMAutomationConfig:
    defaults = create_default_crm_automation_config(event_id)
    config, _ = CRMAutomationConfig.objects.get_or_create(
        scope=CRMAutomationConfig.SCOPE_CRM,
        event_id=event_id,
        defaults={
            "stages": defaults["stages"],
            "triggers": defaults["triggers"],
            "robots": defaults["robots"],
        },
    )
    return config


def stage_by_id(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        normalized_text(stage.get("id")): stage
        for stage in config.get("stages", [])
        if isinstance(stage, dict) and normalized_text(stage.get("id"))
    }


def status_stage_id(config: dict[str, Any], status_name: str) -> str:
    normalized_status = normalized_text(status_name)
    for stage in config.get("stages", []):
        if isinstance(stage, dict) and normalized_text(stage.get("title")) == normalized_status:
            return normalized_text(stage.get("id"))
    return ""


def target_status_for_stage(config: dict[str, Any], stage_id: str) -> str:
    stage = stage_by_id(config).get(stage_id)
    if stage and normalized_text(stage.get("title")):
        return normalized_text(stage.get("title"))
    fallback = {
        "application-submitted": "Прислал заявку",
        "application-testing": "Прохождение тестирования",
        "application-chat-link-sent": "Отправлена ссылка на орг. чат",
        "application-joined-chat": "Добавился в орг. чат",
        "application-enrollment-closed": "Набор завершён",
        "application-started": "Приступил к ПШ",
    }
    return fallback.get(stage_id, "")


def application_status(application: Application) -> str:
    return application.status.name if application.status_id else ""


def application_display_name(application: Application) -> str:
    display_name = f"{application.user.last_name or ''} {application.user.first_name or ''}".strip()
    return display_name or application.user.get_full_name() or application.user.email or str(application.user)


def user_display_name(user) -> str:
    if not user:
        return ""
    display_name = f"{user.last_name or ''} {user.first_name or ''}".strip()
    return display_name or user.get_full_name() or user.email or str(user)


def application_profile(application: Application):
    try:
        return application.user.crm_profile
    except Exception:
        return None


def latest_test_result(application: Application):
    current_session_id = normalized_text(application.test_session_id)
    if current_session_id:
        result = (
            application.test_results.select_related("session")
            .filter(session__session_id=current_session_id)
            .order_by("-completed_at", "-id")
            .first()
        )
        if result:
            return result
    return application.test_results.order_by("-completed_at", "-id").first()


def event_context(event: CRMAutomationEvent) -> dict[str, Any]:
    application = event.application
    crm_event = application.event
    profile = application_profile(application)
    custom_fields = application.custom_fields if isinstance(application.custom_fields, dict) else {}
    responsible = crm_event.leader if crm_event else None
    test_result = latest_test_result(application)
    test_score = test_result.score if test_result else ""
    test_max_score = test_result.max_score if test_result else ""
    test_percentage = float(test_result.percentage) if test_result else ""
    test_passed = test_result.is_passed if test_result else ""
    test_result_status = test_result.result_status if test_result else ""
    context = {
        "id": application.id,
        "applicationId": application.id,
        "eventCode": event.code,
        "eventId": application.event_id,
        "event": crm_event.name if crm_event else "",
        "student": application_display_name(application),
        "ownerId": application.user_id,
        "status": application_status(application),
        "previousStatus": event.previous_status,
        "direction": application.direction.name if application.direction_id else "",
        "directionId": application.direction_id,
        "project": application.project.name if application.project_id else "",
        "projectId": application.project_id,
        "specialization": application.specialization.name if application.specialization_id else "",
        "university": getattr(profile, "university", "") if profile else "",
        "course": getattr(profile, "course", "") if profile else "",
        "vk": getattr(profile, "vk", "") if profile else "",
        "application_date": application.date_sub.isoformat() if application.date_sub else "",
        "applicationDate": application.date_sub.isoformat() if application.date_sub else "",
        "responsible": user_display_name(responsible),
        "responsibleId": responsible.id if responsible else "",
        "message": application.message,
        "comment": application.comment,
        "testsAssigned": application.tests_assigned,
        "isApproved": application.is_approved,
        "testing_result": test_score,
        "testingResult": test_score,
        "test_score": test_score,
        "testScore": test_score,
        "max_score": test_max_score,
        "maxScore": test_max_score,
        "testing_percentage": test_percentage,
        "testingPercentage": test_percentage,
        "test_passed": test_passed,
        "testPassed": test_passed,
        "result_status": test_result_status,
        "resultStatus": test_result_status,
    }
    for key, value in custom_fields.items():
        normalized_key = normalized_text(key)
        if normalized_key and normalized_key not in context:
            context[normalized_key] = value
    return context


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


def conditions_match(settings: dict[str, Any] | None, event: CRMAutomationEvent) -> bool:
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


def render_template(template: str, event: CRMAutomationEvent) -> str:
    context = event_context(event)
    result = template or ""
    for key, value in context.items():
        result = result.replace("{" + key + "}", normalized_text(value))
    return result


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


def get_application_organizers(application: Application):
    if not application.event_id:
        return []
    recipients = list(application.event.organizers.all())
    if application.event.leader_id and all(recipient.id != application.event.leader_id for recipient in recipients):
        recipients.append(application.event.leader)
    return [recipient for recipient in recipients if recipient]


def create_notification(user_id: int | None, title: str, message: str, link: str = "/requests") -> bool:
    if not user_id:
        return False
    Notification.objects.create(user_id=user_id, title=title[:255], message=message, link=link)
    return True


def create_organizer_notifications(application: Application, title: str, message: str) -> int:
    created = 0
    for organizer in get_application_organizers(application):
        Notification.objects.create(user=organizer, title=title[:255], message=message, link="/requests")
        created += 1
    return created


def update_application_status(application: Application, status_name: str) -> bool:
    if not status_name or application_status(application) == status_name:
        return False
    status_obj, _ = Status.objects.get_or_create(name=status_name, defaults={"description": "", "is_positive": True})
    application.status = status_obj
    application.save(update_fields=["status"])
    return True

def robot_attachment_ids(robot: dict[str, Any]) -> list[int]:
    raw_attachments = robot.get("attachments") if isinstance(robot.get("attachments"), list) else []
    ids: list[int] = []
    for attachment in raw_attachments:
        if isinstance(attachment, dict):
            attachment_id = to_int(attachment.get("id"))
        else:
            attachment_id = to_int(attachment)
        if attachment_id and attachment_id not in ids:
            ids.append(attachment_id)
    return ids


def get_robot_attachments(robot: dict[str, Any], event_id: int):
    ids = robot_attachment_ids(robot)
    if not ids:
        return []
    attachments_by_id = {
        attachment.id: attachment
        for attachment in CRMAutomationAttachment.objects.filter(event_id=event_id, id__in=ids)
    }
    return [attachments_by_id[attachment_id] for attachment_id in ids if attachment_id in attachments_by_id]

def run_robot_action(
    config_model: CRMAutomationConfig,
    robot: dict[str, Any],
    event: CRMAutomationEvent,
    *,
    force_immediate: bool = False,
) -> bool:
    if log_exists(config_model, event, robot, "robot") and not force_immediate:
        return False

    if not force_immediate:
        delayed, scheduled_for = should_delay(robot)
        if delayed:
            create_log(
                config_model=config_model,
                event=event,
                rule=robot,
                rule_kind="robot",
                status=CRMAutomationExecutionLog.STATUS_PENDING,
                message="Запланировано отложенное выполнение робота.",
                scheduled_for=scheduled_for,
            )
            return False

    action = normalized_text(robot.get("action"))
    if action == "message.vk_interactive":
        action = "message.vk"
    title = render_template(robot.get("subject") or robot.get("title", ""), event) or "Уведомление"
    message = render_template(robot.get("message") or robot.get("description", ""), event)
    success = False
    log_message = ""

    if action in {"notification.organizer", "notification.curator"}:
        success = create_organizer_notifications(event.application, title, message) > 0
        log_message = "Уведомления отправлены организаторам." if success else "Организаторы не найдены."
    elif action in {"notification.user", "notification.assignee", "testing.link"}:
        notification_link = f"/testing?applicationId={event.application.id}" if action == "testing.link" else "/requests"
        success = create_notification(event.application.user_id, title, message, link=notification_link)
        log_message = "Уведомление отправлено проектанту." if success else "Проектант не найден."
    elif action == "file.vk":
        try:
            documents = get_robot_attachments(robot, event.event_id)
            if not documents:
                log_message = "Файлы для VK-робота не выбраны."
            else:
                vk_attachments = upload_application_vk_documents(event.application, documents)
                print(f"VK file robot attachments: application_id={event.application.id} attachments={vk_attachments}")
                send_application_vk_message(
                    event.application,
                    message or "Вам отправлены файлы по заявке.",
                    attachments=vk_attachments,
                )
                success = True
                log_message = "VK-файлы отправлены проектанту."
        except (VKConfigurationError, VKAPIError, ValueError) as exc:
            notify_organizers_about_vk_error(event.application, str(exc))
            log_message = str(exc)
    elif action == "planner.invite.vk":
        try:
            send_planner_invite(event.application, message=message)
            success = True
            log_message = "VK-приглашение в планировщик отправлено проектанту."
        except (VKConfigurationError, VKAPIError, ValueError) as exc:
            notify_organizers_about_vk_error(event.application, str(exc))
            log_message = str(exc)
    elif action == "planner.start.vk":
        try:
            send_start_message(event.application, message=message)
            success = True
            log_message = "VK-Сообщение Старта"
        except (VKConfigurationError, VKAPIError, ValueError) as exc:
            log_message = str(exc)
    elif action == "status.change":
        target_stage_id = normalized_text(robot.get("targetStageId"))
        target_status = normalized_text(robot.get("targetStatus")) or target_status_for_stage(
            config_model_to_dict(config_model),
            target_stage_id,
        )
        success = update_application_status(event.application, target_status)
        if success:
            event.application.refresh_from_db()
        log_message = (
            f"Заявка переведена в статус «{target_status}»."
            if success
            else "Статус заявки не изменился."
        )
    elif action in {"message.vk", "chat.link.vk", "message.vk_or_notification"}:
        try:
            if action == "chat.link.vk" and mark_application_joined_chat_if_member(event.application):
                event.application.refresh_from_db()
                success = True
                log_message = "Проектант уже состоит в орг. чате, отправка ссылки пропущена."
            else:
                vk_message = message
                if action in {"chat.link.vk", "message.vk_or_notification"} or CHAT_LINK_PLACEHOLDER in vk_message:
                    vk_message = inject_application_chat_link(vk_message, event.application, event.request)
                send_application_vk_message(event.application, vk_message)
                success = True
                log_message = "VK-сообщение отправлено проектанту."
        except (VKConfigurationError, VKAPIError, ValueError) as exc:
            notify_organizers_about_vk_error(event.application, str(exc))
            log_message = str(exc)
    else:
        log_message = f"Действие робота {action} пока не поддерживается."

    if not force_immediate:
        create_log(
            config_model=config_model,
            event=event,
            rule=robot,
            rule_kind="robot",
            status=CRMAutomationExecutionLog.STATUS_SUCCESS if success else CRMAutomationExecutionLog.STATUS_SKIPPED,
            message=log_message,
        )
    return success


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
