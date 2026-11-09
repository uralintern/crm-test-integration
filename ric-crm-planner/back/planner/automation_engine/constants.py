"""Константы автоматизации планировщика."""




DONE_STATUSES = {"готово", "done", "завершено"}
REVIEW_STATUSES = {"на проверке", "review"}
STARTED_STATUSES = {"в работе", "in progress", "in-progress"}
OVERLOADED_ACTIVE_TASK_LIMIT = 5
STALE_TASK_DAYS = 3
SPRINT_SWEEP_ROBOT_ID = "planner-remove-done-from-sprint"
SPRINT_SWEEP_EVENT_CODE = "sprint.week_ended"
DEFAULT_SPRINT_WEEK_UTC_OFFSET_HOURS = 3
