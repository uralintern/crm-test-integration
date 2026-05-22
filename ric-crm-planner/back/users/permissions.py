"""Reusable role-based permission classes.

This module centralizes checks for CRM roles and their capability flags so
endpoints can declare the required role or capability via DRF permissions.
"""

import secrets

from django.conf import settings
from django.db.models import Q
from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import CRMRole, Direction, Event, Project, ROLE_ADMIN, ROLE_CURATOR, ROLE_PROJECTANT


def has_curator_or_admin_role(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    return CRMRole.objects.filter(user=user, role_type__in=(ROLE_CURATOR, ROLE_ADMIN)).exists()


def is_event_organizer(user, event_id) -> bool:
    if not user or not user.is_authenticated or not event_id:
        return False
    return Event.objects.filter(pk=event_id).filter(Q(leader=user) | Q(organizers=user)).exists()


def resolve_event_id_from_request(request, view):
    kwargs = getattr(view, "kwargs", {}) or {}
    if kwargs.get("event_id"):
        return kwargs.get("event_id")

    if kwargs.get("direction_id"):
        return Direction.objects.filter(pk=kwargs.get("direction_id")).values_list("event_id", flat=True).first()

    if kwargs.get("project_id"):
        return Project.objects.filter(pk=kwargs.get("project_id")).values_list("direction__event_id", flat=True).first()

    data = getattr(request, "data", {}) or {}
    if isinstance(data, dict):
        event_id = data.get("event") or data.get("event_id")
        if event_id:
            return event_id

        direction_id = data.get("direction") or data.get("direction_id")
        if direction_id:
            return Direction.objects.filter(pk=direction_id).values_list("event_id", flat=True).first()

        project_id = data.get("project") or data.get("project_id")
        if project_id:
            return Project.objects.filter(pk=project_id).values_list("direction__event_id", flat=True).first()

    return None


class RolePermission(BasePermission):
    """Base permission that checks roles for read and write actions."""

    safe_roles: tuple[str, ...] = ()
    write_roles: tuple[str, ...] = ()

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False

        if user.is_superuser or user.is_staff:
            return True

        allowed_roles = self.safe_roles if request.method in SAFE_METHODS else self.write_roles
        if not allowed_roles:
            return False

        return CRMRole.objects.filter(user=user, role_type__in=allowed_roles).exists()


class AdminOnlyPermission(RolePermission):
    """Allow access to users with the admin CRM role."""

    safe_roles = write_roles = (ROLE_ADMIN,)


class CuratorOnlyPermission(RolePermission):
    """Allow access to users with the curator CRM role."""

    safe_roles = write_roles = (ROLE_CURATOR,)


class ProjectantOnlyPermission(RolePermission):
    """Allow access to users with the projectant CRM role."""

    safe_roles = write_roles = (ROLE_PROJECTANT,)


class CuratorOrAdminPermission(RolePermission):
    """Allow access to users who are curators or admins."""

    safe_roles = write_roles = (ROLE_CURATOR, ROLE_ADMIN)

    def has_permission(self, request, view):
        if super().has_permission(request, view):
            return True

        user = getattr(request, "user", None)
        return is_event_organizer(user, resolve_event_id_from_request(request, view))


class ProjectantReadCuratorAdminWritePermission(RolePermission):
    """Allow projectants to read and curators/admins to manage resources."""

    safe_roles = (ROLE_PROJECTANT, ROLE_CURATOR, ROLE_ADMIN)
    write_roles = (ROLE_CURATOR, ROLE_ADMIN)


class PublicReadCuratorAdminWritePermission(BasePermission):
    """Allow anonymous read access and curator/admin write access."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True

        return CuratorOrAdminPermission().has_permission(request, view)


class TestingServicePermission(BasePermission):
    """Allow access for the external testing service via shared token."""

    message = "Invalid testing service token."

    def has_permission(self, request, view):
        expected_token = getattr(settings, "TESTING_SERVICE_TOKEN", "") or ""
        if not expected_token:
            return False

        header_token = request.headers.get("X-Service-Token", "") or ""
        auth_header = request.headers.get("Authorization", "") or ""

        bearer_token = ""
        if auth_header.lower().startswith("bearer "):
            bearer_token = auth_header[7:].strip()

        provided_token = header_token or bearer_token
        if not provided_token:
            return False

        return secrets.compare_digest(provided_token, expected_token)
