"""Общие проверки доступа для представлений users."""

from users.permissions import has_curator_or_admin_role, is_event_organizer
from users.models import Application


def _user_can_access_application(user, application: Application) -> bool:
    if application.user_id == user.id:
        return True
    if has_curator_or_admin_role(user):
        return True
    return is_event_organizer(user, application.event_id)
