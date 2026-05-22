import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  clearNotifications as clearBackendNotifications,
  createNotification as createBackendNotification,
  deleteNotification as deleteBackendNotification,
  getNotifications as getBackendNotifications,
  markAllNotificationsAsRead as markAllBackendNotificationsAsRead,
  markNotificationAsRead as markBackendNotificationAsRead,
} from "../api/notifications";
import client from "../api/client";
import {
  LS_NOTIFICATIONS,
  NOTIFICATIONS_CHANGED_EVENT,
  pushNotification,
  readNotifications,
} from "../storage/notifications";
import type { CreateNotificationInput, NotificationItem } from "../types/notification";
import { AuthContext } from "./AuthContext";

interface NotificationsContextType {
  notifications: NotificationItem[];
  unreadCount: number;
  addNotification: (input: CreateNotificationInput) => void;
  markAllAsRead: () => void;
  markAsRead: (id: string) => void;
  removeNotification: (id: string) => void;
  clearNotifications: () => void;
}

const NotificationsContext = createContext<NotificationsContextType | null>(null);

function shouldUseBackendNotifications(isAuthenticated: boolean) {
  return isAuthenticated && !client.USE_MOCK;
}

export function NotificationsProvider({ children }: { children: ReactNode }) {
  const { user } = useContext(AuthContext);
  const [items, setItems] = useState<NotificationItem[]>(() => readNotifications());

  useEffect(() => {
    localStorage.setItem(LS_NOTIFICATIONS, JSON.stringify(items));
  }, [items]);

  useEffect(() => {
    if (!client.USE_MOCK) return;

    const syncNotifications = () => {
      setItems(readNotifications());
    };

    window.addEventListener(NOTIFICATIONS_CHANGED_EVENT, syncNotifications);
    window.addEventListener("storage", syncNotifications);
    return () => {
      window.removeEventListener(NOTIFICATIONS_CHANGED_EVENT, syncNotifications);
      window.removeEventListener("storage", syncNotifications);
    };
  }, []);

  useEffect(() => {
    if (!user || !shouldUseBackendNotifications(Boolean(user))) return;

    let cancelled = false;
    void getBackendNotifications()
      .then((loaded) => {
        if (!cancelled) setItems(loaded);
      })
      .catch(() => {
        if (!cancelled) setItems([]);
      });

    return () => {
      cancelled = true;
    };
  }, [user]);

  const notifications = useMemo(() => {
    if (!user) return [];
    return items
      .filter((x) => typeof x.userId === "undefined" || Number(x.userId) === Number(user.id))
      .sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt));
  }, [items, user]);

  const unreadCount = useMemo(() => notifications.filter((x) => !x.read).length, [notifications]);

  const addNotification = useCallback(
    (input: CreateNotificationInput) => {
      if (!user) return;

      if (shouldUseBackendNotifications(Boolean(user))) {
        void createBackendNotification(input)
          .then((created) => {
            setItems((prev) => [created, ...prev.filter((item) => item.id !== created.id)]);
          })
          .catch(() => {
          });
        return;
      }

      pushNotification({ ...input, userId: input.userId ?? user.id });
      setItems(readNotifications());
    },
    [user]
  );

  const markAllAsRead = useCallback(() => {
    if (!user) return;

    setItems((prev) =>
      prev.map((x) => {
        const belongsToCurrent = typeof x.userId === "undefined" || Number(x.userId) === Number(user.id);
        return belongsToCurrent && !x.read ? { ...x, read: true } : x;
      })
    );

    if (shouldUseBackendNotifications(Boolean(user))) {
      void markAllBackendNotificationsAsRead().catch(() => {
      });
    }
  }, [user]);

  const markAsRead = useCallback(
    (id: string) => {
      if (!user) return;

      setItems((prev) =>
        prev.map((x) => {
          const belongsToCurrent = typeof x.userId === "undefined" || Number(x.userId) === Number(user.id);
          return x.id === id && belongsToCurrent && !x.read ? { ...x, read: true } : x;
        })
      );

      if (shouldUseBackendNotifications(Boolean(user)) && /^\d+$/.test(id)) {
        void markBackendNotificationAsRead(id).catch(() => {
        });
      }
    },
    [user]
  );

  const removeNotification = useCallback(
    (id: string) => {
      if (!user) return;

      setItems((prev) => prev.filter((x) => x.id !== id));

      if (shouldUseBackendNotifications(Boolean(user)) && /^\d+$/.test(id)) {
        void deleteBackendNotification(id).catch(() => {
        });
      }
    },
    [user]
  );

  const clearNotificationsHandler = useCallback(() => {
    if (!user) return;

    setItems((prev) =>
      prev.filter((x) => typeof x.userId !== "undefined" && Number(x.userId) !== Number(user.id))
    );

    if (shouldUseBackendNotifications(Boolean(user))) {
      void clearBackendNotifications().catch(() => {
      });
    }
  }, [user]);

  const value = useMemo<NotificationsContextType>(
    () => ({
      notifications,
      unreadCount,
      addNotification,
      markAllAsRead,
      markAsRead,
      removeNotification,
      clearNotifications: clearNotificationsHandler,
    }),
    [notifications, unreadCount, addNotification, markAllAsRead, markAsRead, removeNotification, clearNotificationsHandler]
  );

  return <NotificationsContext.Provider value={value}>{children}</NotificationsContext.Provider>;
}

export function useNotifications() {
  const ctx = useContext(NotificationsContext);
  if (!ctx) {
    throw new Error("useNotifications должен использоваться внутри NotificationsProvider");
  }
  return ctx;
}
