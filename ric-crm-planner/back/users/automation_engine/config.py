"""Конфигурация автоматизации мероприятия: нормализация, стадии, целевые статусы."""

from copy import deepcopy
from typing import Any
from users.automation_defaults import create_default_crm_automation_config
from users.models import CRMAutomationConfig
from .utils import normalized_text, to_int


CHAT_LINK_ROBOT_IDS = {"crm-send-chat-link", "request-send-chat-link"}
CHAT_LINK_TRIGGER_IDS = {"crm-chat-link-opened", "request-chat-link-opened"}


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
