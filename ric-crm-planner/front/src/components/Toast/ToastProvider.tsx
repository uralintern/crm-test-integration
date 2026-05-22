import { createContext, useCallback, useContext } from "react";
import type { ReactNode } from "react";
import { notification } from "antd";
import "../../styles/toast.scss";

export type ToastType = "success" | "error" | "info";

interface ToastContextValue {
  showToast: (type: ToastType, message: string) => void;
}

const ToastContext = createContext<ToastContextValue>({ showToast: () => {} });

export function useToast() {
  return useContext(ToastContext);
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [api, contextHolder] = notification.useNotification();

  const showToast = useCallback(
    (type: ToastType, message: string) => {
      const normalizedMessage = message.trim();
      if (!normalizedMessage) return;

      api[type]({
        message: normalizedMessage,
        placement: "topRight",
        duration: 2,
        showProgress: true,
        pauseOnHover: false,
        className: `app-notification app-notification--${type}`,
      });
    },
    [api]
  );

  return (
    <ToastContext.Provider value={{ showToast }}>
      {contextHolder}
      {children}
    </ToastContext.Provider>
  );
}
