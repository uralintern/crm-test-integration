import type { CreateNotificationInput, NotificationItem } from "../types/notification";

export const LS_NOTIFICATIONS = "ric_notifications_v1";
export const NOTIFICATIONS_CHANGED_EVENT = "notifications:changed";

function readLS<T>(key: string, fallback: T): T {
  const raw = localStorage.getItem(key);
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function nextId() {
  return `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function emitNotificationsChanged(items: NotificationItem[]) {
  window.dispatchEvent(new CustomEvent(NOTIFICATIONS_CHANGED_EVENT, { detail: items }));
}

export function readNotifications(): NotificationItem[] {
  return readLS<NotificationItem[]>(LS_NOTIFICATIONS, []);
}

export function writeNotifications(items: NotificationItem[]) {
  localStorage.setItem(LS_NOTIFICATIONS, JSON.stringify(items));
  emitNotificationsChanged(items);
}

export function pushNotification(input: CreateNotificationInput): NotificationItem {
  const created: NotificationItem = {
    id: nextId(),
    userId: input.userId,
    title: input.title,
    message: input.message,
    link: input.link,
    createdAt: new Date().toISOString(),
    read: false,
  };

  writeNotifications([created, ...readNotifications()]);
  return created;
}

export function pushNotifications(inputs: CreateNotificationInput[]) {
  const created = inputs.map<NotificationItem>((input) => ({
    id: nextId(),
    userId: input.userId,
    title: input.title,
    message: input.message,
    link: input.link,
    createdAt: new Date().toISOString(),
    read: false,
  }));

  if (created.length > 0) writeNotifications([...created, ...readNotifications()]);
  return created;
}
