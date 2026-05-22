import { useCallback, useContext, useEffect, useState } from "react";
import { AuthContext } from "../../context/AuthContext";
import { getVKBotStatus, type VKBotStatus } from "../../api/vk";
import Modal from "../Modal/Modal";
import AppButton from "../UI/Button";
import { useToast } from "../Toast/ToastProvider";

export const VK_BOT_CONFIRMATION_REQUIRED_KEY = "vk_bot_confirmation_required_v1";

export function requireVKBotConfirmation() {
  localStorage.setItem(VK_BOT_CONFIRMATION_REQUIRED_KEY, "1");
}

export default function VKBotConfirmationGuard() {
  const { user, refreshUser } = useContext(AuthContext);
  const { showToast } = useToast();
  const [status, setStatus] = useState<VKBotStatus | null>(null);
  const [open, setOpen] = useState(false);
  const [checking, setChecking] = useState(false);

  const shouldCheck = Boolean(user && user.role === "student" && user.vk && !user.vkConfirmed);

  const refresh = useCallback(async (manual = false) => {
    if (!user || user.role !== "student") return;
    if (manual) setChecking(true);

    try {
      const nextStatus = await getVKBotStatus();
      setStatus(nextStatus);
      if (nextStatus.confirmed) {
        localStorage.removeItem(VK_BOT_CONFIRMATION_REQUIRED_KEY);
        await refreshUser();
        setOpen(false);
        if (manual) showToast("success", "VK-бот подтвержден.");
        return;
      }

      setOpen(true);
      if (manual) {
        showToast("info", "Подтверждение пока не найдено. Откройте VK-бота и нажмите «Начать».");
      }
    } catch {
      setOpen(true);
      if (manual) showToast("error", "Не удалось проверить подтверждение VK-бота.");
    } finally {
      if (manual) setChecking(false);
    }
  }, [refreshUser, showToast, user]);

  useEffect(() => {
    if (!shouldCheck) {
      setOpen(false);
      return;
    }

    void refresh();
    const timer = window.setInterval(() => {
      void refresh();
    }, 60_000);

    return () => window.clearInterval(timer);
  }, [refresh, shouldCheck]);

  if (!shouldCheck) return null;

  const botUrl = status?.botUrl || user?.vkBotUrl || "";

  return (
    <Modal isOpen={open} onClose={() => setOpen(false)} title="Подтвердите VK-бота" hideActions>
      <div className="vk-bot-confirmation">
        <p>
          Чтобы получать сообщения по заявке и организационному чату, перейдите в VK-бота и нажмите кнопку «Начать».
          Окно будет появляться раз в минуту, пока бот не подтвердит ваш VK.
        </p>
        <div className="vk-bot-confirmation__actions">
          {botUrl && (
            <AppButton className="close-btn" onClick={() => window.open(botUrl, "_blank", "noopener,noreferrer")}>
              Открыть VK-бота
            </AppButton>
          )}
          <AppButton className="btn-send" loading={checking} onClick={() => void refresh(true)}>
            Проверить подтверждение
          </AppButton>
        </div>
      </div>
    </Modal>
  );
}
