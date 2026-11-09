"""Чтение бэклога: запросы к БД и вычисляемые поля.

Число запросов не зависит от количества строк: этапы, задачи и подзадачи
загружаются тремя запросами, счётчики работ считаются в БД.
"""

from dataclasses import dataclass, field
from datetime import date

from django.db.models import Count, Prefetch, Q
from django.utils import timezone

from .filters import SPRINT_NONE, BacklogFilters
from .models import BacklogSprint, BacklogStage, BacklogSubtask, BacklogTask
from .statuses import KANBAN_STATUSES, BacklogStatus


@dataclass
class SubtaskNode:
    subtask: BacklogSubtask
    is_overdue: bool

    @property
    def progress(self) -> dict:
        return {"done": self.subtask.work_done, "total": self.subtask.work_total}


@dataclass
class TaskNode:
    task: BacklogTask
    subtasks: list[SubtaskNode]
    start_date: date
    end_date: date
    start_date_is_auto: bool
    end_date_is_auto: bool
    executors: list
    progress: dict
    is_overdue: bool
    visible_subtasks: list[SubtaskNode] = field(default_factory=list)


@dataclass
class StageNode:
    stage: BacklogStage
    tasks: list[TaskNode]


# --- запросы -----------------------------------------------------------------


def subtask_queryset():
    return BacklogSubtask.objects.select_related(
        "executor__crm_profile", "created_by__crm_profile", "sprint", "rework_of"
    ).annotate(
        work_total=Count("work_items", distinct=True),
        work_done=Count("work_items", filter=Q(work_items__is_done=True), distinct=True),
    )


def task_queryset():
    return BacklogTask.objects.select_related(
        "stage", "responsible__crm_profile", "created_by__crm_profile", "sprint", "rework_of"
    ).prefetch_related(Prefetch("subtasks", queryset=subtask_queryset()))


# --- вычисляемые поля ----------------------------------------------------------


def _is_overdue(end_date: date, status: str, today: date) -> bool:
    return status != BacklogStatus.DONE and end_date < today


def effective_task_dates(task: BacklogTask, subtasks) -> tuple[date, date, bool, bool]:
    """Сроки задачи по правилам «Карточек» §4.

    Без подзадач — ручные даты. С подзадачами начало = самое раннее начало подзадач;
    окончание остаётся ручным, пока подзадачи в него укладываются, иначе — самое позднее окончание.
    """
    if not subtasks:
        return task.start_date, task.end_date, False, False
    start = min(subtask.start_date for subtask in subtasks)
    latest_end = max(subtask.end_date for subtask in subtasks)
    end_is_auto = latest_end > task.end_date
    return start, (latest_end if end_is_auto else task.end_date), True, end_is_auto


def _unique_executors(subtasks) -> list:
    executors, seen = [], set()
    for subtask in subtasks:
        if subtask.executor_id and subtask.executor_id not in seen:
            seen.add(subtask.executor_id)
            executors.append(subtask.executor)
    return executors


def build_task_node(task: BacklogTask, today: date) -> TaskNode:
    subtasks = list(task.subtasks.all())
    start, end, start_auto, end_auto = effective_task_dates(task, subtasks)
    subtask_nodes = [SubtaskNode(subtask, _is_overdue(subtask.end_date, subtask.status, today)) for subtask in subtasks]
    return TaskNode(
        task=task,
        subtasks=subtask_nodes,
        start_date=start,
        end_date=end,
        start_date_is_auto=start_auto,
        end_date_is_auto=end_auto,
        executors=_unique_executors(subtasks),
        progress={
            "done": sum(1 for subtask in subtasks if subtask.status == BacklogStatus.DONE),
            "total": len(subtasks),
        },
        is_overdue=_is_overdue(end, task.status, today),
        visible_subtasks=subtask_nodes,
    )


# --- фильтры -------------------------------------------------------------------


def _text_matches(query: str, *values) -> bool:
    needle = query.lower()
    return any(needle in (value or "").lower() for value in values)


def _overlaps(start: date, end: date, filters: BacklogFilters) -> bool:
    if filters.date_from and end < filters.date_from:
        return False
    if filters.date_to and start > filters.date_to:
        return False
    return True


def _sprint_matches(sprint_id, filters: BacklogFilters) -> bool:
    if filters.sprint is None:
        return True
    if filters.sprint == SPRINT_NONE:
        return sprint_id is None
    return sprint_id == filters.sprint


def _task_matches_itself(node: TaskNode, filters: BacklogFilters) -> bool:
    task = node.task
    return (
        filters.executor_id is None  # у задачи нет исполнителя — по исполнителю ищутся подзадачи
        and (filters.responsible_id is None or task.responsible_id == filters.responsible_id)
        and (not filters.statuses or task.status in filters.statuses)
        and _sprint_matches(task.sprint_id, filters)
        and _overlaps(node.start_date, node.end_date, filters)
        and (not filters.query or _text_matches(filters.query, task.title, task.description, task.code))
    )


def _subtask_matches(task: BacklogTask, subtask: BacklogSubtask, filters: BacklogFilters) -> bool:
    return (
        (filters.responsible_id is None or task.responsible_id == filters.responsible_id)
        and (filters.executor_id is None or subtask.executor_id == filters.executor_id)
        and (not filters.statuses or subtask.status in filters.statuses)
        and _sprint_matches(subtask.sprint_id, filters)
        and _overlaps(subtask.start_date, subtask.end_date, filters)
        and (not filters.query or _text_matches(filters.query, subtask.title, subtask.description, subtask.code))
    )


def _apply_filters(stage_nodes: list[StageNode], filters: BacklogFilters) -> list[StageNode]:
    """Оставляет подходящие объекты и их родителей (контекст), остальное скрывает."""
    if filters.is_empty:
        return stage_nodes
    result = []
    for stage_node in stage_nodes:
        visible_tasks = []
        for node in stage_node.tasks:
            matching = [sub for sub in node.subtasks if _subtask_matches(node.task, sub.subtask, filters)]
            if matching or _task_matches_itself(node, filters):
                node.visible_subtasks = matching
                visible_tasks.append(node)
        stage = stage_node.stage
        stage_matches = filters.only_text_query and _text_matches(filters.query, stage.title, stage.description)
        if visible_tasks or stage_matches:
            result.append(StageNode(stage=stage, tasks=visible_tasks))
    return result


# --- публичные функции -----------------------------------------------------------


def build_team_backlog(team_id: int, filters: BacklogFilters, today: date | None = None) -> list[StageNode]:
    today = today or timezone.localdate()
    stages = list(BacklogStage.objects.filter(team_id=team_id).select_related("created_by__crm_profile"))
    nodes_by_stage = {stage.id: [] for stage in stages}
    for task in task_queryset().filter(team_id=team_id):
        nodes_by_stage.setdefault(task.stage_id, []).append(build_task_node(task, today))
    stage_nodes = [StageNode(stage=stage, tasks=nodes_by_stage[stage.id]) for stage in stages]
    return _apply_filters(stage_nodes, filters)


def get_task_node(task_id: int, today: date | None = None) -> TaskNode | None:
    task = task_queryset().filter(pk=task_id).first()
    return build_task_node(task, today or timezone.localdate()) if task else None


def subtask_nodes(subtask_ids: list[int], today: date | None = None) -> list[SubtaskNode]:
    """Несколько подзадач одним запросом, в порядке переданных id."""
    today = today or timezone.localdate()
    by_id = {subtask.id: subtask for subtask in subtask_queryset().filter(pk__in=subtask_ids)}
    return [
        SubtaskNode(by_id[pk], _is_overdue(by_id[pk].end_date, by_id[pk].status, today))
        for pk in subtask_ids
        if pk in by_id
    ]


def get_subtask_node(subtask_id: int, today: date | None = None) -> SubtaskNode | None:
    subtask = (
        subtask_queryset()
        .select_related("task__responsible__crm_profile")
        .prefetch_related("work_items")
        .filter(pk=subtask_id)
        .first()
    )
    if subtask is None:
        return None
    return SubtaskNode(subtask, _is_overdue(subtask.end_date, subtask.status, today or timezone.localdate()))


def team_sprints(team_id: int) -> list[BacklogSprint]:
    return list(BacklogSprint.objects.filter(team_id=team_id).select_related("created_by__crm_profile"))


def is_current_sprint(sprint: BacklogSprint, today: date) -> bool:
    return sprint.start_date <= today <= sprint.end_date


def current_sprint(team_id: int, today: date | None = None) -> BacklogSprint | None:
    """Спринт, в который попадает сегодняшний день (при пересечении — начавшийся позже)."""
    today = today or timezone.localdate()
    return (
        BacklogSprint.objects.filter(team_id=team_id, start_date__lte=today, end_date__gte=today)
        .order_by("-start_date", "-id")
        .first()
    )


@dataclass
class KanbanColumn:
    status: str
    tasks: list[TaskNode]
    subtasks: list[SubtaskNode]


def build_kanban(sprint: BacklogSprint | None, today: date | None = None) -> list[KanbanColumn]:
    """Задачи и подзадачи спринта в статусах «В спринте» и «На проверке» (BL-28)."""
    today = today or timezone.localdate()
    if sprint is None:
        return [KanbanColumn(status, [], []) for status in KANBAN_STATUSES]
    tasks = [
        build_task_node(task, today)
        for task in task_queryset()
        .filter(sprint=sprint, status__in=KANBAN_STATUSES)
        .order_by("stage__position", "position", "id")
    ]
    subtasks = [
        SubtaskNode(subtask, _is_overdue(subtask.end_date, subtask.status, today))
        for subtask in subtask_queryset()
        .filter(sprint=sprint, status__in=KANBAN_STATUSES)
        .order_by("task__stage__position", "task__position", "position", "id")
    ]
    return [
        KanbanColumn(
            status,
            [node for node in tasks if node.task.status == status],
            [node for node in subtasks if node.subtask.status == status],
        )
        for status in KANBAN_STATUSES
    ]


def find_by_code(code: str):
    """Задача или подзадача по коду без учёта регистра: (тип, объект) или (None, None).

    Коды хранятся в верхнем регистре, поэтому запрос приводится к нему и ищется точным совпадением
    по уникальному индексу; таблица выбирается по префиксу кода.
    """
    normalized = (code or "").strip().upper()
    if normalized.startswith(f"{BacklogTask.CODE_PREFIX}-"):
        task = BacklogTask.objects.filter(code=normalized).only("id", "team_id").first()
        return ("task", task) if task else (None, None)
    if normalized.startswith(f"{BacklogSubtask.CODE_PREFIX}-"):
        subtask = BacklogSubtask.objects.filter(code=normalized).only("id", "team_id").first()
        return ("subtask", subtask) if subtask else (None, None)
    return None, None
