import { REQUEST_STATUS } from "../../../constants/requestProgress";
import type {
  AutomationCommonSettings,
  AutomationRobot,
  AutomationScope,
  AutomationStage,
  AutomationTrigger,
} from "../types";

export const DEFAULT_SETTINGS: AutomationCommonSettings = {
  runMode: "queue",
  timing: "immediate",
  delayMinutes: 0,
  condition: {
    mode: "all",
    rules: [],
  },
};

const APPLICATION_STAGES: AutomationStage[] = [
  {
    id: "application-submitted",
    title: REQUEST_STATUS.SUBMITTED,
    description: "Проектант отправил заявку на мероприятие.",
  },
  {
    id: "application-testing",
    title: REQUEST_STATUS.TESTING,
    description: "Проектанту отправлено тестирование или заявка ожидает проверки.",
  },
  {
    id: "application-chat-link-sent",
    title: REQUEST_STATUS.CHAT_LINK_SENT,
    description: "Проектанту отправлена индивидуальная ссылка на организационный чат.",
  },
  {
    id: "application-joined-chat",
    title: REQUEST_STATUS.JOINED_CHAT,
    description: "Проектант перешел в организационный чат мероприятия.",
  },
  {
    id: "application-started",
    title: REQUEST_STATUS.STARTED,
    description: "Проектант приступил к проектной школе.",
  },
];

export const STAGE_TEMPLATES: Record<AutomationScope, AutomationStage[]> = {
  crm: APPLICATION_STAGES,
  planner: [
    {
      id: "backlog",
      title: "Бэклог",
      description: "Большая задача или подзадача создана, но еще не взята в спринт.",
    },
    {
      id: "planned",
      title: "Запланировано",
      description: "Подзадача добавлена в спринт и ожидает начала работы.",
    },
    {
      id: "in-progress",
      title: "В работе",
      description: "Исполнитель начал выполнение подзадачи.",
    },
    {
      id: "review",
      title: "На проверке",
      description: "Результат готов и ожидает проверки куратором.",
    },
    {
      id: "done",
      title: "Готово",
      description: "Подзадача или большая задача завершена.",
    },
    {
      id: "risk",
      title: "Риск по сроку",
      description: "Задача приближается к дедлайну, просрочена или заблокирована.",
    },
  ],
  requests: APPLICATION_STAGES,
};

export const ROBOT_TEMPLATES: Record<AutomationScope, Array<Omit<AutomationRobot, "enabled" | "settings">>> = {
  crm: [
    {
      id: "crm-notify-organizer",
      stageId: "application-submitted",
      title: "Уведомить организатора",
      description: "Создает уведомление ответственным организаторам о новой заявке.",
      action: "notification.organizer",
      subject: "Новая заявка в CRM",
      message: "Проектант отправил заявку. Проверьте карточку и выберите следующий статус.",
    },
    {
      id: "crm-send-testing",
      stageId: "application-testing",
      title: "Отправить тестирование",
      description: "Отправляет проектанту ссылку на модуль тестирования.",
      action: "testing.link",
      subject: "Тестирование по заявке",
      message: "Ваша заявка перешла на этап тестирования. Откройте ссылку и выполните задание.",
    },
    {
      id: "crm-send-chat-link",
      stageId: "application-chat-link-sent",
      title: "Отправить ссылку на орг.чат",
      description: "Отправляет проектанту уведомление или сообщение VK со ссылкой на организационный чат.",
      action: "chat.link.vk",
      subject: "Ссылка на организационный чат",
      message: "Перейдите по ссылке и присоединитесь к организационному чату мероприятия.",
    },
  ],
  planner: [
    {
      id: "planner-notify-assignee-planned",
      stageId: "planned",
      title: "Уведомить исполнителя о назначении",
      description: "Отправляет проектанту уведомление, когда подзадача назначена и добавлена в спринт.",
      action: "notification.assignee",
      subject: "Вам назначена задача",
      message: "Проверьте описание, сроки и ответственного по задаче в планировщике.",
    },
    {
      id: "planner-notify-curator-risk",
      stageId: "risk",
      title: "Уведомить куратора о риске",
      description: "Сообщает куратору, что задача близка к дедлайну, просрочена или заблокирована.",
      action: "notification.curator",
      subject: "Риск по сроку задачи",
      message: "Задача требует внимания: проверьте срок, статус и назначенного исполнителя.",
    },
    {
      id: "planner-create-review-task",
      stageId: "review",
      title: "Поставить проверку куратору",
      description: "Создает действие для проверки результата, когда задача перешла на стадию проверки.",
      action: "task.review",
      subject: "Проверить результат",
      message: "Исполнитель перевел задачу на проверку. Проверьте результат и оставьте обратную связь.",
    },
    {
      id: "planner-notify-team-done",
      stageId: "done",
      title: "Уведомить команду о завершении",
      description: "Отправляет уведомление после завершения задачи или набора подзадач.",
      action: "notification.assignee",
      subject: "Задача завершена",
      message: "Задача отмечена как готовая. Проверьте итоговый статус в планировщике.",
    },
  ],
  requests: [
    {
      id: "request-notify-organizer",
      stageId: "application-submitted",
      title: "Уведомить организатора",
      description: "Создает уведомление о новой заявке и прикладывает ссылку на карточку.",
      action: "notification.organizer",
      subject: "Новая заявка",
      message: "Проектант отправил заявку. Проверьте карточку и выберите следующий статус.",
    },
    {
      id: "request-send-testing",
      stageId: "application-testing",
      title: "Отправить тестирование",
      description: "Отправляет проектанту ссылку на модуль тестирования.",
      action: "testing.link",
      subject: "Тестирование по заявке",
      message: "Ваша заявка перешла на этап тестирования. Откройте ссылку и выполните задание.",
    },
    {
      id: "request-send-chat-link",
      stageId: "application-chat-link-sent",
      title: "Отправить ссылку на орг.чат",
      description: "Отправляет проектанту ссылку на организационный чат.",
      action: "chat.link.vk",
      subject: "Ссылка на организационный чат",
      message: "Перейдите по ссылке и присоединитесь к организационному чату мероприятия.",
    },
  ],
};

export const TRIGGER_TEMPLATES: Record<
  AutomationScope,
  Array<Omit<AutomationTrigger, "enabled" | "settings" | "allowBackTransition">>
> = {
  crm: [
    {
      id: "crm-application-created",
      stageId: "application-submitted",
      title: "Проектант подал заявку",
      description: "Отслеживает отправку заявки и перемещает карточку в статус новой заявки.",
      eventCode: "application.created",
      targetStageId: "application-submitted",
    },
    {
      id: "crm-testing-started",
      stageId: "application-testing",
      title: "Тестирование начато",
      description: "Срабатывает, когда проектант открывает или начинает тестирование.",
      eventCode: "testing.started",
      targetStageId: "application-testing",
    },
    {
      id: "crm-chat-link-opened",
      stageId: "application-joined-chat",
      title: "Переход по ссылке на орг.чат",
      description: "Срабатывает, когда проектант переходит по индивидуальной ссылке на орг.чат.",
      eventCode: "notification.chat_link_opened",
      targetStageId: "application-joined-chat",
    },
  ],
  planner: [
    {
      id: "planner-subtask-added-to-sprint",
      stageId: "planned",
      title: "Подзадача добавлена в спринт",
      description: "Когда подзадачу включили в спринт, триггер переводит ее в плановую стадию.",
      eventCode: "task.sprint_added",
      targetStageId: "planned",
    },
    {
      id: "planner-task-started",
      stageId: "in-progress",
      title: "Исполнитель начал работу",
      description: "Когда статус меняется на «В работе», триггер переводит задачу в активную стадию.",
      eventCode: "task.status_started",
      targetStageId: "in-progress",
    },
    {
      id: "planner-task-review",
      stageId: "review",
      title: "Задача отправлена на проверку",
      description: "Когда исполнитель переводит задачу на проверку, триггер переносит ее в стадию проверки.",
      eventCode: "task.review_requested",
      targetStageId: "review",
    },
    {
      id: "planner-task-done",
      stageId: "done",
      title: "Задача завершена",
      description: "Когда задача получила финальный статус, триггер переносит ее в завершенную стадию.",
      eventCode: "task.status_done",
      targetStageId: "done",
    },
    {
      id: "planner-deadline-risk",
      stageId: "risk",
      title: "До дедлайна остался один день",
      description: "Отслеживает приближение крайнего срока и переносит задачу в стадию риска.",
      eventCode: "task.deadline_soon",
      targetStageId: "risk",
    },
  ],
  requests: [
    {
      id: "request-application-created",
      stageId: "application-submitted",
      title: "Проектант подал заявку",
      description: "Отслеживает отправку заявки и перемещает карточку в стадию новой заявки.",
      eventCode: "application.created",
      targetStageId: "application-submitted",
    },
    {
      id: "request-testing-started",
      stageId: "application-testing",
      title: "Тестирование начато",
      description: "Отслеживает начало тестирования проектантом.",
      eventCode: "testing.started",
      targetStageId: "application-testing",
    },
    {
      id: "request-chat-link-opened",
      stageId: "application-joined-chat",
      title: "Переход по ссылке на орг.чат",
      description: "Когда проектант открыл ссылку на орг.чат, карточка переходит на стадию подтверждения.",
      eventCode: "notification.chat_link_opened",
      targetStageId: "application-joined-chat",
    },
  ],
};
