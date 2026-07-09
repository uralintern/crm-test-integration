import { useState, type Dispatch, type SetStateAction } from "react";
import type {
  PlannerParentTask,
  PlannerSubtask,
  PlannerTeam,
} from "../../../../types/planner";
import type { ParentEditDraft, SubtaskEditDraft } from "../../planner.types";
import {
  Badge,
  Button,
  Card,
  DatePicker,
  Empty,
  Flex,
  Input,
  Popconfirm,
  Select,
  Space,
  Statistic,
  Switch,
  Tag,
  Typography,
} from "antd";
import {
  CalendarOutlined,
  CaretDownFilled,
  CaretRightFilled,
  CloseOutlined,
  DeleteOutlined,
  EditOutlined,
  FilterOutlined,
  FolderOpenOutlined,
  PlusOutlined,
  SaveFilled,
  TeamOutlined,
  UserOutlined,
} from "@ant-design/icons";
import type { Dayjs } from "dayjs";
import dayjs from "dayjs";

const { Text, Title } = Typography;

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
  assigneeFilterOptions: Array<{
    value: string;
    label: string;
    disabled?: boolean;
  }>;
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

const getSubtaskAssignee = (
  subtask: PlannerSubtask,
  displayAssigneeLabel: (id: number) => string,
) => {
  if (subtask.assigneeId)
    return formatAssigneeName(displayAssigneeLabel(subtask.assigneeId));
  return subtask.role || "Исполнитель не назначен";
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
  onTeamFilterChange,
  subInSprint,
  onSubInSprintChange,
}: BacklogTabProps) {
  const [openParentById, setOpenParentById] = useState<Record<number, boolean>>(
    {},
  );

  const getParentSubtasks = (parentId: number) =>
    filteredSubtasks.filter(
      (subtask) => Number(subtask.parentTaskId) === Number(parentId),
    );

  const toggleParent = (parentId: number) => {
    const fallbackOpen = Number(selectedParentId) === Number(parentId);
    setOpenParentById((prev) => ({
      ...prev,
      [parentId]: !(prev[parentId] ?? fallbackOpen),
    }));
    onSelectParent(parentId);
  };

  const formatDate = (date: Dayjs | undefined): string =>
    date ? dayjs(date).format("DD.MM.YYYY") : "Нет срока";

  const memberOptions = (ids: number[]) =>
    ids.map((id) => ({
      value: String(id),
      label: formatAssigneeName(displayAssigneeLabel(Number(id))),
    }));

  const renderParentEditor = (parent: PlannerParentTask) => (
    <Flex gap={12} wrap>
      <Input
        value={editingParentDraft?.title ?? ""}
        onChange={(event) =>
          setEditingParentDraft((prev) =>
            prev ? { ...prev, title: event.target.value } : prev,
          )
        }
        placeholder="Название большой задачи"
      />
      <Select
        value={
          editingParentDraft?.assigneeId != null
            ? String(editingParentDraft.assigneeId)
            : ""
        }
        onChange={(value) =>
          setEditingParentDraft((prev) =>
            prev
              ? { ...prev, assigneeId: value ? Number(value) : undefined }
              : prev,
          )
        }
        options={[
          { value: "", label: "Без ответственного" },
          ...memberOptions(getTeamMemberIds(parent.teamId)),
        ]}
      />
      <DatePicker
        format="DD.MM.YYYY"
        placeholder="Начало"
        value={editingParentDraft?.startDate}
        onChange={(startDate) =>
          setEditingParentDraft((state) =>
            state ? { ...state, startDate: startDate ?? undefined } : null,
          )
        }
      />
      <DatePicker
        format="DD.MM.YYYY"
        placeholder="Срок"
        value={editingParentDraft?.endDate}
        onChange={(endDate) =>
          setEditingParentDraft((state) =>
            state ? { ...state, endDate: endDate ?? undefined } : null,
          )
        }
      />
    </Flex>
  );

  const renderSubtaskEditor = (subtask: PlannerSubtask) => (
    <Flex gap={12} align="center" wrap>
      <Input
        value={editingSubtaskDraft?.title ?? ""}
        onChange={(event) =>
          setEditingSubtaskDraft((prev) =>
            prev ? { ...prev, title: event.target.value } : prev,
          )
        }
        placeholder="Название подзадачи"
      />
      <Select
        value={
          editingSubtaskDraft?.assigneeId != null
            ? String(editingSubtaskDraft.assigneeId)
            : "0"
        }
        onChange={(value) =>
          setEditingSubtaskDraft((prev) =>
            prev ? { ...prev, assigneeId: Number(value) } : prev,
          )
        }
        options={[
          { value: "0", label: "Без ответственного" },
          ...memberOptions(getTeamMemberIds(subtask.teamId)),
        ]}
      />
      <DatePicker
        format="DD.MM.YYYY"
        placeholder="Начало"
        value={editingSubtaskDraft?.startDate}
        onChange={(startDate) =>
          setEditingSubtaskDraft((state) =>
            state ? { ...state, startDate: startDate ?? undefined } : null,
          )
        }
      />
      <DatePicker
        format="DD.MM.YYYY"
        placeholder="Срок"
        value={editingSubtaskDraft?.endDate}
        onChange={(endDate) =>
          setEditingSubtaskDraft((state) =>
            state ? { ...state, endDate: endDate ?? undefined } : null,
          )
        }
      />
      <Switch
        checked={Boolean(editingSubtaskDraft?.inSprint)}
        onChange={(checked) =>
          setEditingSubtaskDraft((prev) =>
            prev ? { ...prev, inSprint: checked } : prev,
          )
        }
        checkedChildren="В спринт"
        unCheckedChildren="Не в спринт"
      />
    </Flex>
  );

  const renderSubtaskRow = (subtask: PlannerSubtask) => {
    const assigneeLabel = getSubtaskAssignee(subtask, displayAssigneeLabel);
    const subtaskEditable = canEditTeam(subtask.teamId);
    const isEditing = editingSubtaskId === subtask.id && editingSubtaskDraft;

    return (
      <Card key={subtask.id} className="backlog-subtask-card" size="small">
        <Flex justify="space-between" gap={12}>
          {isEditing ? (
            renderSubtaskEditor(subtask)
          ) : (
            <Flex gap={6} vertical>
              <Button
                type="link"
                className="backlog-title-link"
                onClick={() => onOpenTaskCard("subtask", subtask.id)}
              >
                {subtask.title}
              </Button>
              <Flex gap={12} wrap>
                <Tag icon={<CalendarOutlined />}>
                  {formatDate(subtask.startDate)} —{" "}
                  {formatDate(subtask.endDate)}
                </Tag>
                <Tag
                  icon={<UserOutlined />}
                  color={subtask.assigneeId ? "blue" : "default"}
                >
                  {assigneeLabel}
                </Tag>
                {subtask.inSprint && (
                  <Tag color={"green"} variant="solid">
                    В спринте
                  </Tag>
                )}
                <Tag>{subtask.status}</Tag>
              </Flex>
            </Flex>
          )}

          {subtaskEditable &&
            (isEditing ? (
              <Flex gap={12}>
                <Button
                  color="green"
                  variant="solid"
                  size="large"
                  icon={<SaveFilled />}
                  onClick={onSaveEditedSubtask}
                />
                <Button
                  color="red"
                  variant="solid"
                  size="large"
                  icon={<CloseOutlined />}
                  onClick={onCancelEditSubtask}
                />
              </Flex>
            ) : (
              <Flex gap={12}>
                <Button
                  size="large"
                  icon={<EditOutlined />}
                  onClick={(event) => {
                    event.stopPropagation();
                    onStartEditSubtask(subtask.id);
                  }}
                />
                <Popconfirm
                  title="Вы уверены, что хотите удалить эту подзадачу?"
                  onConfirm={(event) => {
                    event?.stopPropagation();
                    onDeleteSubtask(subtask.id);
                  }}
                  okText="Да"
                  cancelText="Нет"
                >
                  <Button size="large" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              </Flex>
            ))}
        </Flex>
      </Card>
    );
  };

  return (
    <div className="planner-stack backlog-tab">
      <Card className="planner-card backlog-hero">
        <Flex justify="space-between" gap={16} wrap align="center">
          <Space vertical size={4}>
            <Text className="teams-eyebrow">Бэклог команды</Text>
            <Title level={3} className="backlog-title">
              {activeTeamName || "Выберите команду"}
            </Title>
          </Space>
          <Space size={[12, 12]} wrap>
            <Statistic title="Большие задачи" value={filteredParents.length} />
            <Statistic title="Подзадачи" value={filteredSubtasks.length} />
          </Space>
        </Flex>

        <Flex wrap style={{ marginTop: 16 }} gap={12}>
          <Flex style={{ width: "100%" }} vertical>
            <span>
              <TeamOutlined /> Команда
            </span>
            <Select
              size="large"
              value={teamFilter || ""}
              onChange={(value) => onTeamFilterChange(String(value))}
              options={
                visibleTeams.length === 0
                  ? [{ value: "", label: "Нет команд" }]
                  : visibleTeams.map((team) => ({
                      value: String(team.id),
                      label: team.name,
                    }))
              }
            />
          </Flex>
          <Flex style={{ width: "100%" }} vertical>
            <span>
              <FilterOutlined /> Исполнитель
            </span>
            <Select
              size="large"
              value={assigneeFilter}
              onChange={(value) => onAssigneeFilterChange(String(value))}
              options={assigneeFilterOptions}
            />
          </Flex>
        </Flex>
      </Card>

      <div className="backlog-list">
        {filteredParents.length === 0 && (
          <Empty
            className="planner-card"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="Пока нет больших задач для выбранной команды"
          />
        )}

        {filteredParents.map((parent) => {
          const parentSubtasks = getParentSubtasks(parent.id);
          const isOpen =
            Boolean(
              openParentById[parent.id] ??
              Number(selectedParentId) === Number(parent.id),
            ) || editingParentId === parent.id;
          const editable = canEditTeam(parent.teamId);
          const parentAssignee = parent.assigneeId
            ? formatAssigneeName(displayAssigneeLabel(parent.assigneeId))
            : "Исполнитель не назначен";

          return (
            <Card
              key={parent.id}
              styles={{ body: { padding: 8 } }}
              className={`backlog-parent-card ${isOpen ? "is-open" : ""}`}
              onClick={(event) => {
                event.stopPropagation();
                toggleParent(parent.id);
              }}
            >
              <Flex justify="space-between" gap={12}>
                <Flex gap={12}>
                  <span className="backlog-expander">
                    {isOpen ? <CaretDownFilled /> : <CaretRightFilled />}
                  </span>
                  <span className="backlog-task-copy">
                    <Flex gap={12} align="center">
                      <Text
                        strong
                        className="backlog-parent-title"
                        onClick={(event) => {
                          event.stopPropagation();
                          onOpenTaskCard("parent", parent.id);
                        }}
                      >
                        {parent.title}
                      </Text>
                      <Badge
                        count={parentSubtasks.length}
                        overflowCount={99}
                        color="#2563eb"
                      />
                    </Flex>
                    <Flex gap={12} wrap>
                      <Tag icon={<CalendarOutlined />}>
                        {formatDate(parent.startDate)} —{" "}
                        {formatDate(parent.endDate)}
                      </Tag>
                      <Tag
                        icon={<UserOutlined />}
                        color={parent.assigneeId ? "blue" : "default"}
                      >
                        {parentAssignee}
                      </Tag>
                    </Flex>
                  </span>
                </Flex>
                {editable &&
                  (editingParentId === parent.id ? (
                    <Flex gap={12}>
                      <Button
                        color="green"
                        size="large"
                        variant="solid"
                        icon={<SaveFilled />}
                        onClick={(event) => {
                          event.stopPropagation();
                          onSaveEditedParent();
                        }}
                      />
                      <Button
                        color="red"
                        size="large"
                        variant="solid"
                        icon={<CloseOutlined />}
                        onClick={(event) => {
                          event.stopPropagation();
                          onCancelEditParent();
                        }}
                      />
                    </Flex>
                  ) : (
                    <Flex gap={12}>
                      <Button
                        size="large"
                        icon={<EditOutlined />}
                        onClick={(event) => {
                          event.stopPropagation();
                          onStartEditParent(parent.id);
                        }}
                      />
                      <Popconfirm
                        title="Вы уверены, что хотите удалить эту задачу?"
                        onConfirm={(event) => {
                          event?.stopPropagation();
                          onDeleteParent(parent.id);
                        }}
                        okText="Да"
                        cancelText="Нет"
                      >
                        <Button danger size="large" icon={<DeleteOutlined />} />
                      </Popconfirm>
                    </Flex>
                  ))}
              </Flex>

              {isOpen && (
                <div
                  className="backlog-parent-content"
                  onClick={(event) => event.stopPropagation()}
                >
                  {editingParentId === parent.id &&
                    editingParentDraft &&
                    renderParentEditor(parent)}
                  <Space vertical size={10} className="backlog-subtask-list">
                    {parentSubtasks.length === 0 ? (
                      <Empty
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                        description="Подзадач пока нет"
                      />
                    ) : (
                      parentSubtasks.map(renderSubtaskRow)
                    )}
                  </Space>
                  <Card
                    size="small"
                    className="backlog-create-card"
                    title={
                      <Space>
                        <PlusOutlined />
                        Новая подзадача
                      </Space>
                    }
                    onClick={(event) => event.stopPropagation()}
                  >
                    <Flex gap={12} vertical justify="space-between">
                      <Flex gap={12}>
                        <Input
                          value={subTitle}
                          onChange={(event) =>
                            onSubTitleChange(event.target.value)
                          }
                          placeholder="Название подзадачи"
                        />
                        <Button
                          type="primary"
                          icon={<PlusOutlined />}
                          onClick={onAddSubtask}
                        >
                          Создать подзадачу
                        </Button>
                      </Flex>
                      <Flex gap={12} align="center">
                        <Select
                          value={subAssigneeId || "0"}
                          onChange={(value) =>
                            onSubAssigneeChange(String(value))
                          }
                          options={[
                            { value: "0", label: "Без ответственного" },
                            ...memberOptions(selectedTeamMembers),
                          ]}
                        />
                        <DatePicker
                          format="DD.MM.YYYY"
                          value={subStart}
                          onChange={(date) =>
                            onSubStartChange(date ? date : undefined)
                          }
                          placeholder="Начало"
                        />
                        <DatePicker
                          format="DD.MM.YYYY"
                          value={subEnd}
                          onChange={(date) =>
                            onSubEndChange(date ? date : undefined)
                          }
                          placeholder="Срок"
                        />
                        <Switch
                          checked={subInSprint}
                          onChange={onSubInSprintChange}
                          checkedChildren="В спринт"
                          unCheckedChildren="Не в спринт"
                        />
                      </Flex>
                    </Flex>
                  </Card>
                </div>
              )}
            </Card>
          );
        })}
      </div>

      <Card
        className="planner-card backlog-create-card"
        title={
          <Space>
            <FolderOpenOutlined />
            Новая большая задача
          </Space>
        }
      >
        <Flex gap={12} vertical justify="space-between">
          <Flex gap={12}>
            <Input
              value={parentTitle}
              onChange={(event) => onParentTitleChange(event.target.value)}
              placeholder="Название большой задачи"
            />
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={onAddParentTask}
            >
              Создать задачу
            </Button>
          </Flex>
          <Flex gap={12}>
            <Select
              value={parentAssigneeId || "0"}
              onChange={(value) => onParentAssigneeChange(String(value))}
              options={[
                { value: "0", label: "Без ответственного" },
                ...memberOptions(activeTeamMembers),
              ]}
            />
            <DatePicker
              format="DD.MM.YYYY"
              value={parentStart}
              onChange={(date) => onParentStartChange(date ? date : undefined)}
              placeholder="Начало"
            />
            <DatePicker
              format="DD.MM.YYYY"
              value={parentEnd}
              onChange={(date) => onParentEndChange(date ? date : undefined)}
              placeholder="Срок"
            />
          </Flex>
        </Flex>
      </Card>
    </div>
  );
}
