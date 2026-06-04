from channels.db import database_sync_to_async
from channels.sessions import CookieMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


@database_sync_to_async
def _get_user_from_access_token(token: str | None):
    if not token:
        return AnonymousUser()

    authenticator = JWTAuthentication()
    try:
        validated_token = authenticator.get_validated_token(token)
        return authenticator.get_user(validated_token)
    except (InvalidToken, TokenError):
        return AnonymousUser()


class CookieJWTAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        cookies = scope.get("cookies") or {}
        scope["user"] = await _get_user_from_access_token(cookies.get("access_token"))
        return await self.inner(scope, receive, send)


def CookieJWTAuthMiddlewareStack(inner):
    return CookieMiddleware(CookieJWTAuthMiddleware(inner))
