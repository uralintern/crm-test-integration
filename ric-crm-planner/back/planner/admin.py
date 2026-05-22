from django.contrib import admin

from planner.models import PlannerAutomationConfig, PlannerAutomationExecutionLog, TeamPlannerDesk


@admin.register(TeamPlannerDesk)
class TeamPlannerDeskAdmin(admin.ModelAdmin):
    list_display = ("team_id", "team_name", "updated_at")
    search_fields = ("team_id", "team_name")


@admin.register(PlannerAutomationConfig)
class PlannerAutomationConfigAdmin(admin.ModelAdmin):
    list_display = ("scope", "event_id", "updated_at")
    search_fields = ("scope", "event_id")


@admin.register(PlannerAutomationExecutionLog)
class PlannerAutomationExecutionLogAdmin(admin.ModelAdmin):
    list_display = ("event_id", "rule_kind", "rule_id", "event_code", "status", "created_at")
    list_filter = ("status", "rule_kind", "event_code")
    search_fields = ("rule_id", "event_code", "entity_id", "message")
