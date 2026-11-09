"""Движок автоматизации планировщика.

Все прежние имена доступны как `planner.automation_engine.<имя>`.
"""

from .constants import (  # noqa: F401
    DONE_STATUSES,
    REVIEW_STATUSES,
    STARTED_STATUSES,
    OVERLOADED_ACTIVE_TASK_LIMIT,
    STALE_TASK_DAYS,
    SPRINT_SWEEP_ROBOT_ID,
    SPRINT_SWEEP_EVENT_CODE,
    DEFAULT_SPRINT_WEEK_UTC_OFFSET_HOURS,
)
from .utils import (  # noqa: F401
    to_int,
    normalized_text,
    lower_text,
    stable_fingerprint,
)
from .events import (  # noqa: F401
    PlannerAutomationEvent,
)
from .items import (  # noqa: F401
    item_id,
    item_team_id,
    item_assignee_id,
    item_member_id,
    item_recipient_id,
    item_status,
    item_end_date,
    item_updated_at,
    is_done_status,
    is_review_status,
    is_started_status,
    is_active_task,
    is_in_sprint,
    set_in_sprint,
    list_by_id,
    team_by_id,
    team_event_id,
    team_curator_id,
    task_stage_id,
    _member_ids_from_team_like,
)
from .config import (  # noqa: F401
    stage_by_id,
    target_status_for_stage,
    config_model_to_dict,
    get_or_create_config,
)
from .conditions import (  # noqa: F401
    event_context,
    condition_value,
    compare_values,
    conditions_match,
    render_template,
)
from .logs import (  # noqa: F401
    create_log,
    log_exists,
    should_delay,
)
from .actions import (  # noqa: F401
    create_notification,
    send_vk_notification,
    run_robot_action,
    update_item_status,
)
from .detection import (  # noqa: F401
    has_task_data_changed,
    deadline_changed,
    detect_planner_events,
    detect_planner_scan_events,
)
from .runner import (  # noqa: F401
    execute_pending_log,
    run_stage_robots,
    run_trigger,
    run_config_for_event,
    apply_sprint_added_fallback,
    workspace_state_dict,
    run_planner_automation,
    scan_planner_deadlines,
    run_due_planner_automation,
)
from .sprint import (  # noqa: F401
    sprint_week_timezone,
    sprint_week_key,
    find_sprint_sweep_robot,
    sprint_sweep_event,
    sync_desks_in_sprint_flags,
    sweep_done_subtasks_from_sprint,
)
