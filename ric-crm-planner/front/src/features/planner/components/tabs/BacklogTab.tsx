import { useState, type Dispatch, type SetStateAction, type MouseEvent } from "react";
import type { PlannerParentTask, PlannerSubtask, PlannerTeam } from "../../../../types/planner";
import type { ParentEditDraft, SubtaskEditDraft } from "../../planner.types";
import { Select, Button, Input, DatePicker, Flex, Typography, Popconfirm } from "antd";
import { CaretDownFilled, CaretRightFilled, CloseCircleFilled, DeleteFilled, EditFilled, SaveFilled } from '@ant-design/icons'
import type { Dayjs } from "dayjs";
import dayjs from "dayjs";

const { Text } = Typography;

type BacklogTabProps = {
  activeTeamName: string;
  parentTitle: string;
  parentAssigneeId: string;
  parentStart: Dayjs | undefined;
  parentEnd: Dayjs | undefined;
  onParentTitleChange: (value: string) => void;
  onParentAssigneeChange: (value: string) => void;
  onParentStartChange: (value: Dayjs | undefined) => void;
  onParentEndChange: (value: Dayjs | undefined) => void;
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
  subStart: Dayjs | undefined;
  subEnd: Dayjs | undefined;
  subInSprint: boolean;
  onSubAssigneeChange: (value: string) => void;
  onSubTitleChange: (value: string) => void;
  onSubStartChange: (value: Dayjs | undefined) => void;
  onSubEndChange: (value: Dayjs | undefined) => void;
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

  visibleTeams: PlannerTeam[];
  teamFilter: string;
  onTeamFilterChange: (value: string) => void;
};

const formatAssigneeName = (label: string) => {
  const namePart = label.split(" - ")[0]?.trim() || label.trim();
  const parts = namePart.split(/\s+/).filter(Boolean);
  return parts.length > 2 ? parts.slice(0, 2).join(" ") : namePart;
};

const getSubtaskAssignee = (subtask: PlannerSubtask, displayAssigneeLabel: (id: number) => string) => {
  if (subtask.assigneeId) return formatAssigneeName(displayAssigneeLabel(subtask.assigneeId));
  return subtask.role || "Исполнитель не назначен";
};

export default function BacklogTab({
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
  onStartEditParent,
  onSaveEditedParent,
  onCancelEditParent,
  onDeleteParent,
  canEditTeam,
  selectedTeamMembers,
  subAssigneeId,
  subTitle,
  subStart,
  subEnd,
  onSubAssigneeChange,
  onSubTitleChange,
  onSubStartChange,
  onSubEndChange,
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
  visibleTeams,
  teamFilter,
  onTeamFilterChange
}: BacklogTabProps) {
  const [openParentById, setOpenParentById] = useState<Record<number, boolean>>({});

  const getParentSubtasks = (parentId: number) =>
    filteredSubtasks.filter((subtask) => Number(subtask.parentTaskId) === Number(parentId));

  const toggleParent = (parentId: number) => {
    const fallbackOpen = Number(selectedParentId) === Number(parentId);
    setOpenParentById((prev) => ({ ...prev, [parentId]: !(prev[parentId] ?? fallbackOpen) }));
    onSelectParent(parentId);
  };

  const runHeaderAction = (event: MouseEvent, action: () => void) => {
    event.preventDefault();
    event.stopPropagation();
    action();
  };

  //Редактор большой задачи
  const renderParentEditor = (parent: PlannerParentTask) => (
    <Flex>
      <Input
        value={editingParentDraft?.title ?? ""}
        onClick={(event) => event.stopPropagation()}
        onChange={(event) => setEditingParentDraft((prev) => (prev ? { ...prev, title: event.target.value } : prev))}
        placeholder="Название большой задачи"
      />
      <Select
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
      <DatePicker
        format="DD.MM.YYYY"
        value={editingParentDraft?.startDate}
        onChange={(startDate) =>
          setEditingParentDraft((state) =>
            state ? { ...state, startDate: startDate ?? undefined } : null
          )
        }
      />
      <DatePicker
        format="DD.MM.YYYY"
        value={editingParentDraft?.endDate}
        onChange={(endDate) =>
          setEditingParentDraft((state) =>
            state ? { ...state, endDate: endDate ?? undefined } : null
          )
        }
      />
    </Flex>
  );

  //Редактор подзадачи
  const renderSubtaskEditor = (subtask: PlannerSubtask) => (
    <Flex gap={8}>
      <Input
        value={editingSubtaskDraft?.title ?? ""}
        onChange={(event) => setEditingSubtaskDraft((prev) => (prev ? { ...prev, title: event.target.value } : prev))}
        placeholder="Название подзадачи"
      />
      <Select
        value={editingSubtaskDraft?.assigneeId != null ? String(editingSubtaskDraft.assigneeId) : "0"}
        onChange={(value) => setEditingSubtaskDraft((prev) => (prev ? { ...prev, assigneeId: Number(value) } : prev))}
        options={[
          { value: "0", label: "Без ответственного" },
          ...getTeamMemberIds(subtask.teamId).map((id) => ({ value: String(id), label: formatAssigneeName(displayAssigneeLabel(Number(id))) })),
        ]}
      />
      <DatePicker
        style={{ width: '100%' }}
        format="DD.MM.YYYY"
        value={editingSubtaskDraft?.startDate}
        onChange={(startDate) =>
          setEditingSubtaskDraft((state) =>
            state ? { ...state, startDate: startDate ?? undefined } : null
          )
        }
      />
      <DatePicker
        style={{ width: '100%' }}
        format="DD.MM.YYYY"
        value={editingSubtaskDraft?.endDate}
        onChange={(endDate) =>
          setEditingSubtaskDraft((state) =>
            state ? { ...state, endDate: endDate ?? undefined } : null
          )
        }
      />
    </Flex>
  );

  const formatDate = (date: Dayjs | undefined): string => {
    if (!date)
      return 'Нет срока'

    return dayjs(date).format('DD.MM.YYYY');
  }

  const renderSubtaskRow = (subtask: PlannerSubtask) => {
    const assigneeLabel = getSubtaskAssignee(subtask, displayAssigneeLabel);
    const subtaskEditable = canEditTeam(subtask.teamId);
    const isEditing = editingSubtaskId === subtask.id && editingSubtaskDraft;

    return (
      <Flex style={{ backgroundColor: 'aqua' }} justify={'space-between'} align="center" key={subtask.id}>
        {/*Список подзадач */}
        {isEditing ? (
          renderSubtaskEditor(subtask)
        ) : (
          <Flex vertical>
            <Text>{subtask.title}</Text>
            <Flex gap={8}>
              <Text>{formatDate(subtask.startDate)} - {formatDate(subtask.endDate)}</Text>
              <Text>{assigneeLabel}</Text>
              <Text>{subtask.status}</Text>
            </Flex>
          </Flex>
        )}

        <Flex>
          {subtaskEditable &&
            (isEditing ? (
              <Flex gap={8}>
                <Button size="large" icon={<SaveFilled />} onClick={onSaveEditedSubtask} />
                <Button size="large" icon={<CloseCircleFilled />} onClick={onCancelEditSubtask} />
              </Flex>
            ) : (
              <Flex gap={8}>
                <Button size="large" icon={<EditFilled />} onClick={() => onStartEditSubtask(subtask.id)} />
                <Popconfirm
                  title="Вы уверены, что хотите удалить эту подзадачу?"
                  onConfirm={() => onDeleteSubtask(subtask.id)}
                  okText="Да"
                  cancelText="Нет">
                  <Button size="large" icon={<DeleteFilled />} />
                </Popconfirm>
              </Flex>
            ))}
        </Flex>
      </Flex>
    );
  };

  return (
    <Flex vertical gap={16}>
      {/* Шапка бэклога */}
      <Flex style={{ backgroundColor: 'blue' }} justify={'space-between'} align={'center'}>
        <Flex align="center" gap={8}>
          <Text>Бэклог команды:</Text>
          <Select
            size="large"
            value={teamFilter || ""}
            onChange={(value) => onTeamFilterChange(String(value))}
            options={
              visibleTeams.length === 0
                ? [{ value: "", label: "Нет команд" }]
                : visibleTeams.map((team) => ({ value: String(team.id), label: team.name }))
            }
          />
        </Flex>

        <Flex gap={16}>
          <Text>{filteredParents.length} задач</Text>
          <Text>{filteredSubtasks.length} подзадач</Text>
        </Flex>

        <Select
          size="large"
          value={assigneeFilter}
          onChange={(value) => onAssigneeFilterChange(String(value))}
          options={assigneeFilterOptions}
        />
      </Flex>

      {/*Список всех больших задач */}
      <Flex style={{ backgroundColor: 'red' }} vertical gap={16}>
        {filteredParents.length === 0 && <div>Пока нет больших задач для выбранной команды</div>}

        {filteredParents.map((parent) => {
          const parentSubtasks = getParentSubtasks(parent.id);
          const isOpen = Boolean(openParentById[parent.id] ?? Number(selectedParentId) === Number(parent.id)) || editingParentId === parent.id;
          const editable = canEditTeam(parent.teamId);
          const parentAssignee = parent.assigneeId ? formatAssigneeName(displayAssigneeLabel(parent.assigneeId)) : "Исполнитель не назначен";

          return (
            <Flex vertical key={parent.id}>
              <Flex justify="space-between" align="center">
                <Flex align="center" wrap style={{ backgroundColor: 'yellow', width: '100%' }} gap={16} onClick={() => toggleParent(parent.id)}>
                  <Button icon={isOpen ? <CaretDownFilled /> : <CaretRightFilled />} />
                  <Text>{parent.title}</Text>
                  <Text>{parentSubtasks.length} подзадач</Text>
                  <Text>{formatDate(parent.startDate)} - {formatDate(parent.endDate)}</Text>
                  <Text>{parentAssignee}</Text>
                </Flex>

                <Flex>
                  {editable &&
                    (editingParentId === parent.id ? (
                      <Flex gap={8}>
                        <Button size="large" icon={<SaveFilled />}
                          onClick={(event) => runHeaderAction(event, onSaveEditedParent)} />
                        <Button size="large" icon={<CloseCircleFilled />}
                          onClick={(event) => runHeaderAction(event, onCancelEditParent)} />
                      </Flex>
                    ) : (
                      <Flex gap={8}>
                        <Button size="large" icon={<EditFilled />}
                          onClick={() => onStartEditParent(parent.id)} />
                        <Popconfirm
                          title="Вы уверены, что хотите удалить эту задачу?"
                          onConfirm={() => onDeleteParent(parent.id)}
                          okText="Да"
                          cancelText="Нет">
                          <Button size="large" icon={<DeleteFilled />} />
                        </Popconfirm>
                      </Flex>
                    ))}
                </Flex>
              </Flex>

              {isOpen && (
                <Flex style={{ marginLeft: 64 }} gap={8} vertical>
                  {editingParentId === parent.id && editingParentDraft && renderParentEditor(parent)}

                  <Flex gap={8} vertical>
                    {parentSubtasks.length === 0 ? (
                      <Text>Подзадач пока нет.</Text>
                    ) : (
                      parentSubtasks.map(renderSubtaskRow)
                    )}
                  </Flex>

                  {/** Создание подзадач */}
                  <Flex gap={8} style={{ backgroundColor: 'orange' }} vertical>
                    <Text>Новая подзадача</Text>
                    <Input value={subTitle} onChange={(event) => onSubTitleChange(event.target.value)} placeholder="Название подзадачи" />
                    <Flex gap={8}>
                      <Select
                        value={subAssigneeId || "0"}
                        onChange={(value) => onSubAssigneeChange(String(value))}
                        options={[
                          { value: "0", label: "Без ответственного" },
                          ...selectedTeamMembers.map((id) => ({ value: String(id), label: formatAssigneeName(displayAssigneeLabel(Number(id))) })),
                        ]}
                      />
                      <DatePicker
                        format="DD.MM.YYYY"
                        value={subStart}
                        onChange={(date) => onSubStartChange(date ? date : undefined)}
                      />
                      <DatePicker
                        format="DD.MM.YYYY"
                        value={subEnd}
                        onChange={(date) => onSubEndChange(date ? date : undefined)}
                      />
                    </Flex>
                    <Flex>
                      <Button onClick={onAddSubtask}>
                        Создать подзадачу
                      </Button>
                    </Flex>
                  </Flex>
                </Flex>
              )}
            </Flex>
          );
        })}
      </Flex>

      {/* Создание новой большой задачи */}
      <Flex style={{ backgroundColor: 'green' }} vertical gap={8}>
        <Flex>
          <Text>Новая большая задача</Text>
        </Flex>
        <Flex>
          <Input value={parentTitle} onChange={(event) => onParentTitleChange(event.target.value)} placeholder="Название большой задачи" />
        </Flex>
        <Flex gap={8}>
          <Select
            value={parentAssigneeId || "0"}
            onChange={(value) => onParentAssigneeChange(String(value))}
            options={[
              { value: "0", label: "Без ответственного" },
              ...activeTeamMembers.map((id) => ({ value: String(id), label: formatAssigneeName(displayAssigneeLabel(Number(id))) })),
            ]}
          />
          <DatePicker
            format="DD.MM.YYYY"
            value={parentStart}
            onChange={(date) => onParentStartChange(date ? date : undefined)}
          />
          <DatePicker
            format="DD.MM.YYYY"
            value={parentEnd}
            onChange={(date) => onParentEndChange(date ? date : undefined)}
          />
        </Flex>
        <Flex>
          <Button onClick={onAddParentTask}>
            Создать задачу
          </Button>
        </Flex>
      </Flex>
    </Flex>
  );
}
