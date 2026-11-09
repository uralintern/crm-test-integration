"""Определение событий по изменению состояния планировщика."""

from typing import Any
from django.utils import timezone
from .constants import OVERLOADED_ACTIVE_TASK_LIMIT, STALE_TASK_DAYS
from .utils import normalized_text, stable_fingerprint, to_int
from .events import PlannerAutomationEvent
from .items import (
    is_active_task,
    is_done_status,
    is_review_status,
    is_started_status,
    item_assignee_id,
    item_end_date,
    item_id,
    item_status,
    item_team_id,
    item_updated_at,
    list_by_id,
    _member_ids_from_team_like,
    team_by_id,
    team_curator_id,
    team_event_id,
)


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
