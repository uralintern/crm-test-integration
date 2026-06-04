"""
ASGI config for api project.
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.settings")

django_asgi_app = get_asgi_application()

from planner.routing import websocket_urlpatterns  # noqa: E402
from users.ws_auth import CookieJWTAuthMiddlewareStack  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": CookieJWTAuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
