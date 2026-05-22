from django.db import models


def planner_default_columns():
    return ["Запланировано", "В работе", "На проверке", "Готово"]


class PlannerWorkspaceState(models.Model):
    enrollment_closed = models.BooleanField(default=False)
    participants = models.JSONField(default=list)
    teams = models.JSONField(default=list)
    parent_tasks = models.JSONField(default=list)
    subtasks = models.JSONField(default=list)
    columns = models.JSONField(default=planner_default_columns)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "CRM_PLANNER_WORKSPACE_STATE"

    def __str__(self):
        return "Состояние планировщика"


class TeamPlannerDesk(models.Model):
    team_id = models.BigIntegerField(unique=True)
    team_name = models.CharField(max_length=255, blank=True)
    curator_id = models.BigIntegerField(null=True, blank=True)
    member_ids = models.JSONField(default=list)
    parent_tasks = models.JSONField(default=list)
    subtasks = models.JSONField(default=list)
    columns = models.JSONField(default=planner_default_columns)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "CRM_TEAM_PLANNER_DESK"
        ordering = ("team_id",)

    def __str__(self):
        return f"Доска команды #{self.team_id}"


class PlannerAutomationConfig(models.Model):
    SCOPE_PLANNER = "planner"

    scope = models.CharField(max_length=32, default=SCOPE_PLANNER)
    event_id = models.BigIntegerField()
    stages = models.JSONField(default=list)
    triggers = models.JSONField(default=list)
    robots = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "CRM_PLANNER_AUTOMATION_CONFIG"
        constraints = [
            models.UniqueConstraint(
                fields=["scope", "event_id"],
                name="unique_planner_automation_config_scope_event",
            )
        ]
        ordering = ("scope", "event_id")

    def __str__(self):
        return f"Автоматизация планировщика: {self.scope}:{self.event_id}"


class PlannerAutomationExecutionLog(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SUCCESS = "success"
    STATUS_SKIPPED = "skipped"
    STATUS_FAILED = "failed"

    config = models.ForeignKey(
        PlannerAutomationConfig,
        on_delete=models.CASCADE,
        related_name="execution_logs",
    )
    event_id = models.BigIntegerField()
    team_id = models.BigIntegerField(null=True, blank=True)
    entity_type = models.CharField(max_length=32)
    entity_id = models.CharField(max_length=64)
    event_code = models.CharField(max_length=100)
    rule_kind = models.CharField(max_length=16)
    rule_id = models.CharField(max_length=120)
    run_key = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=16, default=STATUS_PENDING)
    message = models.TextField(blank=True)
    context = models.JSONField(default=dict)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "CRM_PLANNER_AUTOMATION_EXECUTION_LOG"
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=["event_id", "status"]),
            models.Index(fields=["scheduled_for", "status"]),
        ]

    def __str__(self):
        return f"{self.rule_kind}:{self.rule_id} — {self.status}"
