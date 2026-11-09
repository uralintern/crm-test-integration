"""Swagger: теги, схемы ответов и общие параметры для представлений users."""

from drf_yasg import openapi


TAG_AUTH = "Auth"
TAG_USERS = "Users"
TAG_PROFILE = "Profile"
TAG_EVENTS = "Events"
TAG_DIRECTIONS = "Directions"
TAG_PROJECTS = "Projects"
TAG_APPLICATIONS = "Applications"
TAG_NOTIFICATIONS = "Уведомления"
TAG_REFERENCE = "Reference"
TAG_INTEGRATION = "Integration"
MESSAGE_RESPONSE_SCHEMA = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={"message": openapi.Schema(type=openapi.TYPE_STRING)},
)
ERROR_RESPONSE_SCHEMA = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    additional_properties=openapi.Schema(type=openapi.TYPE_STRING),
)
LOGIN_RESPONSE_SCHEMA = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={"user": openapi.Schema(type=openapi.TYPE_OBJECT)},
)
REFRESH_RESPONSE_SCHEMA = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "access": openapi.Schema(type=openapi.TYPE_STRING),
        "refresh": openapi.Schema(type=openapi.TYPE_STRING),
    },
)
INTEGRATION_TOKEN_PARAMETER = openapi.Parameter(
    "X-Service-Token",
    openapi.IN_HEADER,
    description="Shared token for CRM and testing service integration.",
    type=openapi.TYPE_STRING,
    required=True,
)
