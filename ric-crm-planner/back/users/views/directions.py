"""Направления и проекты."""

from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema
from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveUpdateDestroyAPIView
from users.permissions import PublicReadCuratorAdminWritePermission
from users.serializers import DirectionSerializer, ProjectSerializer
from users.models import Direction, Event, Project
from .schema import ERROR_RESPONSE_SCHEMA, TAG_DIRECTIONS, TAG_PROJECTS


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_DIRECTIONS],
        operation_summary="List directions in event",
        operation_description="List directions in event",
        responses={200: DirectionSerializer(many=True), 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        tags=[TAG_DIRECTIONS],
        operation_summary="Create direction in event",
        operation_description="Create direction in event",
        request_body=DirectionSerializer,
        responses={201: DirectionSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
class DirectionListCreateView(ListCreateAPIView):
    permission_classes = (PublicReadCuratorAdminWritePermission,)
    serializer_class = DirectionSerializer

    def get_queryset(self):
        event = get_object_or_404(Event, pk=self.kwargs.get("event_id"), is_archived=False)
        return Direction.objects.filter(event=event).select_related("event", "leader")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["event"] = get_object_or_404(Event, pk=self.kwargs.get("event_id"), is_archived=False)
        return context


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_DIRECTIONS],
        operation_summary="Get direction",
        operation_description="Get direction",
        responses={200: DirectionSerializer, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="put",
    decorator=swagger_auto_schema(
        tags=[TAG_DIRECTIONS],
        operation_summary="Replace direction",
        operation_description="Replace direction",
        request_body=DirectionSerializer,
        responses={200: DirectionSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="patch",
    decorator=swagger_auto_schema(
        tags=[TAG_DIRECTIONS],
        operation_summary="Update direction",
        operation_description="Update direction",
        request_body=DirectionSerializer,
        responses={200: DirectionSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="delete",
    decorator=swagger_auto_schema(
        tags=[TAG_DIRECTIONS],
        operation_summary="Delete direction",
        operation_description="Delete direction",
        responses={204: "No content", 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
class DirectionDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = (PublicReadCuratorAdminWritePermission,)
    serializer_class = DirectionSerializer
    lookup_url_kwarg = "direction_id"

    def get_queryset(self):
        event = get_object_or_404(Event, pk=self.kwargs.get("event_id"), is_archived=False)
        return Direction.objects.filter(event=event).select_related("event", "leader")


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_PROJECTS],
        operation_summary="List projects in direction",
        operation_description="List projects in direction",
        responses={200: ProjectSerializer(many=True), 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        tags=[TAG_PROJECTS],
        operation_summary="Create project in direction",
        operation_description="Create project in direction",
        request_body=ProjectSerializer,
        responses={201: ProjectSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
class ProjectListCreateView(ListCreateAPIView):
    permission_classes = (PublicReadCuratorAdminWritePermission,)
    serializer_class = ProjectSerializer

    def get_queryset(self):
        event = get_object_or_404(Event, pk=self.kwargs.get("event_id"), is_archived=False)
        direction = get_object_or_404(
            Direction, pk=self.kwargs.get("direction_id"), event=event
        )
        return Project.objects.filter(direction=direction).select_related(
            "direction", "curator", "direction__event"
        )
        

    def get_serializer_context(self):
        context = super().get_serializer_context()
        event = get_object_or_404(Event, pk=self.kwargs.get("event_id"), is_archived=False)
        direction = get_object_or_404(
            Direction, pk=self.kwargs.get("direction_id"), event=event
        )
        context["direction"] = direction
        return context


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_PROJECTS],
        operation_summary="Get project",
        operation_description="Get project",
        responses={200: ProjectSerializer, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="put",
    decorator=swagger_auto_schema(
        tags=[TAG_PROJECTS],
        operation_summary="Replace project",
        operation_description="Replace project",
        request_body=ProjectSerializer,
        responses={200: ProjectSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="patch",
    decorator=swagger_auto_schema(
        tags=[TAG_PROJECTS],
        operation_summary="Update project",
        operation_description="Update project",
        request_body=ProjectSerializer,
        responses={200: ProjectSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="delete",
    decorator=swagger_auto_schema(
        tags=[TAG_PROJECTS],
        operation_summary="Delete project",
        operation_description="Delete project",
        responses={204: "No content", 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
class ProjectDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = (PublicReadCuratorAdminWritePermission,)
    serializer_class = ProjectSerializer
    lookup_url_kwarg = "project_id"
    queryset = Project.objects.filter(direction__event__is_archived=False).select_related("direction", "curator", "direction__event")


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_PROJECTS],
        operation_summary="List all projects",
        operation_description="List all projects",
        responses={200: ProjectSerializer(many=True), 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        tags=[TAG_PROJECTS],
        operation_summary="Create project",
        operation_description="Create project",
        request_body=ProjectSerializer,
        responses={201: ProjectSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA},
    ),
)
class UserProjectListCreateView(ListCreateAPIView):
    permission_classes = (PublicReadCuratorAdminWritePermission,)
    serializer_class = ProjectSerializer
    queryset = Project.objects.filter(direction__event__is_archived=False).select_related("direction", "curator", "direction__event")


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_DIRECTIONS],
        operation_summary="List all directions",
        operation_description="List all directions",
        responses={200: DirectionSerializer(many=True), 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA},
    ),
)
class UserDirectionListView(ListAPIView):
    permission_classes = (PublicReadCuratorAdminWritePermission,)
    serializer_class = DirectionSerializer
    queryset = Direction.objects.filter(event__is_archived=False).select_related("event", "leader")
