"""Контекст события, условия правил и шаблоны сообщений."""

from typing import Any
from django.utils import timezone
from .utils import normalized_text
from .events import PlannerAutomationEvent
from .items import is_done_status, item_end_date, item_recipient_id, item_status, team_curator_id


def event_context(event: PlannerAutomationEvent) -> dict[str, Any]:
    item = event.item
    team = event.team or {}
    end_date = item_end_date(item)
    today = timezone.localdate()
    days_to_deadline = (end_date - today).days if end_date else None
    return {
        **item,
        "type": event.entity_type,
        "eventCode": event.code,
        "teamId": event.team_id,
        "eventId": event.event_id,
        "teamName": team.get("name", ""),
        "teamConfirmed": bool(team.get("confirmed", False)),
        "curatorId": team_curator_id(team),
        "assigneeId": item_recipient_id(item),
        "status": item_status(item),
        "task_status": item_status(item),
        "taskStatus": item_status(item),
        "title": item.get("title", ""),
        "task": item.get("title", ""),
        "task_type": event.entity_type,
        "taskType": event.entity_type,
        "team": team.get("name", "") or event.team_id,
        "curator": team_curator_id(team),
        "assignee": item_recipient_id(item),
        "deadline": end_date.isoformat() if end_date else "",
        "in_sprint": item.get("inSprint", item.get("in_sprint", "")),
        "inSprint": item.get("inSprint", item.get("in_sprint", "")),
        "daysToDeadline": days_to_deadline,
        "previousDeadline": (event.previous_item or {}).get("endDate", (event.previous_item or {}).get("end_date", "")),
        "deadlineChanged": bool(item.get("deadlineChanged", item.get("deadline_changed", False))),
        "memberId": item.get("memberId", item.get("member_id", "")),
        "activeTaskCount": item.get("activeTaskCount", item.get("active_task_count", "")),
        "inactiveDays": item.get("inactiveDays", item.get("inactive_days", "")),
        "isOverdue": days_to_deadline is not None and days_to_deadline < 0 and not is_done_status(item_status(item)),
    }


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


def conditions_match(settings: dict[str, Any] | None, event: PlannerAutomationEvent) -> bool:
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


def render_template(template: str, event: PlannerAutomationEvent) -> str:
    context = event_context(event)
    result = template or ""
    for key, value in context.items():
        result = result.replace("{" + key + "}", normalized_text(value))
    return result
