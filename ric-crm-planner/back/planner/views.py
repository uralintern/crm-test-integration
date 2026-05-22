from copy import deepcopy

from django.db.models import Q
from django.db import transaction
from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.generics import ListAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from planner.automation_defaults import create_default_planner_automation_config
from planner.automation_engine import run_due_planner_automation, run_planner_automation, scan_planner_deadlines
from planner.models import PlannerAutomationConfig, PlannerAutomationExecutionLog, PlannerWorkspaceState, TeamPlannerDesk
from planner.serializers import (
    PlannerAutomationConfigPayloadSerializer,
    PlannerAutomationConfigSerializer,
    PlannerAutomationExecutionLogSerializer,
    PlannerWorkspaceStateSerializer,
    TeamPlannerDeskSerializer,
)
from users.models import Application, Event
from users.permissions import CuratorOrAdminPermission, has_curator_or_admin_role

TAG_PLANNER = "Planner"

ERROR_RESPONSE_SCHEMA = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    additional_properties=openapi.Schema(type=openapi.TYPE_STRING),
)


def _to_int(value):
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _team_id_from_item(item):
    if not isinstance(item, dict):
        return None
    return _to_int(item.get("teamId", item.get("team_id")))


def _member_ids_from_team(team):
    if not isinstance(team, dict):
        return []
    member_ids = team.get("memberIds", team.get("member_ids", []))
    if not isinstance(member_ids, list):
        return []
    return [_to_int(member_id) for member_id in member_ids]


def _team_ids_for_user(teams, user_id):
    if not isinstance(teams, list):
        return set()
    return {
        _to_int(team.get("id"))
        for team in teams
        if isinstance(team, dict)
        and (
            user_id in _member_ids_from_team(team)
            or user_id == _to_int(team.get("curatorId", team.get("curator_id")))
        )
    } - {None}


def _team_event_id(team):
    if not isinstance(team, dict):
        return None
    return _to_int(team.get("eventId", team.get("event_id")))


def _team_created_by(team):
    if not isinstance(team, dict):
        return None
    return _to_int(team.get("createdBy", team.get("created_by")))


def _assigned_event_ids_for_user(user):
    if not user or not user.is_authenticated:
        return set()
    return set(
        Event.objects.filter(Q(leader=user) | Q(organizers=user)).values_list("id", flat=True)
    )


def _team_ids_created_by_event_organizer(teams, user_id, event_ids):
    if not isinstance(teams, list) or not event_ids:
        return set()
    return {
        _to_int(team.get("id"))
        for team in teams
        if isinstance(team, dict)
        and _team_event_id(team) in event_ids
        and _team_created_by(team) == user_id
    } - {None}


def _visible_team_ids_for_restricted_user(teams, user):
    user_id = _to_int(user.id)
    assigned_event_ids = _assigned_event_ids_for_user(user)
    return _team_ids_for_user(teams, user_id) | _team_ids_created_by_event_organizer(teams, user_id, assigned_event_ids)


def _assignee_id_from_item(item):
    if not isinstance(item, dict):
        return None
    return _to_int(item.get("assigneeId", item.get("assignee_id")))


def _has_assignee_field(item):
    return isinstance(item, dict) and (
        "assigneeId" in item or "assignee_id" in item
    )


def _filter_items_by_team(items, team_ids):
    if not isinstance(items, list):
        return []
    return [item for item in items if _team_id_from_item(item) in team_ids]


def _team_member_roles(team):
    if not isinstance(team, dict):
        return {}
    member_roles = team.get("memberRoles", team.get("member_roles", {}))
    if isinstance(member_roles, dict):
        return {
            str(user_id): str(role)
            for user_id, role in member_roles.items()
            if str(role).strip()
        }
    return {}


def _enrich_team_member_roles(teams):
    if not isinstance(teams, list):
        return teams

    enriched = []
    for team in teams:
        if not isinstance(team, dict):
            enriched.append(team)
            continue

        member_ids = [member_id for member_id in _member_ids_from_team(team) if member_id is not None]
        member_roles = _team_member_roles(team)
        if member_ids:
            applications = (
                Application.objects.filter(user_id__in=member_ids)
                .select_related("specialization")
                .order_by("-date_sub", "-id")
            )
            source_request_ids = team.get("sourceRequestIds", team.get("source_request_ids", []))
            if isinstance(source_request_ids, list) and source_request_ids:
                applications = applications.filter(id__in=source_request_ids)
            else:
                event_id = _to_int(team.get("eventId", team.get("event_id")))
                direction_id = _to_int(team.get("directionId", team.get("direction_id")))
                project_id = _to_int(team.get("projectId", team.get("project_id")))
                if event_id is not None:
                    applications = applications.filter(event_id=event_id)
                if direction_id is not None:
                    applications = applications.filter(direction_id=direction_id)
                if project_id is not None:
                    applications = applications.filter(project_id=project_id)

            for application in applications:
                if not application.specialization_id:
                    continue
                member_roles.setdefault(str(application.user_id), application.specialization.name)

        enriched.append({**team, "memberRoles": member_roles})

    return enriched


def _sync_team_desks_from_workspace(workspace: PlannerWorkspaceState):
    teams = workspace.teams if isinstance(workspace.teams, list) else []
    parent_tasks = workspace.parent_tasks if isinstance(workspace.parent_tasks, list) else []
    subtasks = workspace.subtasks if isinstance(workspace.subtasks, list) else []

    teams_by_id = {}
    for team in teams:
        if not isinstance(team, dict):
            continue
        team_id = _to_int(team.get("id"))
        if team_id is None:
            continue
        teams_by_id[team_id] = team

    target_ids = set(teams_by_id.keys())

    with transaction.atomic():
        for team_id, team_data in teams_by_id.items():
            desk, _ = TeamPlannerDesk.objects.get_or_create(team_id=team_id)
            desk.team_name = str(team_data.get("name", "") or "")
            desk.curator_id = _to_int(team_data.get("curatorId", team_data.get("curator_id")))
            member_ids = team_data.get("memberIds", team_data.get("member_ids", []))
            desk.member_ids = member_ids if isinstance(member_ids, list) else []
            desk.parent_tasks = [item for item in parent_tasks if _team_id_from_item(item) == team_id]
            desk.subtasks = [item for item in subtasks if _team_id_from_item(item) == team_id]
            desk.columns = workspace.columns
            desk.save()

        TeamPlannerDesk.objects.exclude(team_id__in=target_ids).delete()


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_PLANNER],
        operation_summary="Get workspace planner state",
        operation_description="Get workspace planner state",
        responses={200: PlannerWorkspaceStateSerializer, 401: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="put",
    decorator=swagger_auto_schema(
        tags=[TAG_PLANNER],
        operation_summary="Replace workspace planner state",
        operation_description="Replace workspace planner state",
        request_body=PlannerWorkspaceStateSerializer,
        responses={200: PlannerWorkspaceStateSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="patch",
    decorator=swagger_auto_schema(
        tags=[TAG_PLANNER],
        operation_summary="Update workspace planner state",
        operation_description="Update workspace planner state",
        request_body=PlannerWorkspaceStateSerializer,
        responses={200: PlannerWorkspaceStateSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA},
    ),
)
class PlannerStateCompatView(RetrieveUpdateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = PlannerWorkspaceStateSerializer

    def get_object(self):
        state = PlannerWorkspaceState.objects.order_by("id").first()
        if state:
            return state
        return PlannerWorkspaceState.objects.create()

    def get(self, request, *args, **kwargs):
        workspace = self.get_object()
        data = self.get_serializer(workspace).data
        data["teams"] = _enrich_team_member_roles(data.get("teams", []))
        if not has_curator_or_admin_role(request.user):
            team_ids = _visible_team_ids_for_restricted_user(data.get("teams", []), request.user)
            data["teams"] = [
                team for team in data.get("teams", []) if _to_int(team.get("id")) in team_ids
            ]
            data["parent_tasks"] = _filter_items_by_team(data.get("parent_tasks", []), team_ids)
            data["subtasks"] = _filter_items_by_team(data.get("subtasks", []), team_ids)
        return Response(data)

    def perform_update(self, serializer):
        previous_teams = (
            deepcopy(serializer.instance.teams)
            if serializer.instance and isinstance(serializer.instance.teams, list)
            else []
        )
        previous_parent_tasks = (
            deepcopy(serializer.instance.parent_tasks)
            if serializer.instance and isinstance(serializer.instance.parent_tasks, list)
            else []
        )
        previous_subtasks = (
            deepcopy(serializer.instance.subtasks)
            if serializer.instance and isinstance(serializer.instance.subtasks, list)
            else []
        )
        previous_state = {
            "teams": previous_teams,
            "parent_tasks": previous_parent_tasks,
            "subtasks": previous_subtasks,
            "columns": deepcopy(serializer.instance.columns) if serializer.instance and isinstance(serializer.instance.columns, list) else [],
        }
        workspace = serializer.save()

        if not has_curator_or_admin_role(self.request.user):
            user_id = _to_int(self.request.user.id)
            assigned_event_ids = _assigned_event_ids_for_user(self.request.user)
            incoming_teams = workspace.teams if isinstance(workspace.teams, list) else []
            member_team_ids = _team_ids_for_user(previous_teams, user_id)
            organizer_team_ids = _team_ids_created_by_event_organizer(previous_teams + incoming_teams, user_id, assigned_event_ids)
            allowed_team_ids = member_team_ids | organizer_team_ids
            incoming_parent_tasks = workspace.parent_tasks if isinstance(workspace.parent_tasks, list) else []
            incoming_subtasks = workspace.subtasks if isinstance(workspace.subtasks, list) else []
            editable_teams = [
                team
                for team in incoming_teams
                if _to_int(team.get("id")) in organizer_team_ids
                and _team_event_id(team) in assigned_event_ids
                and _team_created_by(team) == user_id
            ]
            foreign_teams = [
                team for team in previous_teams if _to_int(team.get("id")) not in organizer_team_ids
            ]

            editable_parent_tasks = _filter_items_by_team(incoming_parent_tasks, allowed_team_ids)
            foreign_parent_tasks = [
                item for item in previous_parent_tasks if _team_id_from_item(item) not in allowed_team_ids
            ]
            editable_subtasks = _filter_items_by_team(incoming_subtasks, allowed_team_ids)
            foreign_subtasks = [
                item for item in previous_subtasks if _team_id_from_item(item) not in allowed_team_ids
            ]

            workspace.teams = foreign_teams + editable_teams
            workspace.parent_tasks = foreign_parent_tasks + editable_parent_tasks
            workspace.subtasks = foreign_subtasks + editable_subtasks
            workspace.save(update_fields=["teams", "parent_tasks", "subtasks", "updated_at"])

        run_planner_automation(previous_state, workspace)
        workspace.refresh_from_db()
        _sync_team_desks_from_workspace(workspace)


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
    queryset = TeamPlannerDesk.objects.all()


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
        return desk


class PlannerAutomationConfigView(RetrieveUpdateAPIView):
    permission_classes = (CuratorOrAdminPermission,)
    serializer_class = PlannerAutomationConfigSerializer

    def get_object(self):
        event_id = int(self.kwargs["event_id"])
        config = PlannerAutomationConfig.objects.filter(
            scope=PlannerAutomationConfig.SCOPE_PLANNER,
            event_id=event_id,
        ).first()
        if config:
            return config
        defaults = create_default_planner_automation_config(event_id)
        return PlannerAutomationConfig.objects.create(
            scope=PlannerAutomationConfig.SCOPE_PLANNER,
            event_id=event_id,
            stages=defaults["stages"],
            triggers=defaults["triggers"],
            robots=defaults["robots"],
        )

    def put(self, request, *args, **kwargs):
        return self._save_config(request)

    def patch(self, request, *args, **kwargs):
        return self._save_config(request, partial=True)

    def _save_config(self, request, partial=False):
        event_id = int(self.kwargs["event_id"])
        config = self.get_object()
        serializer = PlannerAutomationConfigPayloadSerializer(data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        config.scope = PlannerAutomationConfig.SCOPE_PLANNER
        config.event_id = event_id
        if "stages" in data:
            config.stages = data["stages"]
        if "triggers" in data:
            config.triggers = data["triggers"]
        if "robots" in data:
            config.robots = data["robots"]
        config.save()
        return Response(PlannerAutomationConfigSerializer(config).data)


class PlannerAutomationExecutionLogListView(ListAPIView):
    permission_classes = (CuratorOrAdminPermission,)
    serializer_class = PlannerAutomationExecutionLogSerializer

    def get_queryset(self):
        return PlannerAutomationExecutionLog.objects.filter(
            event_id=self.kwargs["event_id"],
            config__scope=PlannerAutomationConfig.SCOPE_PLANNER,
        ).select_related("config")


class PlannerAutomationDeadlineScanView(APIView):
    permission_classes = (CuratorOrAdminPermission,)

    def post(self, request, *args, **kwargs):
        return Response(scan_planner_deadlines())


class PlannerAutomationPendingRunView(APIView):
    permission_classes = (CuratorOrAdminPermission,)

    def post(self, request, *args, **kwargs):
        return Response(run_due_planner_automation())
