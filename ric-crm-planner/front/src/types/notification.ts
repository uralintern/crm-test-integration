export interface NotificationItem {
  id: string;
  userId?: number;
  title: string;
  message?: string;
  link?: string;
  createdAt: string;
  read: boolean;
}

export interface CreateNotificationInput {
  userId?: number;
  title: string;
  message?: string;
  link?: string;
}
