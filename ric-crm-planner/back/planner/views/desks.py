"""Доски команд."""

from copy import deepcopy
from django.db.models import Q
from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import ListAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from planner.automation_engine import run_planner_automation
from planner.models import PlannerWorkspaceState, TeamPlannerDesk
from planner.realtime import broadcast_team_desk_update
from planner.serializers import TeamPlannerDeskSerializer
from users.permissions import has_curator_or_admin_role
from .schema import ERROR_RESPONSE_SCHEMA, TAG_PLANNER
from .access import _to_int, _user_can_access_team_desk, _visible_team_ids_for_restricted_user
from .sync import (
    _is_stale_team_desk_update,
    _merge_stale_team_desk_payload,
    _sync_workspace_from_team_desk,
)


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_PLANNER],
        operation_summary="List team planner desks",
        operation_description="List team planner desks",
        responses={200: TeamPlannerDeskSerializer(many=True), 401: ERROR_RESPONSE_SCHEMA},
    ),
)
class TeamPlannerDeskListView(ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = TeamPlannerDeskSerializer

    def get_queryset(self):
        if has_curator_or_admin_role(self.request.user):
            return TeamPlannerDesk.objects.all()

        workspace = PlannerWorkspaceState.objects.order_by("id").first()
        teams = workspace.teams if workspace and isinstance(workspace.teams, list) else []
        visible_team_ids = _visible_team_ids_for_restricted_user(teams, self.request.user)
        user_id = _to_int(self.request.user.id)
        return TeamPlannerDesk.objects.filter(
            Q(team_id__in=visible_team_ids) | Q(curator_id=user_id) | Q(member_ids__contains=[user_id])
        )


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_PLANNER],
        operation_summary="Get team planner desk",
        operation_description="Get team planner desk",
        responses={200: TeamPlannerDeskSerializer, 401: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="put",
    decorator=swagger_auto_schema(
        tags=[TAG_PLANNER],
        operation_summary="Replace team planner desk",
        operation_description="Replace team planner desk",
        request_body=TeamPlannerDeskSerializer,
        responses={200: TeamPlannerDeskSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="patch",
    decorator=swagger_auto_schema(
        tags=[TAG_PLANNER],
        operation_summary="Update team planner desk",
        operation_description="Update team planner desk",
        request_body=TeamPlannerDeskSerializer,
        responses={200: TeamPlannerDeskSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
class TeamPlannerDeskDetailView(RetrieveUpdateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = TeamPlannerDeskSerializer
    lookup_url_kwarg = "team_id"

    def get_object(self):
        team_id = self.kwargs.get(self.lookup_url_kwarg)
        desk, _ = TeamPlannerDesk.objects.get_or_create(team_id=team_id)
        if not _user_can_access_team_desk(self.request.user, team_id):
            raise PermissionDenied("No access to team desk.")
        return desk

    def perform_update(self, serializer):
        incoming_updated_at = self.request.data.get("updated_at") or self.request.data.get("updatedAt")
        if _is_stale_team_desk_update(serializer.instance, incoming_updated_at):
            _merge_stale_team_desk_payload(serializer.instance, serializer.validated_data)

        workspace = PlannerWorkspaceState.objects.order_by("id").first()
        previous_state = {
            "teams": deepcopy(workspace.teams) if workspace and isinstance(workspace.teams, list) else [],
            "parent_tasks": deepcopy(workspace.parent_tasks) if workspace and isinstance(workspace.parent_tasks, list) else [],
            "subtasks": deepcopy(workspace.subtasks) if workspace and isinstance(workspace.subtasks, list) else [],
            "columns": deepcopy(workspace.columns) if workspace and isinstance(workspace.columns, list) else [],
        }
        desk = serializer.save()
        workspace = _sync_workspace_from_team_desk(desk)
        run_planner_automation(previous_state, workspace)
        broadcast_team_desk_update(desk)
