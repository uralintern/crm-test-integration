import client from "./client";
import type { CreateNotificationInput, NotificationItem } from "../types/notification";

type BackendNotification = {
  id: number | string;
  userId?: number | string;
  user?: number | string;
  title: string;
  message?: string;
  link?: string;
  read?: boolean;
  createdAt?: string;
  created_at?: string;
};

function mapNotification(item: BackendNotification): NotificationItem {
  return {
    id: String(item.id),
    userId:
      typeof item.userId !== "undefined"
        ? Number(item.userId)
        : typeof item.user !== "undefined"
          ? Number(item.user)
          : undefined,
    title: item.title,
    message: item.message,
    link: item.link,
    createdAt: item.createdAt ?? item.created_at ?? new Date().toISOString(),
    read: Boolean(item.read),
  };
}

export async function getNotifications(): Promise<NotificationItem[]> {
  const raw = await client.get<BackendNotification[]>("/api/users/notifications/");
  return Array.isArray(raw) ? raw.map(mapNotification) : [];
}

export async function createNotification(input: CreateNotificationInput): Promise<NotificationItem> {
  const created = await client.post<BackendNotification>("/api/users/notifications/", {
    userId: input.userId,
    title: input.title,
    message: input.message ?? "",
    link: input.link ?? "",
  });
  return mapNotification(created);
}

export async function markNotificationAsRead(id: string): Promise<void> {
  await client.patch(`/api/users/notifications/${Number(id)}/`, { read: true });
}

export async function markAllNotificationsAsRead(): Promise<void> {
  await client.post("/api/users/notifications/mark-all-read/", {});
}

export async function deleteNotification(id: string): Promise<void> {
  await client.del(`/api/users/notifications/${Number(id)}/`);
}

export async function clearNotifications(): Promise<void> {
  await client.del("/api/users/notifications/clear/");
}
