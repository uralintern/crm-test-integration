import type {
  AutomationCommonSettings,
  AutomationConditionGroup,
  AutomationConditionMode,
  AutomationConditionOperator,
  AutomationRunMode,
  AutomationTiming,
} from "../types";

export const DEFAULT_CONDITION: AutomationConditionGroup = {
  mode: "all",
  rules: [],
};

export const DEFAULT_COMMON_SETTINGS: AutomationCommonSettings = {
  runMode: "queue",
  timing: "immediate",
  delayMinutes: 0,
  condition: DEFAULT_CONDITION,
};

export const RUN_MODE_OPTIONS: Array<{ value: AutomationRunMode; label: string }> = [
  { value: "queue", label: "После предыдущих" },
  { value: "parallel", label: "Независимо" },
];

export const TIMING_OPTIONS: Array<{ value: AutomationTiming; label: string }> = [
  { value: "immediate", label: "Сразу" },
  { value: "delayed", label: "Через время" },
];

export const CONDITION_MODE_OPTIONS: Array<{ value: AutomationConditionMode; label: string }> = [
  { value: "all", label: "Все условия" },
  { value: "any", label: "Любое условие" },
];

export const CONDITION_FIELD_OPTIONS = [
  { value: "status", label: "Статус" },
  { value: "event", label: "Мероприятие" },
  { value: "direction", label: "Направление" },
  { value: "project", label: "Проект" },
  { value: "specialization", label: "Специализация" },
  { value: "university", label: "Университет" },
  { value: "course", label: "Курс" },
  { value: "vk", label: "Аккаунт VK" },
  { value: "application_date", label: "Дата подачи заявки" },
  { value: "testing_result", label: "Результат тестирования" },
  { value: "responsible", label: "Ответственный" },
  { value: "task_type", label: "Тип задачи" },
  { value: "task_status", label: "Статус задачи" },
  { value: "team", label: "Команда" },
  { value: "curator", label: "Куратор" },
  { value: "assignee", label: "Исполнитель" },
  { value: "deadline", label: "Дедлайн" },
  { value: "in_sprint", label: "В спринте" },
  { value: "active_task_count", label: "Активных задач" },
  { value: "inactive_days", label: "Дней без движения" },
  { value: "member_id", label: "Участник" },
  { value: "deadline_changed", label: "Дедлайн изменен" },
];

export const CONDITION_OPERATOR_OPTIONS: Array<{ value: AutomationConditionOperator; label: string }> = [
  { value: "equals", label: "равно" },
  { value: "not_equals", label: "не равно" },
  { value: "contains", label: "содержит" },
  { value: "not_contains", label: "не содержит" },
  { value: "filled", label: "заполнено" },
  { value: "empty", label: "не заполнено" },
  { value: "greater_or_equal", label: "больше или равно" },
  { value: "less_or_equal", label: "меньше или равно" },
  { value: "in_range", label: "в диапазоне" },
];
