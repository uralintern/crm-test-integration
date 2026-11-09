"""Заявки."""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from rest_framework import status
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.generics import CreateAPIView, ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from users.permissions import (
    CuratorOrAdminPermission,
    ProjectantOnlyPermission,
    has_curator_or_admin_role,
    is_event_organizer,
)
from users.serializers import ApplicationCreateSerializer, ApplicationSerializer
from users.models import Application, Direction, Event
from users.automation_engine import run_crm_automation
from .schema import ERROR_RESPONSE_SCHEMA, TAG_APPLICATIONS


class ApplicationListView(ListCreateAPIView):
    """List and create applications."""

    filter_parameters = [
        openapi.Parameter(
            "event",
            openapi.IN_QUERY,
            description="ID мероприятия",
            type=openapi.TYPE_INTEGER,
        ),
        openapi.Parameter(
            "direction",
            openapi.IN_QUERY,
            description="ID направления",
            type=openapi.TYPE_INTEGER,
        ),
        openapi.Parameter(
            "specialization",
            openapi.IN_QUERY,
            description="ID специализации",
            type=openapi.TYPE_INTEGER,
        ),
        openapi.Parameter(
            "status",
            openapi.IN_QUERY,
            description="ID статуса",
            type=openapi.TYPE_INTEGER,
        ),
        openapi.Parameter(
            "user",
            openapi.IN_QUERY,
            description="ID пользователя",
            type=openapi.TYPE_INTEGER,
        ),
        openapi.Parameter(
            "is_approved",
            openapi.IN_QUERY,
            description="Фильтр по признаку одобрения заявки",
            type=openapi.TYPE_BOOLEAN,
        ),
        openapi.Parameter(
            "tests_assigned",
            openapi.IN_QUERY,
            description="Фильтр по назначению тестов",
            type=openapi.TYPE_BOOLEAN,
        ),
    ]
    def get_permissions(self):
        if self.request.method.lower() == "get":
            permissions = (IsAuthenticated,)
        else:
            permissions = (ProjectantOnlyPermission,)
        return [permission() for permission in permissions]

    def get_serializer_class(self):
        if self.request.method.lower() == "post":
            return ApplicationCreateSerializer
        return ApplicationSerializer
    @swagger_auto_schema(
        tags=[TAG_APPLICATIONS],
        operation_summary="List applications",
        operation_description="List applications",
        manual_parameters=filter_parameters,
        responses={200: ApplicationSerializer(many=True), 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=[TAG_APPLICATIONS],
        operation_summary="Create application",
        operation_description="Create application",
        request_body=ApplicationCreateSerializer,
        responses={201: ApplicationSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA},
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        run_crm_automation(instance, "application.created", request=request)
        output = ApplicationSerializer(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(output.data)
        return Response(output.data, status=status.HTTP_201_CREATED, headers=headers)

    def get_queryset(self):
        queryset = Application.objects.select_related(
            "user", "direction", "event", "project", "specialization", "status"
        ).filter(Q(event__is_archived=False) | Q(event__isnull=True)).order_by("-date_sub")
        
        if not has_curator_or_admin_role(self.request.user):
            assigned_event_ids = Event.objects.filter(
                Q(leader=self.request.user) | Q(organizers=self.request.user)
            ).values_list("id", flat=True)
            queryset = queryset.filter(Q(user=self.request.user) | Q(event_id__in=assigned_event_ids))

        filters = {
            "event": "event_id",
            "direction": "direction_id",
            "specialization": "specialization_id",
            "status": "status_id",
            "user": "user_id",
        }

        for param, field in filters.items():
            value = self.request.query_params.get(param)
            if value:
                queryset = queryset.filter(**{field: value})

        boolean_params = {
            "is_approved": "is_approved",
            "tests_assigned": "tests_assigned",
        }
        for param, field in boolean_params.items():
            value = self.request.query_params.get(param)
            if value is not None:
                normalized = value.lower() in {"true", "1", "yes", "t"}
                queryset = queryset.filter(**{field: normalized})

        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.method.lower() == "post":
            event_id = self.request.data.get("event") or self.request.data.get("event_id")
            direction_id = self.request.data.get("direction") or self.request.data.get("direction_id")

            if event_id:
                context["event"] = get_object_or_404(Event, pk=event_id, is_archived=False)
            if direction_id:
                context["direction"] = get_object_or_404(Direction, pk=direction_id)

        return context


class ApplicationDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete a specific application."""

    serializer_class = ApplicationSerializer
    lookup_url_kwarg = "application_id"

    def get_queryset(self):
        queryset = Application.objects.select_related(
            "user", "direction", "event", "project", "specialization", "status"
        ).filter(Q(event__is_archived=False) | Q(event__isnull=True))

        if not has_curator_or_admin_role(self.request.user):
            assigned_event_ids = Event.objects.filter(
                Q(leader=self.request.user) | Q(organizers=self.request.user)
            ).values_list("id", flat=True)
            queryset = queryset.filter(Q(user=self.request.user) | Q(event_id__in=assigned_event_ids))

        return queryset

    def get_permissions(self):
        if self.request.method.lower() == "get":
            permissions = (IsAuthenticated,)
        elif self.request.method.lower() in {"put", "patch"}:
            permissions = (IsAuthenticated,)
        else:
            permissions = (IsAuthenticated,)
        return [permission() for permission in permissions]

    @swagger_auto_schema(
        tags=[TAG_APPLICATIONS],
        operation_summary="Get application",
        operation_description="Получение заявки",
        responses={200: ApplicationSerializer, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=[TAG_APPLICATIONS],
        operation_summary="Update application",
        operation_description="Обновление заявки",
        request_body=ApplicationSerializer,
        responses={200: ApplicationSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=[TAG_APPLICATIONS],
        operation_summary="Delete application",
        operation_description="Удаление заявки",
        responses={204: "No content", 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    )
    def delete(self, request, *args, **kwargs):
        application = self.get_object()
        is_curator_or_admin = CuratorOrAdminPermission().has_permission(request, self)
        is_assigned_event_organizer = is_event_organizer(request.user, application.event_id)
        is_owner = application.user_id == request.user.id

        if not (is_curator_or_admin or is_assigned_event_organizer or is_owner):
            return Response(status=status.HTTP_403_FORBIDDEN)

        self.perform_destroy(application)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_update(self, serializer):
        previous_status = serializer.instance.status.name if serializer.instance.status_id else ""
        instance = serializer.save()
        current_status = instance.status.name if instance.status_id else ""
        if previous_status == current_status:
            return

        run_crm_automation(
            instance,
            "request.status_changed",
            previous_status=previous_status,
            request=self.request,
        )
        if current_status == "Прохождение тестирования":
            run_crm_automation(
                instance,
                "testing.started",
                previous_status=previous_status,
                request=self.request,
            )
        if current_status == "Добавился в орг. чат":
            run_crm_automation(
                instance,
                "notification.chat_link_opened",
                previous_status=previous_status,
                request=self.request,
            )
        if current_status == "Набор завершён":
            run_crm_automation(
                instance,
                "enrollment.closed",
                previous_status=previous_status,
                request=self.request,
            )

    def get_queryset(self):
        queryset = Application.objects.select_related(
            "user", "direction", "event", "project", "specialization", "status"
        )

        if has_curator_or_admin_role(self.request.user):
            return queryset

        assigned_event_ids = Event.objects.filter(
            Q(leader=self.request.user) | Q(organizers=self.request.user)
        ).values_list("id", flat=True)
        return queryset.filter(Q(user=self.request.user) | Q(event_id__in=assigned_event_ids))


@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        tags=[TAG_APPLICATIONS],
        operation_summary="Create application for direction",
        operation_description="Create application for direction",
        request_body=ApplicationCreateSerializer,
        responses={201: ApplicationSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
class DirectionApplicationCreateView(CreateAPIView):
    permission_classes = (ProjectantOnlyPermission,)
    serializer_class = ApplicationCreateSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        event = get_object_or_404(Event, pk=self.kwargs.get("event_id"), is_archived=False)
        direction = get_object_or_404(
            Direction, pk=self.kwargs.get("direction_id"), event=event
        )
        context.update({"event": event, "direction": direction})
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        output = ApplicationSerializer(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(output.data)
        return Response(output.data, status=status.HTTP_201_CREATED, headers=headers)
