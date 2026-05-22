from django.urls import path

from planner.views import (
    PlannerAutomationConfigView,
    PlannerAutomationDeadlineScanView,
    PlannerAutomationExecutionLogListView,
    PlannerAutomationPendingRunView,
    TeamPlannerDeskDetailView,
    TeamPlannerDeskListView,
)


urlpatterns = [
    path("automation/<int:event_id>/", PlannerAutomationConfigView.as_view(), name="planner-automation-config"),
    path(
        "automation/<int:event_id>/logs/",
        PlannerAutomationExecutionLogListView.as_view(),
        name="planner-automation-log-list",
    ),
    path("automation/run-deadline-scan/", PlannerAutomationDeadlineScanView.as_view(), name="planner-automation-deadline-scan"),
    path("automation/run-pending/", PlannerAutomationPendingRunView.as_view(), name="planner-automation-run-pending"),
    path("teams/desks/", TeamPlannerDeskListView.as_view(), name="planner-team-desk-list"),
    path(
        "teams/<int:team_id>/desk/",
        TeamPlannerDeskDetailView.as_view(),
        name="planner-team-desk-detail",
    ),
]
