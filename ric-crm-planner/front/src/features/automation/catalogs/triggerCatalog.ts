import type { AutomationScope, CatalogGroup } from "../types";

export const TRIGGER_CATALOG: Record<AutomationScope, CatalogGroup[]> = {
  crm: [
    {
      title: "Действия проектанта",
      items: [
        {
          code: "application.created",
          title: "Проектант подал заявку",
          description: "Срабатывает после отправки заявки на мероприятие.",
        },
        {
          code: "notification.link_opened",
          title: "Переход по ссылке",
          description: "Срабатывает после перехода по ссылке из уведомления.",
        },
        {
          code: "testing.started",
          title: "Тестирование начато",
          description: "Срабатывает, когда проектант открыл или начал тестирование.",
        },
        {
          code: "testing.completed",
          title: "Тестирование завершено",
          description: "Срабатывает, когда проектант завершил тестирование.",
        },
      ],
    },
    {
      title: "Изменения карточки",
      items: [
        {
          code: "request.status_changed",
          title: "Статус изменен",
          description: "Срабатывает при ручном изменении статуса заявки.",
        },
        {
          code: "field.changed",
          title: "Поле изменено",
          description: "Срабатывает после изменения выбранного поля карточки.",
        },
      ],
    },
  ],
  planner: [
    {
      title: "Жизненный цикл задачи",
      items: [
        {
          code: "task.created",
          title: "Задача создана",
          description: "Срабатывает после создания большой задачи или подзадачи.",
        },
        {
          code: "task.sprint_added",
          title: "Подзадача добавлена в спринт",
          description: "Срабатывает, когда подзадачу включили в спринт и она появилась в канбане.",
        },
        {
          code: "task.assignee_changed",
          title: "Изменен исполнитель",
          description: "Срабатывает при назначении или смене ответственного за задачу.",
        },
        {
          code: "task.status_changed",
          title: "Статус задачи изменен",
          description: "Срабатывает при любой смене статуса задачи в канбане.",
        },
        {
          code: "task.unassigned",
          title: "Задача без исполнителя",
          description: "Срабатывает, если задача или подзадача находится в работе без назначенного исполнителя.",
        },
        {
          code: "task.subtask_changed",
          title: "Изменилась подзадача",
          description: "Срабатывает при изменении названия, исполнителя, сроков или параметров подзадачи.",
        },
        {
          code: "task.deadline_changed",
          title: "Изменился дедлайн",
          description: "Срабатывает при изменении крайнего срока задачи или подзадачи.",
        },
      ],
    },
    {
      title: "Сроки и контроль",
      items: [
        {
          code: "task.deadline_soon",
          title: "Скоро дедлайн",
          description: "Срабатывает за выбранное время до крайнего срока.",
        },
        {
          code: "task.overdue",
          title: "Задача просрочена",
          description: "Срабатывает, если крайний срок прошел, а задача не завершена.",
        },
        {
          code: "task.review_requested",
          title: "Задача отправлена на проверку",
          description: "Срабатывает при переходе задачи на стадию проверки.",
        },
        {
          code: "task.stale",
          title: "Задача долго без движения",
          description: "Срабатывает, если активная задача несколько дней не обновлялась.",
        },
        {
          code: "task.status_done",
          title: "Задача завершена",
          description: "Срабатывает, когда задача переходит в финальный статус.",
        },
      ],
    },
    {
      title: "Команда",
      items: [
        {
          code: "team.confirmed",
          title: "Команда подтверждена",
          description: "Срабатывает после подтверждения состава команды организатором.",
        },
        {
          code: "team.curator_assigned",
          title: "Куратор назначен",
          description: "Срабатывает после назначения или смены куратора команды.",
        },
        {
          code: "member.overloaded",
          title: "Участник перегружен",
          description: "Срабатывает, когда у участника слишком много активных задач.",
        },
        {
          code: "member.idle",
          title: "Участник без задач",
          description: "Срабатывает, когда участник подтвержденной команды не имеет активных задач.",
        },
      ],
    },
  ],
  requests: [
    {
      title: "Заявки",
      items: [
        {
          code: "application.created",
          title: "Проектант подал заявку",
          description: "Срабатывает после отправки заявки.",
        },
        {
          code: "testing.started",
          title: "Тестирование начато",
          description: "Срабатывает после начала тестирования проектантом.",
        },
        {
          code: "notification.chat_link_opened",
          title: "Переход по ссылке на орг.чат",
          description: "Срабатывает после перехода по индивидуальной ссылке.",
        },
      ],
    },
  ],
};
