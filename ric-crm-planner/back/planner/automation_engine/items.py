"""Чтение полей задач и команд из JSON планировщика."""

from typing import Any
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from .constants import DONE_STATUSES, REVIEW_STATUSES, STARTED_STATUSES
from .utils import lower_text, normalized_text, to_int


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


def is_in_sprint(item: dict[str, Any]) -> bool:
    return bool(item.get("inSprint", item.get("in_sprint", False)))


def set_in_sprint(item: dict[str, Any], value: bool) -> None:
    item["inSprint"] = value
    if "in_sprint" in item:
        item["in_sprint"] = value


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


def _member_ids_from_team_like(team: dict[str, Any]) -> list[int]:
    member_ids = team.get("memberIds", team.get("member_ids", []))
    if not isinstance(member_ids, list):
        return []
    return [member_id for member_id in (to_int(value) for value in member_ids) if member_id is not None]
