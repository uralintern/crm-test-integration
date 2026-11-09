"""Контекст события, условия правил и шаблоны сообщений."""

from typing import Any
from users.models import Application
from .utils import normalized_text
from .events import CRMAutomationEvent


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
