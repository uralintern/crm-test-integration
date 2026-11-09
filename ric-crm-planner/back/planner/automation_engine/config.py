"""Конфигурация автоматизации планировщика и стадии."""

from typing import Any
from planner.automation_defaults import create_default_planner_automation_config
from planner.models import PlannerAutomationConfig
from .utils import normalized_text


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
