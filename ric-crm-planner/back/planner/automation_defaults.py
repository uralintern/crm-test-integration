from copy import deepcopy
from django.utils import timezone


DEFAULT_AUTOMATION_SETTINGS = {
    "runMode": "queue",
    "timing": "immediate",
    "delayMinutes": 0,
    "condition": {
        "mode": "all",
        "rules": [],
    },
}

PLANNER_STAGES = [
    {
        "id": "backlog",
        "title": "Бэклог",
        "description": "Большая задача или подзадача создана, но еще не взята в спринт.",
    },
    {
        "id": "planned",
        "title": "Запланировано",
        "description": "Подзадача добавлена в спринт и ожидает начала работы.",
    },
    {
        "id": "in-progress",
        "title": "В работе",
        "description": "Исполнитель начал выполнение подзадачи.",
    },
    {
        "id": "review",
        "title": "На проверке",
        "description": "Результат готов и ожидает проверки куратором.",
    },
    {
        "id": "done",
        "title": "Готово",
        "description": "Подзадача или большая задача завершена.",
    },
    {
        "id": "risk",
        "title": "Риск по сроку",
        "description": "Задача приближается к дедлайну, просрочена или заблокирована.",
    },
]

PLANNER_ROBOTS = [
    {
        "id": "planner-notify-assignee-planned",
        "stageId": "planned",
        "title": "Уведомить исполнителя о назначении",
        "description": "Отправляет проектанту уведомление, когда подзадача назначена и добавлена в спринт.",
        "action": "notification.assignee",
        "enabled": True,
        "settings": deepcopy(DEFAULT_AUTOMATION_SETTINGS),
        "subject": "Вам назначена задача",
        "message": "Проверьте задачу «{task}», сроки и текущий статус в планировщике.",
    },
    {
        "id": "planner-notify-curator-risk",
        "stageId": "risk",
        "title": "Уведомить куратора о риске",
        "description": "Сообщает куратору, что задача близка к дедлайну, просрочена или заблокирована.",
        "action": "notification.curator",
        "enabled": True,
        "settings": deepcopy(DEFAULT_AUTOMATION_SETTINGS),
        "subject": "Риск по сроку задачи",
        "message": "Задача «{task}» требует внимания. Статус: {status}.",
    },
    {
        "id": "planner-create-review-task",
        "stageId": "review",
        "title": "Поставить проверку куратору",
        "description": "Создает действие для проверки результата, когда задача перешла на стадию проверки.",
        "action": "task.review",
        "enabled": True,
        "settings": deepcopy(DEFAULT_AUTOMATION_SETTINGS),
        "subject": "Проверить результат",
        "message": "Исполнитель перевел задачу «{task}» на проверку.",
    },
    {
        "id": "planner-notify-team-done",
        "stageId": "done",
        "title": "Уведомить команду о завершении",
        "description": "Отправляет уведомление после завершения задачи.",
        "action": "notification.assignee",
        "enabled": True,
        "settings": deepcopy(DEFAULT_AUTOMATION_SETTINGS),
        "subject": "Задача завершена",
        "message": "Задача «{task}» отмечена как готовая.",
    },
    {
        "id": "planner-remove-done-from-sprint",
        "stageId": "done",
        "title": "Убрать готовые задачи из спринта",
        "description": (
            "В начале новой недели убирает из спринта подзадачи, оставшиеся в статусе «Готово». "
            "Задачи остаются в бэклоге и пропадают с канбана."
        ),
        "action": "sprint.remove_done",
        "enabled": True,
        "settings": deepcopy(DEFAULT_AUTOMATION_SETTINGS),
        "subject": "Задача убрана из спринта",
        "message": "Задача «{task}» завершена и убрана из спринта по итогам недели.",
    },
]

PLANNER_TRIGGERS = [
    {
        "id": "planner-subtask-added-to-sprint",
        "stageId": "planned",
        "title": "Подзадача добавлена в спринт",
        "description": "Когда подзадачу включили в спринт, триггер переводит ее в плановую стадию.",
        "eventCode": "task.sprint_added",
        "enabled": True,
        "settings": deepcopy(DEFAULT_AUTOMATION_SETTINGS),
        "targetStageId": "planned",
        "allowBackTransition": False,
    },
    {
        "id": "planner-task-started",
        "stageId": "in-progress",
        "title": "Исполнитель начал работу",
        "description": "Когда статус меняется на «В работе», триггер переводит задачу в активную стадию.",
        "eventCode": "task.status_started",
        "enabled": True,
        "settings": deepcopy(DEFAULT_AUTOMATION_SETTINGS),
        "targetStageId": "in-progress",
        "allowBackTransition": False,
    },
    {
        "id": "planner-task-review",
        "stageId": "review",
        "title": "Задача отправлена на проверку",
        "description": "Когда исполнитель переводит задачу на проверку, триггер переносит ее в стадию проверки.",
        "eventCode": "task.review_requested",
        "enabled": True,
        "settings": deepcopy(DEFAULT_AUTOMATION_SETTINGS),
        "targetStageId": "review",
        "allowBackTransition": False,
    },
    {
        "id": "planner-task-done",
        "stageId": "done",
        "title": "Задача завершена",
        "description": "Когда задача получила финальный статус, триггер переносит ее в завершенную стадию.",
        "eventCode": "task.status_done",
        "enabled": True,
        "settings": deepcopy(DEFAULT_AUTOMATION_SETTINGS),
        "targetStageId": "done",
        "allowBackTransition": False,
    },
    {
        "id": "planner-deadline-risk",
        "stageId": "risk",
        "title": "До дедлайна остался один день",
        "description": "Отслеживает приближение крайнего срока и переносит задачу в стадию риска.",
        "eventCode": "task.deadline_soon",
        "enabled": True,
        "settings": deepcopy(DEFAULT_AUTOMATION_SETTINGS),
        "targetStageId": "risk",
        "allowBackTransition": False,
    },
]


def create_default_planner_automation_config(event_id: int) -> dict:
    return {
        "scope": "planner",
        "eventId": int(event_id),
        "updatedAt": timezone.now().isoformat(),
        "stages": deepcopy(PLANNER_STAGES),
        "triggers": deepcopy(PLANNER_TRIGGERS),
        "robots": deepcopy(PLANNER_ROBOTS),
    }
