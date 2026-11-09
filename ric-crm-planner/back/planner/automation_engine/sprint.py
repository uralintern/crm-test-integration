"""Еженедельная очистка спринта от выполненных подзадач."""

from datetime import timedelta, timezone as dt_timezone
from typing import Any
from django.conf import settings as django_settings
from django.db import transaction
from django.utils import timezone
from planner.automation_defaults import create_default_planner_automation_config
from planner.models import PlannerAutomationExecutionLog, PlannerWorkspaceState, TeamPlannerDesk
from planner.realtime import broadcast_team_desk_update
from .constants import (
    DEFAULT_SPRINT_WEEK_UTC_OFFSET_HOURS,
    SPRINT_SWEEP_EVENT_CODE,
    SPRINT_SWEEP_ROBOT_ID,
)
from .utils import normalized_text, stable_fingerprint, to_int
from .events import PlannerAutomationEvent
from .items import (
    is_done_status,
    is_in_sprint,
    item_id,
    item_status,
    item_team_id,
    set_in_sprint,
    team_by_id,
    team_event_id,
)
from .config import config_model_to_dict, get_or_create_config
from .conditions import conditions_match
from .logs import create_log, log_exists
from .runner import workspace_state_dict


def sprint_week_timezone() -> dt_timezone:
    offset_hours = getattr(django_settings, "PLANNER_SPRINT_WEEK_UTC_OFFSET_HOURS", None)
    if not isinstance(offset_hours, int) or abs(offset_hours) > 14:
        offset_hours = DEFAULT_SPRINT_WEEK_UTC_OFFSET_HOURS
    return dt_timezone(timedelta(hours=offset_hours))


def sprint_week_key(now=None) -> str:
    local_now = (now or timezone.now()).astimezone(sprint_week_timezone())
    iso_year, iso_week, _ = local_now.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def find_sprint_sweep_robot(config: dict[str, Any]) -> dict[str, Any] | None:
    robots = config.get("robots") if isinstance(config.get("robots"), list) else []
    for robot in robots:
        if isinstance(robot, dict) and normalized_text(robot.get("id")) == SPRINT_SWEEP_ROBOT_ID:
            return robot

    for robot in create_default_planner_automation_config(to_int(config.get("eventId")) or 0).get("robots", []):
        if normalized_text(robot.get("id")) == SPRINT_SWEEP_ROBOT_ID:
            return robot
    return None


def sprint_sweep_event(
    event_id: int,
    week_key: str,
    *,
    item: dict[str, Any] | None = None,
    team: dict[str, Any] | None = None,
) -> PlannerAutomationEvent:
    if item is None:
        return PlannerAutomationEvent(
            code=SPRINT_SWEEP_EVENT_CODE,
            entity_type="sprint",
            entity_id=str(event_id),
            item={},
            previous_item=None,
            team=None,
            event_id=event_id,
            team_id=None,
            fingerprint=stable_fingerprint({"week": week_key}),
        )

    return PlannerAutomationEvent(
        code=SPRINT_SWEEP_EVENT_CODE,
        entity_type="subtask",
        entity_id=item_id(item),
        item=item,
        previous_item=None,
        team=team,
        event_id=event_id,
        team_id=item_team_id(item),
        fingerprint=stable_fingerprint({"week": week_key, "entity": item_id(item)}),
    )


def sync_desks_in_sprint_flags(cleared_ids_by_team: dict[int, set[str]]) -> None:
    for desk in TeamPlannerDesk.objects.filter(team_id__in=list(cleared_ids_by_team.keys())):
        cleared_ids = cleared_ids_by_team.get(desk.team_id, set())
        desk_subtasks = desk.subtasks if isinstance(desk.subtasks, list) else []
        desk_changed = False
        for subtask in desk_subtasks:
            if isinstance(subtask, dict) and item_id(subtask) in cleared_ids and is_in_sprint(subtask):
                set_in_sprint(subtask, False)
                desk_changed = True
        if desk_changed:
            desk.subtasks = desk_subtasks
            desk.save(update_fields=["subtasks", "updated_at"])
            broadcast_team_desk_update(desk)


def sweep_done_subtasks_from_sprint(now=None) -> dict[str, int]:
    workspace = PlannerWorkspaceState.objects.order_by("id").first()
    if not workspace:
        return {"events": 0, "changed": 0}

    teams = team_by_id(workspace_state_dict(workspace).get("teams"))
    week_key = sprint_week_key(now)
    subtasks = workspace.subtasks if isinstance(workspace.subtasks, list) else []

    done_by_event: dict[int, list[dict[str, Any]]] = {}
    for subtask in subtasks:
        if not isinstance(subtask, dict) or not is_in_sprint(subtask):
            continue
        if not is_done_status(item_status(subtask)):
            continue
        team = teams.get(item_team_id(subtask) or -1)
        event_id = team_event_id(team)
        if event_id is not None:
            done_by_event.setdefault(event_id, []).append(subtask)

    event_ids = {
        event_id
        for event_id in (team_event_id(team) for team in teams.values())
        if event_id is not None
    }

    result = {"events": 0, "changed": 0}
    cleared_ids_by_team: dict[int, set[str]] = {}

    with transaction.atomic():
        for event_id in sorted(event_ids):
            config_model = get_or_create_config(event_id)
            robot = find_sprint_sweep_robot(config_model_to_dict(config_model))
            if robot is None:
                continue

            marker = sprint_sweep_event(event_id, week_key)
            if log_exists(config_model, marker, robot, "robot"):
                continue

            result["events"] += 1
            log_status = PlannerAutomationExecutionLog.STATUS_SUCCESS

            if not PlannerAutomationExecutionLog.objects.filter(
                config=config_model, rule_id=SPRINT_SWEEP_ROBOT_ID
            ).exists():
                message = "Первый запуск: текущая неделя взята за точку отсчета, задачи не тронуты."
                log_status = PlannerAutomationExecutionLog.STATUS_SKIPPED
            elif not robot.get("enabled", False) or robot.get("deleted", False):
                message = "Робот выключен."
                log_status = PlannerAutomationExecutionLog.STATUS_SKIPPED
            else:
                cleared = 0
                for subtask in done_by_event.get(event_id, []):
                    team = teams.get(item_team_id(subtask) or -1)
                    if not conditions_match(robot.get("settings"), sprint_sweep_event(event_id, week_key, item=subtask, team=team)):
                        continue
                    set_in_sprint(subtask, False)
                    cleared += 1
                    team_id = item_team_id(subtask)
                    if team_id is not None:
                        cleared_ids_by_team.setdefault(team_id, set()).add(item_id(subtask))

                result["changed"] += cleared
                message = f"Из спринта убрано готовых задач: {cleared}."

            create_log(
                config_model=config_model,
                event=marker,
                rule=robot,
                rule_kind="robot",
                status=log_status,
                message=message,
            )

        if result["changed"]:
            workspace.subtasks = subtasks
            workspace.save(update_fields=["subtasks", "updated_at"])
            sync_desks_in_sprint_flags(cleared_ids_by_team)

    return result
