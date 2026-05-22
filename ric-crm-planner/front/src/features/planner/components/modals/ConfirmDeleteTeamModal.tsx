import Modal from "../../../../components/Modal/Modal";
import AppButton from "../../../../components/UI/Button";
import type { PlannerTeam } from "../../../../types/planner";

type ConfirmDeleteTeamModalProps = {
  isOpen: boolean;
  team: PlannerTeam | null;
  onClose: () => void;
  onConfirm: () => void;
};

export default function ConfirmDeleteTeamModal({
  isOpen,
  team,
  onClose,
  onConfirm,
}: ConfirmDeleteTeamModalProps) {
  const teamName = team?.name?.trim() || "команду";

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Удаление команды">
      <div className="confirm-body">
        <div className="confirm-text">
          Удалить команду «{teamName}»? Будут удалены команда, большие задачи, подзадачи и все данные планировщика по ней.
          Восстановить эти данные нельзя.
        </div>
        <div className="confirm-actions">
          <AppButton className="link-btn" onClick={onClose}>
            Отмена
          </AppButton>
          <AppButton className="danger-outline" onClick={onConfirm}>
            Удалить
          </AppButton>
        </div>
      </div>
    </Modal>
  );
}
