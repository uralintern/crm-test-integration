"""Синхронизация общего состояния планировщика и досок команд, слияние правок."""

from copy import deepcopy
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from planner.models import PlannerWorkspaceState, TeamPlannerDesk
from .access import _team_id_from_item, _to_int


def _sync_team_desks_from_workspace(workspace: PlannerWorkspaceState, prune_missing: bool = False):
    teams = workspace.teams if isinstance(workspace.teams, list) else []
    parent_tasks = workspace.parent_tasks if isinstance(workspace.parent_tasks, list) else []
    subtasks = workspace.subtasks if isinstance(workspace.subtasks, list) else []
    updated_desks = []

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
            updated_desks.append(desk)

        if prune_missing:
            TeamPlannerDesk.objects.exclude(team_id__in=target_ids).delete()

    return updated_desks


def _request_flag_enabled(value):
    return value is True or str(value).strip().lower() in {"1", "true", "yes", "on"}


def _merge_missing_json_items_by_id(current_items, previous_items):
    result = deepcopy(current_items) if isinstance(current_items, list) else []
    seen_ids = {
        _to_int(item.get("id"))
        for item in result
        if isinstance(item, dict) and _to_int(item.get("id")) is not None
    }
    for item in previous_items if isinstance(previous_items, list) else []:
        if not isinstance(item, dict):
            continue
        item_id = _to_int(item.get("id"))
        if item_id is not None and item_id not in seen_ids:
            result.append(deepcopy(item))
            seen_ids.add(item_id)
    return result


def _sync_workspace_from_team_desk(desk: TeamPlannerDesk):
    workspace = PlannerWorkspaceState.objects.order_by("id").first()
    if not workspace:
        workspace = PlannerWorkspaceState.objects.create()

    team_id = _to_int(desk.team_id)
    teams = workspace.teams if isinstance(workspace.teams, list) else []
    parent_tasks = workspace.parent_tasks if isinstance(workspace.parent_tasks, list) else []
    subtasks = workspace.subtasks if isinstance(workspace.subtasks, list) else []

    next_teams = []
    team_found = False
    for team in teams:
        if not isinstance(team, dict) or _to_int(team.get("id")) != team_id:
            next_teams.append(team)
            continue

        team_found = True
        next_teams.append(
            {
                **team,
                "name": desk.team_name or team.get("name", ""),
                "curatorId": desk.curator_id,
                "memberIds": desk.member_ids if isinstance(desk.member_ids, list) else [],
            }
        )

    if not team_found and team_id is not None:
        next_teams.append(
            {
                "id": team_id,
                "name": desk.team_name or f"Команда #{team_id}",
                "curatorId": desk.curator_id,
                "memberIds": desk.member_ids if isinstance(desk.member_ids, list) else [],
                "confirmed": False,
            }
        )

    workspace.teams = next_teams
    workspace.parent_tasks = [item for item in parent_tasks if _team_id_from_item(item) != team_id] + (
        desk.parent_tasks if isinstance(desk.parent_tasks, list) else []
    )
    workspace.subtasks = [item for item in subtasks if _team_id_from_item(item) != team_id] + (
        desk.subtasks if isinstance(desk.subtasks, list) else []
    )
    if isinstance(desk.columns, list) and desk.columns:
        workspace.columns = desk.columns
    workspace.save(update_fields=["teams", "parent_tasks", "subtasks", "columns", "updated_at"])
    return workspace


def _parse_client_updated_at(value):
    if not value:
        return None
    parsed = parse_datetime(str(value))
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _is_stale_team_desk_update(desk: TeamPlannerDesk, incoming_updated_at) -> bool:
    client_updated_at = _parse_client_updated_at(incoming_updated_at)
    if client_updated_at is None or not desk.updated_at:
        return False
    return client_updated_at < desk.updated_at - timedelta(milliseconds=10)


def _merge_json_items_by_id(current_items, incoming_items):
    result = deepcopy(current_items) if isinstance(current_items, list) else []
    seen_ids = {
        _to_int(item.get("id"))
        for item in result
        if isinstance(item, dict) and _to_int(item.get("id")) is not None
    }
    for item in incoming_items if isinstance(incoming_items, list) else []:
        if not isinstance(item, dict):
            continue
        item_id = _to_int(item.get("id"))
        if item_id is None or item_id not in seen_ids:
            result.append(deepcopy(item))
            if item_id is not None:
                seen_ids.add(item_id)
    return result


def _merge_stale_team_desk_payload(desk: TeamPlannerDesk, validated_data):
    if "parent_tasks" in validated_data:
        validated_data["parent_tasks"] = _merge_json_items_by_id(desk.parent_tasks, validated_data.get("parent_tasks"))
    if "subtasks" in validated_data:
        validated_data["subtasks"] = _merge_json_items_by_id(desk.subtasks, validated_data.get("subtasks"))
    for field in ("team_name", "curator_id", "member_ids", "columns"):
        if field in validated_data:
            validated_data[field] = deepcopy(getattr(desk, field))
