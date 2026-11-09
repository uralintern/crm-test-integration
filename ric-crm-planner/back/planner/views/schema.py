"""Swagger: теги и схемы ответов для представлений планировщика."""

from drf_yasg import openapi


TAG_PLANNER = "Planner"
ERROR_RESPONSE_SCHEMA = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    additional_properties=openapi.Schema(type=openapi.TYPE_STRING),
)
