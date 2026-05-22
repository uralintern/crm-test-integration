"""Convenience decorators for view-level CRM role checks."""

from functools import wraps

from rest_framework.exceptions import NotAuthenticated, PermissionDenied

from .models import CRMRole


def _extract_request(*args):
    """Return the request object from standard view call signatures."""

    if not args:
        return None

    first_arg = args[0]
    if hasattr(first_arg, "user"):
        return first_arg

    if len(args) > 1 and hasattr(args[1], "user"):
        return args[1]

    return None


def role_required(*role_types: str):
    """Ensure the current user has at least one of the given CRM roles.

    The decorator can be used on both function-based and method-based views.
    It will raise a DRF ``NotAuthenticated`` error if the user is anonymous
    and ``PermissionDenied`` if the user lacks the required CRM role.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(*args, **kwargs):
            request = _extract_request(*args)
            if request is None:
                raise PermissionDenied("Request object is required for role checks")

            user = getattr(request, "user", None)
            if not user or not user.is_authenticated:
                raise NotAuthenticated()

            # Суперпользователь должен проходить без проверки CRM ролей.
            if user.is_superuser:
                return view_func(*args, **kwargs)

            if not role_types:
                raise PermissionDenied("No role types provided for role check")

            has_role = CRMRole.objects.filter(user=user, role_type__in=role_types).exists()
            if not has_role:
                raise PermissionDenied("Недостаточно прав для доступа")

            return view_func(*args, **kwargs)

        return _wrapped

    return decorator
