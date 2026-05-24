import type { Dispatch, SetStateAction } from "react";
import { DateRangeField } from "../../../../components/UI/DateField";
import type { PlannerParentTask, PlannerSubtask } from "../../../../types/planner";
import type { ParentEditDraft, SubtaskEditDraft } from "../../planner.types";
import AppButton from "../../../../components/UI/Button";
import AppInput from "../../../../components/UI/Input";
import AppSelect from "../../../../components/UI/Select";
import AppSwitch from "../../../../components/UI/Switch";

type BacklogTabProps = {
  activeTeamName: string;
  parentTitle: string;
  parentAssigneeId: string;
  parentStart: string;
  parentEnd: string;
  onParentTitleChange: (value: string) => void;
  onParentAssigneeChange: (value: string) => void;
  onParentStartChange: (value: string) => void;
  onParentEndChange: (value: string) => void;
  onAddParentTask: () => void;
  activeTeamMembers: number[];
  filteredParents: PlannerParentTask[];
  selectedParentId: number | null;
  onSelectParent: (parentId: number) => void;
  editingParentId: number | null;
  editingParentDraft: ParentEditDraft | null;
  setEditingParentDraft: Dispatch<SetStateAction<ParentEditDraft | null>>;
  onOpenTaskCard: (type: "parent" | "subtask", id: number) => void;
  onStartEditParent: (parentId: number) => void;
  onSaveEditedParent: () => void;
  onCancelEditParent: () => void;
  onDeleteParent: (parentId: number) => void;
  canEditTeam: (teamId: number) => boolean;
  selectedParent?: PlannerParentTask;
  selectedTeamMembers: number[];
  subAssigneeId: string;
  subTitle: string;
  subStart: string;
  subEnd: string;
  subInSprint: boolean;
  onSubAssigneeChange: (value: string) => void;
  onSubTitleChange: (value: string) => void;
  onSubStartChange: (value: string) => void;
  onSubEndChange: (value: string) => void;
  onSubInSprintChange: (value: boolean) => void;
  onAddSubtask: () => void;
  filteredSubtasks: PlannerSubtask[];
  editingSubtaskId: number | null;
  editingSubtaskDraft: SubtaskEditDraft | null;
  setEditingSubtaskDraft: Dispatch<SetStateAction<SubtaskEditDraft | null>>;
  getTeamMemberIds: (teamId: number) => number[];
  displayAssigneeLabel: (id: number) => string;
  onStartEditSubtask: (subtaskId: number) => void;
  onSaveEditedSubtask: () => void;
  onCancelEditSubtask: () => void;
  onDeleteSubtask: (subtaskId: number) => void;
};

const getSubtaskAssignee = (subtask: PlannerSubtask, displayAssigneeLabel: (id: number) => string) => {
  if (subtask.assigneeId) return displayAssigneeLabel(subtask.assigneeId);
  return subtask.role || "Не назначен";
};

export default function BacklogTab({
  activeTeamName,
  parentTitle,
  parentAssigneeId,
  parentStart,
  parentEnd,
  onParentTitleChange,
  onParentAssigneeChange,
  onParentStartChange,
  onParentEndChange,
  onAddParentTask,
  activeTeamMembers,
  filteredParents,
  selectedParentId,
  onSelectParent,
  editingParentId,
  editingParentDraft,
  setEditingParentDraft,
  onOpenTaskCard,
  onStartEditParent,
  onSaveEditedParent,
  onCancelEditParent,
  onDeleteParent,
  canEditTeam,
  selectedParent,
  selectedTeamMembers,
  subAssigneeId,
  subTitle,
  subStart,
  subEnd,
  subInSprint,
  onSubAssigneeChange,
  onSubTitleChange,
  onSubStartChange,
  onSubEndChange,
  onSubInSprintChange,
  onAddSubtask,
  filteredSubtasks,
  editingSubtaskId,
  editingSubtaskDraft,
  setEditingSubtaskDraft,
  getTeamMemberIds,
  displayAssigneeLabel,
  onStartEditSubtask,
  onSaveEditedSubtask,
  onCancelEditSubtask,
  onDeleteSubtask,
}: BacklogTabProps) {
  const selectedParentSubtasks = filteredSubtasks.filter((subtask) => Number(subtask.parentTaskId) === Number(selectedParentId));
  const selectedParentSprintCount = selectedParentSubtasks.filter((subtask) => subtask.inSprint).length;
  const getParentSubtasks = (parentId: number) =>
    filteredSubtasks.filter((subtask) => Number(subtask.parentTaskId) === Number(parentId));

  const renderParentEditor = (parent: PlannerParentTask) => (
    <div className="backlog-edit-form backlog-edit-form--parent">
      <AppInput
        value={editingParentDraft?.title ?? ""}
        onClick={(event) => event.stopPropagation()}
        onChange={(event) => setEditingParentDraft((prev) => (prev ? { ...prev, title: event.target.value } : prev))}
        placeholder="Название большой задачи"
      />
      <AppSelect
        value={editingParentDraft?.assigneeId != null ? String(editingParentDraft.assigneeId) : ""}
        onClick={(event) => event.stopPropagation()}
        onChange={(value) =>
          setEditingParentDraft((prev) => (prev ? { ...prev, assigneeId: value ? Number(value) : undefined } : prev))
        }
        options={[
          { value: "", label: "Без ответственного" },
          ...getTeamMemberIds(parent.teamId).map((id) => ({ value: String(id), label: displayAssigneeLabel(Number(id)) })),
        ]}
      />
      <DateRangeField
        className="backlog-edit-date"
        startValue={editingParentDraft?.startDate ?? ""}
        endValue={editingParentDraft?.endDate ?? ""}
        onChange={(startDate, endDate) => setEditingParentDraft((prev) => (prev ? { ...prev, startDate, endDate } : prev))}
      />
    </div>
  );

  const renderSubtaskEditor = (subtask: PlannerSubtask) => (
    <div className="backlog-subtask-edit">
      <AppInput
        value={editingSubtaskDraft?.title ?? ""}
        onChange={(event) => setEditingSubtaskDraft((prev) => (prev ? { ...prev, title: event.target.value } : prev))}
        placeholder="Название подзадачи"
      />
      <AppSelect
        value={editingSubtaskDraft?.assigneeId != null ? String(editingSubtaskDraft.assigneeId) : ""}
        onChange={(value) => setEditingSubtaskDraft((prev) => (prev ? { ...prev, assigneeId: Number(value) } : prev))}
        options={[
          { value: "", label: "Ответственный", disabled: true },
          ...getTeamMemberIds(subtask.teamId).map((id) => ({ value: String(id), label: displayAssigneeLabel(Number(id)) })),
        ]}
      />
      <DateRangeField
        className="backlog-edit-date"
        startValue={editingSubtaskDraft?.startDate ?? ""}
        endValue={editingSubtaskDraft?.endDate ?? ""}
        onChange={(startDate, endDate) => setEditingSubtaskDraft((prev) => (prev ? { ...prev, startDate, endDate } : prev))}
      />
      <label className="planner-check backlog-sprint-toggle backlog-sprint-toggle--edit">
        <span>В спринт</span>
        <AppSwitch
          checked={Boolean(editingSubtaskDraft?.inSprint)}
          onChange={(checked) => setEditingSubtaskDraft((prev) => (prev ? { ...prev, inSprint: checked } : prev))}
          compact
        />
      </label>
    </div>
  );

  const renderSubtaskCreateRow = () => (
    <div className="backlog-subtask-row backlog-subtask-row--create">
      <div className="backlog-subtask-create-title">
        <AppInput value={subTitle} onChange={(event) => onSubTitleChange(event.target.value)} placeholder="Название подзадачи" />
      </div>
      <div className="backlog-subtask-create-meta">
        <AppSelect
          value={subAssigneeId || ""}
          onChange={(value) => onSubAssigneeChange(String(value))}
          disabled={selectedTeamMembers.length === 0}
          options={[
            { value: "", label: "Ответственный", disabled: true },
            ...selectedTeamMembers.map((id) => ({ value: String(id), label: displayAssigneeLabel(Number(id)) })),
          ]}
        />
        <DateRangeField
          className="backlog-subtask-create-date"
          startValue={subStart}
          endValue={subEnd}
          onChange={(startDate, endDate) => {
            onSubStartChange(startDate);
            onSubEndChange(endDate);
          }}
        />
        <label className="planner-check backlog-sprint-toggle">
          <span>В спринт</span>
          <AppSwitch checked={subInSprint} onChange={onSubInSprintChange} compact />
        </label>
        <AppButton className="primary backlog-save-btn" type="button" onClick={onAddSubtask}>
          Сохранить
        </AppButton>
      </div>
    </div>
  );

  return (
    <div className="planner-stack backlog-layout backlog-layout--sheet">
      <section className="planner-card backlog-sheet">
        <div className="backlog-sheet__head">
          <div>
            <div className="backlog-eyebrow">Бэклог команды</div>
            <div className="planner-current-team">Название команды: <strong>{activeTeamName || "Не выбрана"}</strong></div>
          </div>
          <div className="backlog-summary">
            <span>{filteredParents.length} задач</span>
            <span>{filteredSubtasks.length} подзадач</span>
            <span>{selectedParentSprintCount} в спринте</span>
          </div>
        </div>

        <div className="backlog-sheet__body">
          {filteredParents.length === 0 && <div className="planner-empty-inline">Пока нет больших задач для выбранной команды.</div>}

          {filteredParents.map((parent) => {
            const parentSubtasks = getParentSubtasks(parent.id);
            const parentSprintCount = parentSubtasks.filter((subtask) => subtask.inSprint).length;
            const isActive = Number(selectedParentId) === Number(parent.id);
            const editable = canEditTeam(parent.teamId);

            return (
              <article key={parent.id} className={`backlog-sheet-row ${isActive ? "is-active" : ""}`} onClick={() => onSelectParent(parent.id)}>
                <div className="backlog-sheet-parent">
                  {editingParentId === parent.id && editingParentDraft ? (
                    renderParentEditor(parent)
                  ) : (
                    <>
                      <div className="backlog-sheet-parent__title">{parent.title}</div>
                      <div className="backlog-sheet-parent__meta">
                        <span>Старт: {parent.startDate || "-"}</span>
                        <span>Финиш: {parent.endDate || "-"}</span>
                        <span>В спринте: {parentSprintCount}/{parentSubtasks.length}</span>
                        <span>Ответственный: {parent.assigneeId ? displayAssigneeLabel(parent.assigneeId) : "Не назначен"}</span>
                      </div>
                    </>
                  )}

                  <div className="backlog-sheet-actions" onClick={(event) => event.stopPropagation()}>
                    <AppButton className="link-btn" type="button" onClick={() => onOpenTaskCard("parent", parent.id)}>
                      Карточка
                    </AppButton>
                    {editable && (
                      editingParentId === parent.id ? (
                        <>
                          <AppButton className="link-btn save" type="button" onClick={onSaveEditedParent}>Сохранить</AppButton>
                          <AppButton className="link-btn cancel" type="button" onClick={onCancelEditParent}>Отмена</AppButton>
                        </>
                      ) : (
                        <>
                          <AppButton className="link-btn edit" type="button" onClick={() => onStartEditParent(parent.id)}>Редактировать</AppButton>
                          <AppButton className="link-btn danger" type="button" onClick={() => onDeleteParent(parent.id)}>Удалить</AppButton>
                        </>
                      )
                    )}
                  </div>
                </div>

                <div className="backlog-sheet-subtasks" onClick={(event) => event.stopPropagation()}>
                  {parentSubtasks.length === 0 && !isActive && <div className="backlog-subtask-empty">Подзадач пока нет</div>}

                  {parentSubtasks.map((subtask) => {
                    const assigneeLabel = getSubtaskAssignee(subtask, displayAssigneeLabel);
                    const subtaskEditable = canEditTeam(subtask.teamId);
                    const isEditing = editingSubtaskId === subtask.id && editingSubtaskDraft;

                    return (
                      <div key={subtask.id} className={`backlog-subtask-row ${subtask.inSprint ? "is-in-sprint" : ""}`}>
                        {isEditing ? (
                          renderSubtaskEditor(subtask)
                        ) : (
                          <>
                            <div className="backlog-subtask-title">{subtask.title}</div>
                            <div className="backlog-subtask-meta">
                              <span>{subtask.startDate} - {subtask.endDate}</span>
                              <span>{assigneeLabel}</span>
                              <span>{subtask.status}</span>
                              {subtask.inSprint && <span>в спринте</span>}
                            </div>
                          </>
                        )}

                        <div className="backlog-subtask-actions">
                          <AppButton className="link-btn" type="button" onClick={() => onOpenTaskCard("subtask", subtask.id)}>
                            Карточка
                          </AppButton>
                          {subtaskEditable && (
                            isEditing ? (
                              <>
                                <AppButton className="link-btn save" type="button" onClick={onSaveEditedSubtask}>Сохранить</AppButton>
                                <AppButton className="link-btn cancel" type="button" onClick={onCancelEditSubtask}>Отмена</AppButton>
                              </>
                            ) : (
                              <>
                                <AppButton className="link-btn edit" type="button" onClick={() => onStartEditSubtask(subtask.id)}>Редактировать</AppButton>
                                <AppButton className="link-btn danger" type="button" onClick={() => onDeleteSubtask(subtask.id)}>Удалить</AppButton>
                              </>
                            )
                          )}
                        </div>
                      </div>
                    );
                  })}

                  {isActive && selectedParent ? renderSubtaskCreateRow() : (
                    <AppButton className="backlog-add-inline" type="button" onClick={() => onSelectParent(parent.id)}>
                      + Добавить подзадачу
                    </AppButton>
                  )}
                </div>
              </article>
            );
          })}

          <article className="backlog-sheet-row backlog-sheet-row--new">
            <div className="backlog-sheet-parent backlog-sheet-parent--new">
              <AppInput value={parentTitle} onChange={(event) => onParentTitleChange(event.target.value)} placeholder="Название большой задачи" />
              <AppSelect
                value={parentAssigneeId || ""}
                onChange={(value) => onParentAssigneeChange(String(value))}
                disabled={activeTeamMembers.length === 0}
                options={[
                  { value: "", label: "Без ответственного" },
                  ...activeTeamMembers.map((id) => ({ value: String(id), label: displayAssigneeLabel(Number(id)) })),
                ]}
              />
              <DateRangeField
                className="backlog-edit-date"
                startValue={parentStart}
                endValue={parentEnd}
                onChange={(startDate, endDate) => {
                  onParentStartChange(startDate);
                  onParentEndChange(endDate);
                }}
              />
              <AppButton className="primary backlog-save-btn" type="button" onClick={onAddParentTask}>
                Сохранить задачу
              </AppButton>
            </div>
            <div className="backlog-sheet-subtasks backlog-sheet-subtasks--hint">
              После сохранения большой задачи здесь можно будет добавить подзадачи.
            </div>
          </article>
        </div>
      </section>
    </div>
  );
}
