"""Права пользователя в команде бэклога (BL-32, BL-33, M-12, «Карточки» §8).

Роли:
- участник — пользователь из `memberIds` команды;
- куратор — пользователь из `curatorId` команды (глобальная CRM-роль куратора не учитывается);
- организатор — руководитель или организатор мероприятия команды;
- администратор — суперпользователь, staff или CRM-роль admin.
Куратор, организатор и администратор имеют одинаковые права («менеджер»).
"""

from dataclasses import dataclass
from enum import Enum

from planner.models import PlannerWorkspaceState
from users.models import CRMRole, ROLE_ADMIN
from users.permissions import is_event_organizer


class BacklogRole(str, Enum):
    ADMIN = "admin"
    CURATOR = "curator"
    ORGANIZER = "organizer"
    MEMBER = "member"


MANAGER_ROLES = frozenset({BacklogRole.ADMIN, BacklogRole.CURATOR, BacklogRole.ORGANIZER})


@dataclass(frozen=True)
class TeamAccess:
    team_id: int
    team: dict
    role: BacklogRole | None

    @property
    def can_view(self) -> bool:
        return self.role is not None

    @property
    def can_edit(self) -> bool:
        # Внутри команды права на создание и редактирование одинаковы у всех («Карточки» §8).
        return self.role is not None

    @property
    def is_manager(self) -> bool:
        return self.role in MANAGER_ROLES


def _to_int(value):
    try:
        return int(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def find_team(team_id) -> dict | None:
    """Команда из JSON планировщика по id (или None)."""
    normalized_id = _to_int(team_id)
    if normalized_id is None:
        return None
    workspace = PlannerWorkspaceState.objects.order_by("id").only("teams").first()
    teams = workspace.teams if workspace and isinstance(workspace.teams, list) else []
    for team in teams:
        if isinstance(team, dict) and _to_int(team.get("id")) == normalized_id:
            return team
    return None


def team_member_ids(team: dict) -> set[int]:
    member_ids = team.get("memberIds", team.get("member_ids", []))
    if not isinstance(member_ids, list):
        return set()
    return {member_id for member_id in (_to_int(value) for value in member_ids) if member_id is not None}


def team_curator_id(team: dict) -> int | None:
    return _to_int(team.get("curatorId", team.get("curator_id")))


def team_event_id(team: dict) -> int | None:
    return _to_int(team.get("eventId", team.get("event_id")))


def _is_admin(user) -> bool:
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    return CRMRole.objects.filter(user=user, role_type=ROLE_ADMIN).exists()


def resolve_role(user, team: dict) -> BacklogRole | None:
    if not user or not user.is_authenticated:
        return None
    if team_curator_id(team) == user.id:
        return BacklogRole.CURATOR
    if _is_admin(user):
        return BacklogRole.ADMIN
    event_id = team_event_id(team)
    if event_id and is_event_organizer(user, event_id):
        return BacklogRole.ORGANIZER
    if user.id in team_member_ids(team):
        return BacklogRole.MEMBER
    return None


def get_team_access(user, team_id) -> TeamAccess | None:
    """Права пользователя в команде; None, если такой команды нет."""
    team = find_team(team_id)
    if team is None:
        return None
    return TeamAccess(team_id=_to_int(team_id), team=team, role=resolve_role(user, team))


def can_delete(access: TeamAccess, user, obj) -> bool:
    """Участник удаляет только созданное им; куратор, организатор и админ — всё в команде."""
    return access.is_manager or (obj.created_by_id is not None and obj.created_by_id == user.id)


def can_complete_task(access: TeamAccess) -> bool:
    """Задачу принимает куратор (и организатор, администратор) — «Карточки» §6."""
    return access.is_manager


def can_complete_subtask(access: TeamAccess, user, subtask) -> bool:
    """Подзадачу принимает ответственный задачи или куратор — «Карточки» §6."""
    return access.is_manager or subtask.task.responsible_id == user.id
