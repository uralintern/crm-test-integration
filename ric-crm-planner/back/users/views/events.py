"""Мероприятия, экспорт, справочники статусов и специализаций."""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from users.permissions import (
    PublicReadCuratorAdminWritePermission,
    has_curator_or_admin_role,
    is_event_organizer,
)
from users.serializers import EventSerializer, SpecializationSerializer, StatusSerializer
from users.models import Event, Specialization, Status
from users.exporters import build_event_applications_xlsx_response, build_event_details_docx_response
from .schema import ERROR_RESPONSE_SCHEMA, TAG_EVENTS, TAG_REFERENCE


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_EVENTS],
        operation_summary="List events",
        operation_description="List events",
        responses={200: EventSerializer(many=True), 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        tags=[TAG_EVENTS],
        operation_summary="Create event",
        operation_description="Create event",
        request_body=EventSerializer,
        responses={201: EventSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA},
    ),
)
class EventListCreateView(ListCreateAPIView):
    permission_classes = (PublicReadCuratorAdminWritePermission,)
    serializer_class = EventSerializer
    queryset = Event.objects.all().select_related("leader", "specialization").prefetch_related("organizers")
    lookup_url_kwarg = "event_id"

    def get_queryset(self):
        archived = str(self.request.query_params.get("archived", "")).lower() in ("1", "true", "yes")
        return self.queryset.filter(is_archived=archived)


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_EVENTS],
        operation_summary="Get event",
        operation_description="Get event",
        responses={200: EventSerializer, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="put",
    decorator=swagger_auto_schema(
        tags=[TAG_EVENTS],
        operation_summary="Replace event",
        operation_description="Replace event",
        request_body=EventSerializer,
        responses={200: EventSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="patch",
    decorator=swagger_auto_schema(
        tags=[TAG_EVENTS],
        operation_summary="Update event",
        operation_description="Update event",
        request_body=EventSerializer,
        responses={200: EventSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="delete",
    decorator=swagger_auto_schema(
        tags=[TAG_EVENTS],
        operation_summary="Delete event",
        operation_description="Delete event",
        responses={204: "No content", 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
class EventDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = (PublicReadCuratorAdminWritePermission,)
    serializer_class = EventSerializer
    queryset = Event.objects.all().select_related("leader", "specialization").prefetch_related("organizers")
    lookup_url_kwarg = "event_id"

    def destroy(self, request, *args, **kwargs):
        if not has_curator_or_admin_role(request.user):
            return Response(
                {"detail": "Архивировать мероприятие может только главный организатор."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        instance.is_archived = True
        instance.archived_at = timezone.now()
        instance.save(update_fields=("is_archived", "archived_at"))


def _can_export_event(user, event_id: int) -> bool:
    return has_curator_or_admin_role(user) or is_event_organizer(user, event_id)


class EventDetailsExportView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, event_id: int, *args, **kwargs):
        event = get_object_or_404(
            Event.objects.select_related("leader", "specialization").prefetch_related(
                "organizers",
                "event_specializations__specialization",
            ),
            pk=event_id,
        )
        if not _can_export_event(request.user, event.id):
            return Response({"detail": "Недостаточно прав для экспорта мероприятия."}, status=status.HTTP_403_FORBIDDEN)
        return build_event_details_docx_response(event)


class EventApplicationsExportView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, event_id: int, *args, **kwargs):
        event = get_object_or_404(Event.objects.select_related("leader", "specialization"), pk=event_id)
        if not _can_export_event(request.user, event.id):
            return Response({"detail": "Недостаточно прав для экспорта заявок."}, status=status.HTTP_403_FORBIDDEN)
        return build_event_applications_xlsx_response(event)


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_REFERENCE],
        operation_summary="List statuses",
        operation_description="List statuses",
        responses={200: StatusSerializer(many=True)},
    ),
)
class StatusListView(ListAPIView):
    permission_classes = (AllowAny,)
    serializer_class = StatusSerializer
    queryset = Status.objects.all()


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_REFERENCE],
        operation_summary="List specializations",
        operation_description="List specializations",
        responses={200: SpecializationSerializer(many=True)},
    ),
)
class SpecializationListView(ListAPIView):
    permission_classes = (AllowAny,)
    serializer_class = SpecializationSerializer
    queryset = Specialization.objects.all()
