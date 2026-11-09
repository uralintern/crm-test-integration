"""Движок CRM-автоматизации (стадии, триггеры, роботы).

Все прежние имена доступны как `users.automation_engine.<имя>`.
"""

from .utils import (  # noqa: F401
    to_int,
    normalized_text,
    lower_text,
    stable_fingerprint,
)
from .events import (  # noqa: F401
    CRMAutomationEvent,
)
from .config import (  # noqa: F401
    CHAT_LINK_ROBOT_IDS,
    CHAT_LINK_TRIGGER_IDS,
    normalize_crm_automation_config_dict,
    config_model_to_dict,
    get_or_create_config,
    stage_by_id,
    status_stage_id,
    target_status_for_stage,
)
from .conditions import (  # noqa: F401
    application_status,
    application_display_name,
    user_display_name,
    application_profile,
    latest_test_result,
    event_context,
    condition_value,
    compare_values,
    conditions_match,
    render_template,
)
from .logs import (  # noqa: F401
    should_delay,
    rule_run_key,
    create_log,
    log_exists,
)
from .actions import (  # noqa: F401
    get_application_organizers,
    create_notification,
    create_organizer_notifications,
    update_application_status,
    robot_attachment_ids,
    get_robot_attachments,
    run_robot_action,
)
from .runner import (  # noqa: F401
    run_stage_robots,
    run_trigger,
    run_crm_automation,
    execute_pending_log,
    run_due_crm_automation,
)
