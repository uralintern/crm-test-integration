import Modal from "../../../../components/Modal/Modal";
import type { PlannerParentTask, PlannerSubtask, PlannerTeam } from "../../../../types/planner";

type TaskCardModalProps = {
  isOpen: boolean;
  taskCardParent: PlannerParentTask | null;
  taskCardSubtask: PlannerSubtask | null;
  taskCardTeam: PlannerTeam | null;
  taskCardParentForSubtask: PlannerParentTask | null;
  taskCardSubtasksCount: number;
  displayAssigneeLabel: (id: number) => string;
  sourceLabelForTeam: (team: PlannerTeam) => string;
  onClose: () => void;
};

function formatPlannerDate(value?: string) {
  const raw = String(value || "").trim();
  if (!raw) return "—";

  const [year, month, day] = raw.split("-");
  if (year?.length === 4 && month?.length === 2 && day?.length === 2) {
    return `${day}.${month}.${year}`;
  }

  return raw;
}

export default function TaskCardModal({
  isOpen,
  taskCardParent,
  taskCardSubtask,
  taskCardTeam,
  taskCardParentForSubtask,
  taskCardSubtasksCount,
  displayAssigneeLabel,
  sourceLabelForTeam,
  onClose,
}: TaskCardModalProps) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Карточка задачи">
      <div className="confirm-body">
        {!taskCardParent && !taskCardSubtask ? (
          <div className="confirm-text">Задача не найдена.</div>
        ) : (
          <div className="planner-task-card">
            <div className="planner-task-row">
              <div className="planner-task-label">Тип</div>
              <div className="planner-task-value">{taskCardSubtask ? "Подзадача" : "Большая задача"}</div>
            </div>

            <div className="planner-task-row">
              <div className="planner-task-label">Название</div>
              <div className="planner-task-value">{taskCardSubtask?.title || taskCardParent?.title}</div>
            </div>

            <div className="planner-task-row">
              <div className="planner-task-label">Команда</div>
              <div className="planner-task-value">{taskCardTeam?.name || "—"}</div>
            </div>

            {taskCardTeam && sourceLabelForTeam(taskCardTeam) && (
              <div className="planner-task-row">
                <div className="planner-task-label">Источник</div>
                <div className="planner-task-value">{sourceLabelForTeam(taskCardTeam)}</div>
              </div>
            )}

            <div className="planner-task-row">
              <div className="planner-task-label">Сроки</div>
              <div className="planner-task-value">
                {taskCardSubtask
                  ? `${formatPlannerDate(taskCardSubtask.startDate)} — ${formatPlannerDate(taskCardSubtask.endDate)}`
                  : `${formatPlannerDate(taskCardParent?.startDate)} — ${formatPlannerDate(taskCardParent?.endDate)}`}
              </div>
            </div>

            {taskCardParent?.description && (
              <div className="planner-task-row">
                <div className="planner-task-label">Описание</div>
                <div className="planner-task-value">{taskCardParent.description}</div>
              </div>
            )}

            {taskCardParent && (
              <div className="planner-task-row">
                <div className="planner-task-label">Подзадач</div>
                <div className="planner-task-value">{taskCardSubtasksCount}</div>
              </div>
            )}

            {taskCardParent && (
              <div className="planner-task-row">
                <div className="planner-task-label">Ответственный</div>
                <div className="planner-task-value">
                  {taskCardParent.assigneeId ? displayAssigneeLabel(taskCardParent.assigneeId) : "—"}
                </div>
              </div>
            )}

            {taskCardSubtask && (
              <>
                <div className="planner-task-row">
                  <div className="planner-task-label">Ответственный</div>
                  <div className="planner-task-value">
                    {taskCardSubtask.assigneeId ? displayAssigneeLabel(taskCardSubtask.assigneeId) : "—"}
                  </div>
                </div>

                <div className="planner-task-row">
                  <div className="planner-task-label">Статус</div>
                  <div className="planner-task-value">{taskCardSubtask.status || "—"}</div>
                </div>

                <div className="planner-task-row">
                  <div className="planner-task-label">В спринт</div>
                  <div className="planner-task-value">{taskCardSubtask.inSprint ? "Да" : "Нет"}</div>
                </div>

                <div className="planner-task-row">
                  <div className="planner-task-label">Большая задача</div>
                  <div className="planner-task-value">{taskCardParentForSubtask?.title || "—"}</div>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
}
