import dayjs, { Dayjs } from "dayjs";
import Modal from "../../../../components/Modal/Modal";
import type {
  PlannerParentTask,
  PlannerSubtask,
  PlannerTeam,
} from "../../../../types/planner";

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

const formatDate = (date: Dayjs | undefined): string =>
  date ? dayjs(date).format("DD.MM.YYYY") : "Нет срока";

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
            {/* <div className="planner-task-row">
              <div className="planner-task-label">Тип</div>
              <div className="planner-task-value">
                {taskCardSubtask ? "Подзадача" : "Большая задача"}
              </div>
            </div> */}

            <div className="planner-task-row">
              <div className="planner-task-label">Название</div>
              <div className="planner-task-value">
                {taskCardSubtask?.title || taskCardParent?.title}
              </div>
            </div>

            {taskCardParent?.description && (
              <div className="planner-task-row">
                <div className="planner-task-label">Описание</div>
                <div className="planner-task-value">
                  {taskCardParent.description}
                </div>
              </div>
            )}
            
            <div className="planner-task-row">
              <div className="planner-task-label">Команда</div>
              <div className="planner-task-value">
                {taskCardTeam?.name || "—"}
              </div>
            </div>

            {taskCardTeam && sourceLabelForTeam(taskCardTeam) && (
              <div className="planner-task-row">
                <div className="planner-task-label">Источник</div>
                <div className="planner-task-value">
                  {sourceLabelForTeam(taskCardTeam)}
                </div>
              </div>
            )}

            <div className="planner-task-row">
              <div className="planner-task-label">Сроки</div>
              <div className="planner-task-value">
                {taskCardSubtask
                  ? `${formatDate(taskCardSubtask.startDate)} — ${formatDate(taskCardSubtask.endDate)}`
                  : `${formatDate(taskCardParent?.startDate)} — ${formatDate(taskCardParent?.endDate)}`}
              </div>
            </div>



            {taskCardParent && (
              <div className="planner-task-row">
                <div className="planner-task-label">Подзадач</div>
                <div className="planner-task-value">
                  {taskCardSubtasksCount}
                </div>
              </div>
            )}

            {taskCardParent && (
              <div className="planner-task-row">
                <div className="planner-task-label">Ответственный</div>
                <div className="planner-task-value">
                  {taskCardParent.assigneeId
                    ? displayAssigneeLabel(taskCardParent.assigneeId)
                    : "—"}
                </div>
              </div>
            )}

            {taskCardSubtask && (
              <>
                <div className="planner-task-row">
                  <div className="planner-task-label">Ответственный</div>
                  <div className="planner-task-value">
                    {taskCardSubtask.assigneeId
                      ? displayAssigneeLabel(taskCardSubtask.assigneeId)
                      : "—"}
                  </div>
                </div>

                <div className="planner-task-row">
                  <div className="planner-task-label">Статус</div>
                  <div className="planner-task-value">
                    {taskCardSubtask.status || "—"}
                  </div>
                </div>

                <div className="planner-task-row">
                  <div className="planner-task-label">Большая задача</div>
                  <div className="planner-task-value">
                    {taskCardParentForSubtask?.title || "—"}
                  </div>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
}
