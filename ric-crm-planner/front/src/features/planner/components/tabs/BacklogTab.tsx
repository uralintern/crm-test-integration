import { useState, type Dispatch, type SetStateAction, type MouseEvent } from "react";
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
  assigneeFilter: string;
  assigneeFilterOptions: Array<{ value: string; label: string; disabled?: boolean }>;
  onAssigneeFilterChange: (value: string) => void;
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

const formatAssigneeName = (label: string) => {
  const namePart = label.split(" - ")[0]?.trim() || label.trim();
  const parts = namePart.split(/\s+/).filter(Boolean);
  return parts.length > 2 ? parts.slice(0, 2).join(" ") : namePart;
};

const getSubtaskAssignee = (subtask: PlannerSubtask, displayAssigneeLabel: (id: number) => string) => {
  if (subtask.assigneeId) return formatAssigneeName(displayAssigneeLabel(subtask.assigneeId));
  return subtask.role || "Не назначен";
};

function formatBacklogDate(value?: string) {
  if (!value) return "-";
  const [datePart] = value.split("T");
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(datePart);
  if (!match) return value;
  return `${match[3]}-${match[2]}-${match[1]}`;
}

function isSubtaskInSprint(subtask: PlannerSubtask) {
  const sprintState = subtask as { inSprint?: unknown; in_sprint?: unknown };
  const rawValue = sprintState.inSprint ?? sprintState.in_sprint;
  return rawValue === true || rawValue === 1 || rawValue === "1" || String(rawValue).toLowerCase() === "true";
}

function stopHeaderAction(event: MouseEvent) {
  event.preventDefault();
  event.stopPropagation();
}

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
  assigneeFilter,
  assigneeFilterOptions,
  onAssigneeFilterChange,
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
  const [openParentById, setOpenParentById] = useState<Record<number, boolean>>({});
  const teamSprintCount = filteredSubtasks.filter(isSubtaskInSprint).length;
  const getParentSubtasks = (parentId: number) =>
    filteredSubtasks.filter((subtask) => Number(subtask.parentTaskId) === Number(parentId));

  const openParent = (parentId: number) => {
    setOpenParentById((prev) => ({ ...prev, [parentId]: true }));
    onSelectParent(parentId);
  };

  const toggleParent = (parentId: number) => {
    const fallbackOpen = Number(selectedParentId) === Number(parentId);
    setOpenParentById((prev) => ({ ...prev, [parentId]: !(prev[parentId] ?? fallbackOpen) }));
    onSelectParent(parentId);
  };

  const runHeaderAction = (event: MouseEvent, action: () => void) => {
    stopHeaderAction(event);
    action();
  };

  const renderParentEditor = (parent: PlannerParentTask) => (
    <div className="backlog-edit-form backlog-edit-form--parent backlog-tree-parent-editor">
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
          ...getTeamMemberIds(parent.teamId).map((id) => ({ value: String(id), label: formatAssigneeName(displayAssigneeLabel(Number(id))) })),
        ]}
      />
      <DateRangeField
        className="backlog-edit-date app-date-range-field--compact"
        startValue={editingParentDraft?.startDate ?? ""}
        endValue={editingParentDraft?.endDate ?? ""}
        onChange={(startDate, endDate) => setEditingParentDraft((prev) => (prev ? { ...prev, startDate, endDate } : prev))}
      />
    </div>
  );

  const renderSubtaskEditor = (subtask: PlannerSubtask) => (
    <div className="backlog-subtask-edit backlog-nested-row__editor">
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
          ...getTeamMemberIds(subtask.teamId).map((id) => ({ value: String(id), label: formatAssigneeName(displayAssigneeLabel(Number(id))) })),
        ]}
      />
      <DateRangeField
        className="backlog-edit-date app-date-range-field--compact"
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
    <div className="backlog-subtask-row backlog-subtask-row--create backlog-tree-create-subtask">
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
            ...selectedTeamMembers.map((id) => ({ value: String(id), label: formatAssigneeName(displayAssigneeLabel(Number(id))) })),
          ]}
        />
        <DateRangeField
          className="backlog-subtask-create-date app-date-range-field--compact"
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

  const renderSubtaskRow = (subtask: PlannerSubtask) => {
    const assigneeLabel = getSubtaskAssignee(subtask, displayAssigneeLabel);
    const subtaskEditable = canEditTeam(subtask.teamId);
    const isEditing = editingSubtaskId === subtask.id && editingSubtaskDraft;
    const subtaskInSprint = isSubtaskInSprint(subtask);

    return (
      <div key={subtask.id} className={`backlog-nested-row ${subtaskInSprint ? "is-in-sprint" : ""} ${isEditing ? "is-editing" : ""}`}>
        {isEditing ? (
          renderSubtaskEditor(subtask)
        ) : (
          <div className="backlog-nested-row__main">
            <div className="backlog-nested-row__title">{subtask.title}</div>
            <div className="backlog-nested-row__meta">
              <span>{formatBacklogDate(subtask.startDate)} - {formatBacklogDate(subtask.endDate)}</span>
              <span>{assigneeLabel}</span>
              <span>{subtask.status}</span>
              {subtaskInSprint && <span className="is-sprint">В спринте</span>}
            </div>
          </div>
        )}

        <div className="backlog-subtask-actions">
          <AppButton className="link-btn" type="button" onClick={() => onOpenTaskCard("subtask", subtask.id)}>
            Карточка
          </AppButton>
          {subtaskEditable &&
            (isEditing ? (
              <>
                <AppButton className="link-btn save" type="button" onClick={onSaveEditedSubtask}>Сохранить</AppButton>
                <AppButton className="link-btn cancel" type="button" onClick={onCancelEditSubtask}>Отмена</AppButton>
              </>
            ) : (
              <>
                <AppButton className="link-btn edit" type="button" onClick={() => onStartEditSubtask(subtask.id)}>Редактировать</AppButton>
                <AppButton className="link-btn danger" type="button" onClick={() => onDeleteSubtask(subtask.id)}>Удалить</AppButton>
              </>
            ))}
        </div>
      </div>
    );
  };

  return (
    <div className="planner-stack backlog-layout backlog-layout--sheet">
      <section className="planner-card backlog-sheet">
        <div className="backlog-sheet__head">
          <div>
            <div className="backlog-eyebrow">Бэклог команды</div>
            <div className="planner-current-team">Название команды: <strong>{activeTeamName || "Не выбрана"}</strong></div>
          </div>
          <div className="backlog-head-tools">
            <div className="backlog-filter">
              <span className="backlog-filter__label">Исполнитель</span>
              <AppSelect
                value={assigneeFilter}
                onChange={(value) => onAssigneeFilterChange(String(value))}
                options={assigneeFilterOptions}
              />
            </div>
            <div className="backlog-summary">
              <span>{filteredParents.length} задач</span>
              <span>{filteredSubtasks.length} подзадач</span>
              <span>{teamSprintCount} в спринте</span>
            </div>
          </div>
        </div>

        <div className="planner-source-tree backlog-tree">
          {filteredParents.length === 0 && <div className="planner-empty-inline">Пока нет больших задач для выбранной команды.</div>}

          {filteredParents.map((parent) => {
            const parentSubtasks = getParentSubtasks(parent.id);
            const parentSprintCount = parentSubtasks.filter(isSubtaskInSprint).length;
            const isActive = Number(selectedParentId) === Number(parent.id);
            const isOpen = Boolean(openParentById[parent.id] ?? isActive) || editingParentId === parent.id;
            const editable = canEditTeam(parent.teamId);
            const parentAssignee = parent.assigneeId ? formatAssigneeName(displayAssigneeLabel(parent.assigneeId)) : "Не назначен";

            return (
              <article
                key={parent.id}
                className={`planner-source-node planner-source-node--event backlog-tree-node ${isActive ? "is-active" : ""} ${isOpen ? "is-open" : ""}`}
              >
                <div className="planner-source-summary backlog-tree-summary" onClick={() => openParent(parent.id)}>
                  <button
                    className="backlog-tree-toggle"
                    type="button"
                    aria-expanded={isOpen}
                    aria-label={isOpen ? "Свернуть большую задачу" : "Раскрыть большую задачу"}
                    onClick={(event) => runHeaderAction(event, () => toggleParent(parent.id))}
                  >
                    {isOpen ? "▾" : "▸"}
                  </button>

                  <div className="planner-source-summary-main backlog-tree-summary-main">
                    <span className="backlog-tree-title">Задача: {parent.title}</span>
                    <span className="planner-source-meta">{parentSubtasks.length} подзадач</span>
                    <span className="planner-source-meta">В спринте: {parentSprintCount}/{parentSubtasks.length}</span>
                    <span className="planner-source-meta">{formatBacklogDate(parent.startDate)} - {formatBacklogDate(parent.endDate)}</span>
                    <span className="planner-source-meta">{parentAssignee}</span>
                  </div>

                  <div className="planner-source-summary-actions backlog-tree-actions">
                    <AppButton className="link-btn" type="button" onClick={(event) => runHeaderAction(event, () => onOpenTaskCard("parent", parent.id))}>
                      Карточка
                    </AppButton>
                    {editable &&
                      (editingParentId === parent.id ? (
                        <>
                          <AppButton className="link-btn save" type="button" onClick={(event) => runHeaderAction(event, onSaveEditedParent)}>Сохранить</AppButton>
                          <AppButton className="link-btn cancel" type="button" onClick={(event) => runHeaderAction(event, onCancelEditParent)}>Отмена</AppButton>
                        </>
                      ) : (
                        <>
                          <AppButton
                            className="link-btn edit"
                            type="button"
                            onClick={(event) => runHeaderAction(event, () => {
                              openParent(parent.id);
                              onStartEditParent(parent.id);
                            })}
                          >
                            Редактировать
                          </AppButton>
                          <AppButton className="link-btn danger" type="button" onClick={(event) => runHeaderAction(event, () => onDeleteParent(parent.id))}>Удалить</AppButton>
                        </>
                      ))}
                  </div>
                </div>

                {isOpen && (
                  <div className="planner-source-content backlog-tree-content">
                    {editingParentId === parent.id && editingParentDraft && renderParentEditor(parent)}

                    <div className="backlog-nested-list">
                      {parentSubtasks.length === 0 ? (
                        <div className="backlog-subtask-empty">Подзадач пока нет.</div>
                      ) : (
                        parentSubtasks.map(renderSubtaskRow)
                      )}
                    </div>

                    {isActive && selectedParent ? (
                      renderSubtaskCreateRow()
                    ) : (
                      <AppButton className="backlog-add-inline" type="button" onClick={() => openParent(parent.id)}>
                        + Добавить подзадачу
                      </AppButton>
                    )}
                  </div>
                )}
              </article>
            );
          })}

          <div className="planner-source-node backlog-tree-create-node">
            <div className="planner-source-summary planner-source-summary--static backlog-tree-create-head">
              <div className="planner-source-summary-main">
                <span className="backlog-tree-title">Новая большая задача</span>
                <span className="planner-source-meta">Добавится в выбранную команду</span>
              </div>
            </div>
            <div className="planner-source-content backlog-tree-create-content">
              <div className="backlog-sheet-parent backlog-sheet-parent--new">
                <AppInput value={parentTitle} onChange={(event) => onParentTitleChange(event.target.value)} placeholder="Название большой задачи" />
                <AppSelect
                  value={parentAssigneeId || ""}
                  onChange={(value) => onParentAssigneeChange(String(value))}
                  disabled={activeTeamMembers.length === 0}
                  options={[
                    { value: "", label: "Без ответственного" },
                    ...activeTeamMembers.map((id) => ({ value: String(id), label: formatAssigneeName(displayAssigneeLabel(Number(id))) })),
                  ]}
                />
                <DateRangeField
                  className="backlog-edit-date app-date-range-field--compact"
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
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
