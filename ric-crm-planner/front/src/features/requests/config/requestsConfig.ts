import { REQUEST_STATUS } from "../../../constants/requestProgress";

export const REQUESTS_TEXT = {
  myRequests: "Мои заявки",
  requests: "Заявки",
  list: "Список",
  diagram: "Диаграмма",
  search: "Поиск...",
  studentName: "ФИО студента",
  event: "Мероприятие",
  specialization: "Специализация",
  status: "Статус",
  withdrawRequest: "Отозвать заявку",
  other: "Остальные",
  requestsDiagram: "Диаграмма заявок",
  distribution: "Распределение студентов по текущим статусам",
  total: "всего",
  statusDistribution: "Расклад по статусам",
  circleDiagram: "Круговая",
  lineDiagram: "Линейная",
  statusDisplaySettings: "Настройка отображения статусов",
  statusDisplayDescription:
    "Выбранные статусы отображаются отдельно. Невыбранные статусы попадут в \"Остальные\".",
  selectAllStatuses: "Выбрать все",
  ready: "Готово",
  percentOfTotal: "от общего количества",
  confirmAction: "Подтвердите действие",
  withdrawConfirm: "Вы уверены, что хотите отозвать заявку?",
  cancel: "Отмена",
  withdraw: "Отозвать",
  confirmation: "Подтверждение",
  confirmActionText: "Подтвердите действие.",
  confirm: "Подтвердить",
  allEvents: "Все мероприятия",
  noStudents: "Нет студентов",
  showStudents: "Показать студентов",
  hideStudents: "Скрыть студентов",
  requestNotFound: "Такой заявки не существует!",
} as const;

export const CHART_VIEW_STORAGE_KEY = "requests-chart-view";
export const REQUESTS_VIEW_STORAGE_KEY = "requests-view";
export const DISPLAYED_STATUSES_STORAGE_KEY = "requests-displayed-statuses";
export const DASHBOARD_START_ANGLE = 225;
export const DASHBOARD_SWEEP_ANGLE = 270;
export const OTHER_STATUS_KEY = "other";
export const OTHER_STATUS_COLOR = "#94a3b8";

export const REQUEST_STATUS_COLORS: Record<string, string> = {
  [REQUEST_STATUS.SUBMITTED]: "#2563eb",
  [REQUEST_STATUS.TESTING]: "#0ea5e9",
  [REQUEST_STATUS.CHAT_LINK_SENT]: "#06b6d4",
  [REQUEST_STATUS.JOINED_CHAT]: "#0284c7",
  [REQUEST_STATUS.STARTED]: "#22c55e",
  [REQUEST_STATUS.TESTING_NOT_STARTED]: "#ef4444",
  [REQUEST_STATUS.TESTING_FAILED]: "#ef4444",
  [REQUEST_STATUS.CHAT_NOT_JOINED]: "#ef4444",
  [REQUEST_STATUS.DECLINED_PSH]: "#ef4444",
  [REQUEST_STATUS.REMOVED_FROM_PSH]: "#ef4444",
};
