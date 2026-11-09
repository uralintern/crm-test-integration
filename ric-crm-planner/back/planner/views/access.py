"""Кто какие команды и доски видит: разбор команд из JSON и проверки доступа."""

from django.db.models import Q
from planner.models import PlannerWorkspaceState, TeamPlannerDesk
from users.models import Application, Event
from users.permissions import has_curator_or_admin_role


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


def _team_ids_for_event_organizer(teams, event_ids):
    if not isinstance(teams, list) or not event_ids:
        return set()
    return {
        _to_int(team.get("id"))
        for team in teams
        if isinstance(team, dict) and _team_event_id(team) in event_ids
    } - {None}


def _visible_team_ids_for_restricted_user(teams, user):
    user_id = _to_int(user.id)
    assigned_event_ids = _assigned_event_ids_for_user(user)
    return _team_ids_for_user(teams, user_id) | _team_ids_for_event_organizer(teams, assigned_event_ids)


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


def _user_can_access_team_desk(user, team_id):
    if not user or not user.is_authenticated:
        return False
    if has_curator_or_admin_role(user):
        return True

    normalized_team_id = _to_int(team_id)
    workspace = PlannerWorkspaceState.objects.order_by("id").first()
    teams = workspace.teams if workspace and isinstance(workspace.teams, list) else []
    if normalized_team_id in _visible_team_ids_for_restricted_user(teams, user):
        return True

    desk = TeamPlannerDesk.objects.filter(team_id=normalized_team_id).first()
    if not desk:
        return False

    user_id = _to_int(user.id)
    member_ids = [_to_int(member_id) for member_id in (desk.member_ids if isinstance(desk.member_ids, list) else [])]
    return user_id in member_ids or user_id == _to_int(desk.curator_id)
