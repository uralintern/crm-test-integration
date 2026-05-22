import Modal from "../../../../components/Modal/Modal";
import type { PlannerTeam } from "../../../../types/planner";
import AppButton from "../../../../components/UI/Button";
import AppSwitch from "../../../../components/UI/Switch";

type TeamEditModalProps = {
  isOpen: boolean;
  team: PlannerTeam | null;
  teamEditMembers: number[];
  candidateIds: number[];
  displayAssigneeLabel: (id: number) => string;
  onToggleMember: (id: number) => void;
  onClose: () => void;
  onSave: () => void;
};

export default function TeamEditModal({
  isOpen,
  team,
  teamEditMembers,
  candidateIds,
  displayAssigneeLabel,
  onToggleMember,
  onClose,
  onSave,
}: TeamEditModalProps) {
  const isLocked = Boolean(team?.confirmed);

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={isLocked ? "Состав команды" : "Редактирование команды"}>
      <div className="confirm-body">
        {!team ? (
          <div className="confirm-text">Команда не выбрана.</div>
        ) : (
          <>
            <div className="confirm-text">{team.name || "Команда"}</div>
            <div className="planner-team-edit-meta">Участники: {teamEditMembers.length}</div>
            {isLocked && (
              <div className="planner-note teams-note">
                Команда подтверждена. Состав доступен для просмотра, а для изменений сначала снимите подтверждение.
              </div>
            )}
            {candidateIds.length === 0 ? (
              <div className="planner-empty-inline">Нет участников для выбора.</div>
            ) : (
              <div className="planner-team-edit-list">
                {candidateIds.map((id) => (
                  <label key={`team-edit-${team.id}-${id}`} className="planner-check planner-applicant-row planner-applicant-row--modal">
                    <AppSwitch checked={teamEditMembers.includes(id)} onChange={() => onToggleMember(id)} compact />
                    <span>{displayAssigneeLabel(id)}</span>
                  </label>
                ))}
              </div>
            )}
            <div className="planner-team-edit-actions">
              <AppButton className="link-btn" onClick={onClose}>
                {isLocked ? "Закрыть" : "Отмена"}
              </AppButton>
              {!isLocked && (
                <AppButton className="primary" onClick={onSave}>
                  Сохранить
                </AppButton>
              )}
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
