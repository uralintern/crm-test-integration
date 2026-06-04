import json
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.serializers.json import DjangoJSONEncoder

from planner.serializers import TeamPlannerDeskSerializer

logger = logging.getLogger(__name__)


def planner_team_group_name(team_id: int) -> str:
    return f"planner_team_{int(team_id)}"


def _json_safe(value):
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


def broadcast_team_desk_update(desk, action: str = "updated") -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.warning("Planner realtime skipped: channel layer is not configured")
        return

    payload = _json_safe(TeamPlannerDeskSerializer(desk).data)

    try:
        async_to_sync(channel_layer.group_send)(
            planner_team_group_name(desk.team_id),
            {
                "type": "desk.updated",
                "action": action,
                "teamId": int(desk.team_id),
                "desk": payload,
            },
        )
    except Exception:
        logger.exception("Planner realtime broadcast failed for team_id=%s", desk.team_id)
