import Modal from "../../../../components/Modal/Modal";
import type { PlannerTeam } from "../../../../types/planner";

type TeamInfoModalProps = {
  isOpen: boolean;
  team: PlannerTeam | null;
  specializationByOwnerId: Map<number, string>;
  displayNameForUserId: (id: number) => string;
  onClose: () => void;
};

export default function TeamInfoModal({ isOpen, team, specializationByOwnerId, displayNameForUserId, onClose }: TeamInfoModalProps) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Состав команды">
      <div className="confirm-body">
        {!team ? (
          <div className="confirm-text">Команда не выбрана.</div>
        ) : (
          <>
            <div className="confirm-text">{team.name || "Команда"}</div>
            <div className="planner-team-info-list">
              {team.memberIds.map((id) => (
                <div key={`team-info-${team.id}-${id}`} className="planner-team-info-row">
                  <div className="planner-team-info-name">{displayNameForUserId(id)}</div>
                  <div className="planner-team-info-role">{specializationByOwnerId.get(id) || "-"}</div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
