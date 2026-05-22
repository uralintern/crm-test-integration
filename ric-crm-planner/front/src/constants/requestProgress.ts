export const REQUEST_STATUS = {
  SUBMITTED: "Прислал заявку",
  TESTING: "Прохождение тестирования",
  TESTING_NOT_STARTED: "Не перешёл к тестированию",
  TESTING_FAILED: "Не прошел тестирование",
  CHAT_LINK_SENT: "Отправлена ссылка на орг. чат",
  CHAT_NOT_JOINED: "Не добавился в орг чат",
  JOINED_CHAT: "Добавился в орг. чат",
  STARTED: "Приступил к ПШ",
  DECLINED_PSH: "Отказался от ПШ",
  REMOVED_FROM_PSH: "Удален с ПШ",
} as const;

export const ORGANIZER_REQUEST_STATUSES = [
  REQUEST_STATUS.SUBMITTED,
  REQUEST_STATUS.TESTING,
  REQUEST_STATUS.TESTING_NOT_STARTED,
  REQUEST_STATUS.TESTING_FAILED,
  REQUEST_STATUS.CHAT_LINK_SENT,
  REQUEST_STATUS.CHAT_NOT_JOINED,
  REQUEST_STATUS.JOINED_CHAT,
  REQUEST_STATUS.STARTED,
  REQUEST_STATUS.DECLINED_PSH,
  REQUEST_STATUS.REMOVED_FROM_PSH,
];

export const NEGATIVE_REQUEST_STATUSES = [
  REQUEST_STATUS.TESTING_NOT_STARTED,
  REQUEST_STATUS.TESTING_FAILED,
  REQUEST_STATUS.CHAT_NOT_JOINED,
  REQUEST_STATUS.DECLINED_PSH,
  REQUEST_STATUS.REMOVED_FROM_PSH,
];

export const NON_WITHDRAWABLE_REQUEST_STATUSES = [
  REQUEST_STATUS.STARTED,
  ...NEGATIVE_REQUEST_STATUSES,
];

export function isNegativeRequestStatus(status?: string) {
  const normalizedStatus = String(status || "").trim().toLowerCase();
  return NEGATIVE_REQUEST_STATUSES.some((item) => item.toLowerCase() === normalizedStatus);
}

export function canWithdrawRequestStatus(status?: string) {
  const normalizedStatus = String(status || "").trim().toLowerCase();
  return !NON_WITHDRAWABLE_REQUEST_STATUSES.some((item) => item.toLowerCase() === normalizedStatus);
}

export type RequestTransitionSource = "testing" | "chat" | "start";

export function buildMockRequestTransitionUrl(
  requestId: number,
  targetStatus: string,
  source: RequestTransitionSource
) {
  const url = new URL("/requests", window.location.origin);
  url.searchParams.set("requestAction", "progress");
  url.searchParams.set("requestId", String(requestId));
  url.searchParams.set("targetStatus", targetStatus);
  url.searchParams.set("source", source);
  return url.toString();
}

export function getRequestTransitionCopy(source: RequestTransitionSource, targetStatus: string) {
  if (source === "testing") {
    return {
      title: "Подтверждение перехода",
      message: `Подтвердить завершение тестирования и перевод заявки в статус "${targetStatus}"?`,
    };
  }

  if (source === "chat") {
    return {
      title: "Подтверждение перехода",
      message: `Подтвердить переход в организационный чат и перевод заявки в статус "${targetStatus}"?`,
    };
  }

  return {
    title: "Подтверждение перехода",
    message: `Подтвердить перевод заявки в статус "${targetStatus}"?`,
  };
}

