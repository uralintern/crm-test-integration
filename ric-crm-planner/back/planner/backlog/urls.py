from django.urls import path

from .views import BacklogByCodeView, BacklogSubtaskDetailView, BacklogTaskDetailView, BacklogTeamTreeView
from .views_hierarchy import (
    BacklogStageCreateView,
    BacklogStageDetailView,
    BacklogStageReorderView,
    BacklogSubtaskBulkCreateView,
    BacklogSubtaskCreateView,
    BacklogTaskCreateView,
    BacklogTaskReorderView,
    BacklogWorkCreateView,
    BacklogWorkDetailView,
)
from .views_workflow import (
    BacklogKanbanView,
    BacklogSprintDetailView,
    BacklogSprintListView,
    BacklogSubtaskCommentsView,
    BacklogSubtaskCompleteView,
    BacklogSubtaskReworkView,
    BacklogTaskCommentsView,
    BacklogTaskCompleteView,
    BacklogTaskReworkView,
)

urlpatterns = [
    # Команда
    path("teams/<int:team_id>/", BacklogTeamTreeView.as_view(), name="backlog-team-tree"),
    path("teams/<int:team_id>/stages/", BacklogStageCreateView.as_view(), name="backlog-stage-create"),
    path("teams/<int:team_id>/stages/reorder/", BacklogStageReorderView.as_view(), name="backlog-stage-reorder"),
    path("teams/<int:team_id>/sprints/", BacklogSprintListView.as_view(), name="backlog-sprints"),
    path("teams/<int:team_id>/kanban/", BacklogKanbanView.as_view(), name="backlog-kanban"),
    # Этапы
    path("stages/<int:stage_id>/", BacklogStageDetailView.as_view(), name="backlog-stage-detail"),
    path("stages/<int:stage_id>/tasks/", BacklogTaskCreateView.as_view(), name="backlog-task-create"),
    path("stages/<int:stage_id>/tasks/reorder/", BacklogTaskReorderView.as_view(), name="backlog-task-reorder"),
    # Задачи
    path("tasks/<int:task_id>/", BacklogTaskDetailView.as_view(), name="backlog-task-detail"),
    path("tasks/<int:task_id>/subtasks/", BacklogSubtaskCreateView.as_view(), name="backlog-subtask-create"),
    path("tasks/<int:task_id>/subtasks/bulk/", BacklogSubtaskBulkCreateView.as_view(), name="backlog-subtask-bulk"),
    path("tasks/<int:task_id>/complete/", BacklogTaskCompleteView.as_view(), name="backlog-task-complete"),
    path("tasks/<int:task_id>/rework/", BacklogTaskReworkView.as_view(), name="backlog-task-rework"),
    path("tasks/<int:task_id>/comments/", BacklogTaskCommentsView.as_view(), name="backlog-task-comments"),
    # Подзадачи
    path("subtasks/<int:subtask_id>/", BacklogSubtaskDetailView.as_view(), name="backlog-subtask-detail"),
    path("subtasks/<int:subtask_id>/works/", BacklogWorkCreateView.as_view(), name="backlog-work-create"),
    path("subtasks/<int:subtask_id>/complete/", BacklogSubtaskCompleteView.as_view(), name="backlog-subtask-complete"),
    path("subtasks/<int:subtask_id>/rework/", BacklogSubtaskReworkView.as_view(), name="backlog-subtask-rework"),
    path("subtasks/<int:subtask_id>/comments/", BacklogSubtaskCommentsView.as_view(), name="backlog-subtask-comments"),
    # Работы, спринты, коды
    path("works/<int:work_id>/", BacklogWorkDetailView.as_view(), name="backlog-work-detail"),
    path("sprints/<int:sprint_id>/", BacklogSprintDetailView.as_view(), name="backlog-sprint-detail"),
    path("by-code/<str:code>/", BacklogByCodeView.as_view(), name="backlog-by-code"),
]
