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

CRM_STAGES = [
    {
        "id": "application-submitted",
        "title": "Прислал заявку",
        "description": "Проектант отправил заявку на мероприятие.",
    },
    {
        "id": "application-testing",
        "title": "Прохождение тестирования",
        "description": "Проектанту отправлено тестирование или заявка ожидает проверки.",
    },
    {
        "id": "application-chat-link-sent",
        "title": "Отправлена ссылка на орг. чат",
        "description": "Проектанту отправлена индивидуальная ссылка на организационный чат.",
    },
    {
        "id": "application-joined-chat",
        "title": "Добавился в орг. чат",
        "description": "Проектант перешел в организационный чат мероприятия.",
    },
    {
        "id": "application-started",
        "title": "Приступил к ПШ",
        "description": "Проектант приступил к проектной школе.",
    },
]

CRM_ROBOTS = [
    {
        "id": "crm-notify-organizer",
        "stageId": "application-submitted",
        "title": "Уведомить организатора",
        "description": "Создает уведомление ответственным организаторам о новой заявке.",
        "action": "notification.organizer",
        "enabled": True,
        "settings": deepcopy(DEFAULT_AUTOMATION_SETTINGS),
        "subject": "Новая заявка: {student}",
        "message": "Проектант {student} отправил заявку на мероприятие «{event}».",
    },
    {
        "id": "crm-send-testing",
        "stageId": "application-testing",
        "title": "Отправить тестирование",
        "description": "Отправляет проектанту уведомление о тестировании.",
        "action": "testing.link",
        "enabled": True,
        "settings": deepcopy(DEFAULT_AUTOMATION_SETTINGS),
        "subject": "Тестирование по заявке",
        "message": "Ваша заявка на мероприятие «{event}» перешла на этап тестирования.",
    },
    {
        "id": "crm-send-chat-link",
        "stageId": "application-chat-link-sent",
        "title": "Отправить ссылку на орг.чат",
        "description": "Отправляет проектанту VK-сообщение со ссылкой на организационный чат.",
        "action": "chat.link.vk",
        "enabled": True,
        "settings": deepcopy(DEFAULT_AUTOMATION_SETTINGS),
        "subject": "Ссылка на организационный чат",
        "message": "Перейдите по индивидуальной ссылке и присоединитесь к организационному чату мероприятия.\n\n{chat_link}",
    },
    {
        "id": "crm-send-planner-invite",
        "stageId": "application-joined-chat",
        "title": "Отправить VK-приглашение в планировщик",
        "description": "Отправляет проектанту VK-сообщение с кнопками принятия или отказа от участия в проектной школе.",
        "action": "planner.invite.vk",
        "enabled": False,
        "settings": deepcopy(DEFAULT_AUTOMATION_SETTINGS),
        "subject": "Переход к работе в планировщике",
        "message": "Набор завершён. Подтвердите, готовы ли вы приступить к работе в планировщике.",
    },
]

CRM_TRIGGERS = [
    {
        "id": "crm-application-created",
        "stageId": "application-submitted",
        "title": "Проектант подал заявку",
        "description": "Отслеживает отправку заявки и перемещает карточку в статус новой заявки.",
        "eventCode": "application.created",
        "enabled": True,
        "settings": deepcopy(DEFAULT_AUTOMATION_SETTINGS),
        "targetStageId": "application-submitted",
        "allowBackTransition": False,
    },
    {
        "id": "crm-testing-started",
        "stageId": "application-testing",
        "title": "Тестирование начато",
        "description": "Срабатывает, когда заявка переходит на этап тестирования.",
        "eventCode": "testing.started",
        "enabled": True,
        "settings": deepcopy(DEFAULT_AUTOMATION_SETTINGS),
        "targetStageId": "application-testing",
        "allowBackTransition": False,
    },
    {
        "id": "crm-chat-link-opened",
        "stageId": "application-joined-chat",
        "title": "Переход по ссылке на орг.чат",
        "description": "Срабатывает, когда проектант переходит по индивидуальной ссылке на орг.чат.",
        "eventCode": "notification.chat_link_opened",
        "enabled": True,
        "settings": deepcopy(DEFAULT_AUTOMATION_SETTINGS),
        "targetStageId": "application-joined-chat",
        "allowBackTransition": False,
    },
]


def create_default_crm_automation_config(event_id: int) -> dict:
    return {
        "scope": "crm",
        "eventId": int(event_id),
        "updatedAt": timezone.now().isoformat(),
        "stages": deepcopy(CRM_STAGES),
        "triggers": deepcopy(CRM_TRIGGERS),
        "robots": deepcopy(CRM_ROBOTS),
    }
