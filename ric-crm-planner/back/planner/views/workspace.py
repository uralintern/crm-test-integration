"""Общее состояние планировщика (/api/users/planner/)."""

from copy import deepcopy
from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from planner.automation_engine import run_planner_automation
from planner.models import PlannerWorkspaceState
from planner.realtime import broadcast_team_desk_update
from planner.serializers import PlannerWorkspaceStateSerializer
from users.permissions import has_curator_or_admin_role
from .schema import ERROR_RESPONSE_SCHEMA, TAG_PLANNER
from .access import (
    _assigned_event_ids_for_user,
    _enrich_team_member_roles,
    _filter_items_by_team,
    _team_event_id,
    _team_id_from_item,
    _team_ids_for_event_organizer,
    _team_ids_for_user,
    _to_int,
    _visible_team_ids_for_restricted_user,
)
from .sync import (
    _merge_missing_json_items_by_id,
    _request_flag_enabled,
    _sync_team_desks_from_workspace,
)


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
        prune_missing_team_desks = _request_flag_enabled(self.request.data.get("prune_missing_team_desks"))
        workspace = serializer.save()

        if self.request.method.upper() == "PATCH" and not prune_missing_team_desks:
            update_fields = []
            if "teams" in self.request.data:
                workspace.teams = _merge_missing_json_items_by_id(workspace.teams, previous_teams)
                update_fields.append("teams")
            if "parent_tasks" in self.request.data:
                workspace.parent_tasks = _merge_missing_json_items_by_id(workspace.parent_tasks, previous_parent_tasks)
                update_fields.append("parent_tasks")
            if "subtasks" in self.request.data:
                workspace.subtasks = _merge_missing_json_items_by_id(workspace.subtasks, previous_subtasks)
                update_fields.append("subtasks")
            if update_fields:
                update_fields.append("updated_at")
                workspace.save(update_fields=update_fields)

        if not has_curator_or_admin_role(self.request.user):
            user_id = _to_int(self.request.user.id)
            assigned_event_ids = _assigned_event_ids_for_user(self.request.user)
            incoming_teams = workspace.teams if isinstance(workspace.teams, list) else []
            member_team_ids = _team_ids_for_user(previous_teams, user_id)
            organizer_team_ids = _team_ids_for_event_organizer(previous_teams + incoming_teams, assigned_event_ids)
            allowed_team_ids = member_team_ids | organizer_team_ids
            incoming_parent_tasks = workspace.parent_tasks if isinstance(workspace.parent_tasks, list) else []
            incoming_subtasks = workspace.subtasks if isinstance(workspace.subtasks, list) else []
            editable_teams = [
                team
                for team in incoming_teams
                if _to_int(team.get("id")) in organizer_team_ids
                and _team_event_id(team) in assigned_event_ids
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
        should_sync_desks = self.request.method.upper() == "PUT" or "teams" in self.request.data or "parent_tasks" in self.request.data or "subtasks" in self.request.data
        if should_sync_desks:
            for desk in _sync_team_desks_from_workspace(workspace, prune_missing=prune_missing_team_desks):
                broadcast_team_desk_update(desk)
