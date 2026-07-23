import { useEffect, useState } from "react";
import dayjs, { type Dayjs } from "dayjs";
import type {
  PlannerParentTask,
  PlannerSubtask,
  PlannerTaskChecklistItem,
  PlannerTeam,
} from "../../../../types/planner";
import {
  Flex,
  Input,
  Button,
  Typography,
  DatePicker,
  Modal,
  Checkbox,
  Switch,
  Select,
} from "antd";
import { CloseOutlined } from "@ant-design/icons";
import { DONE_KANBAN_STATUS, PLANNED_KANBAN_STATUS } from "../../planner.utils";

const { TextArea } = Input;
const { Text, Title } = Typography;

type TaskCardModalProps = {
  isOpen: boolean;
  taskCardParent: PlannerParentTask | null;
  taskCardSubtask: PlannerSubtask | null;
  taskCardTeam: PlannerTeam | null;
  taskCardParentForSubtask: PlannerParentTask | null;
  taskCardSubtasksCount: number;
  selectedTeamMembers: number[];
  displayAssigneeLabel: (id: number) => string;
  sourceLabelForTeam: (team: PlannerTeam) => string;
  onClose: () => void;
  onUpdateParentTask: (
    taskId: number,
    updates: Partial<
      Pick<
        PlannerParentTask,
        | "title"
        | "description"
        | "checklist"
        | "startDate"
        | "endDate"
        | "assigneeId"
        | "status"
      >
    >,
  ) => void;
  onUpdateSubtask: (
    subtaskId: number,
    updates: Partial<
      Pick<
        PlannerSubtask,
        | "title"
        | "description"
        | "checklist"
        | "startDate"
        | "endDate"
        | "assigneeId"
        | "inSprint"
        | "status"
      >
    >,
  ) => void;
  onCreateSubtaskFromChecklistItem: (parentTaskId: number, title: string) => void;
};

export default function TaskCardModal({
  isOpen,
  taskCardParent,
  taskCardSubtask,
  onClose,
  onUpdateParentTask,
  onUpdateSubtask,
  onCreateSubtaskFromChecklistItem,
  displayAssigneeLabel,
  selectedTeamMembers,
}: TaskCardModalProps) {
  const activeTask = taskCardSubtask || taskCardParent;
  const startDate = taskCardSubtask?.startDate || taskCardParent?.startDate;
  const endDate = taskCardSubtask?.endDate || taskCardParent?.endDate;

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [start, setStart] = useState<Dayjs | undefined>();
  const [end, setEnd] = useState<Dayjs | undefined>();
  const [checklistInput, setChecklistInput] = useState("");
  const [inSprint, setInSprint] = useState<boolean | undefined>();
  const [checklist, setChecklist] = useState<PlannerTaskChecklistItem[]>([]);
  const [assignee, setAssignee] = useState<number | undefined>();

  const memberOptions = (ids: number[]) =>
    ids.map((id) => ({
      value: id,
      label: displayAssigneeLabel(id),
    }));

  useEffect(() => {
    if (!isOpen || !activeTask) return;

    setTitle(activeTask.title || "");
    setDescription(activeTask.description || "");
    setStart(startDate ? dayjs(startDate) : undefined);
    setEnd(endDate ? dayjs(endDate) : undefined);
    setChecklistInput("");
    setChecklist(activeTask.checklist || []);
    setInSprint(taskCardSubtask?.inSprint);
    setAssignee(activeTask?.assigneeId);
  }, [activeTask, endDate, isOpen, startDate, taskCardSubtask?.inSprint]);

  const addChecklistItem = () => {
    const text = checklistInput.trim();

    if (!text) return;

    setChecklist((items) => [
      ...items,
      { id: Date.now(), text, completed: false },
    ]);
    setChecklistInput("");
  };

  const toggleChecklistItem = (itemId: number) => {
    const nextChecklist = checklist.map((item) =>
      item.id === itemId ? { ...item, completed: !item.completed } : item,
    );

    const allCompleted = nextChecklist.every((item) => item.completed);
    const nextStatus = allCompleted ? DONE_KANBAN_STATUS : undefined;

    setChecklist(nextChecklist);

    if (taskCardSubtask) {
      onUpdateSubtask(taskCardSubtask.id, {
        checklist: nextChecklist,
        status: allCompleted
          ? DONE_KANBAN_STATUS
          : taskCardSubtask.status || PLANNED_KANBAN_STATUS,
      });
    } else if (taskCardParent) {
      onUpdateParentTask(taskCardParent.id, {
        checklist: nextChecklist,
        status: nextStatus,
      });
    }
  };

  const removeChecklistItem = (itemId: number) => {
    setChecklist((items) => items.filter((item) => item.id !== itemId));
  };

  const saveTaskCard = () => {
    if (!activeTask) {
      onClose();
      return;
    }

    const allChecklistCompleted = checklist.length > 0 && checklist.every((item) => item.completed);
    const updates = {
      title: title.trim() || activeTask.title,
      description: description.trim(),
      checklist,
      startDate: start,
      endDate: end,
      inSprint: inSprint,
      assigneeId: assignee,
      status: allChecklistCompleted
        ? DONE_KANBAN_STATUS
        : taskCardSubtask
          ? taskCardSubtask.status || PLANNED_KANBAN_STATUS
          : undefined,
    };

    if (taskCardSubtask) {
      onUpdateSubtask(taskCardSubtask.id, updates);
    } else if (taskCardParent) {
      onUpdateParentTask(taskCardParent.id, updates);
    }

    onClose();
  };

  return (
    <Modal
      open={isOpen}
      onCancel={onClose}
      onOk={saveTaskCard}
      okText="Сохранить"
      cancelText="Отмена"
    >
      {!activeTask ? (
        <Text>Задача не найдена.</Text>
      ) : (
        <Flex gap={16} vertical>
          <Flex vertical>
            <Title
              level={3}
              editable={{
                text: title,
                onChange: (newTitle) => setTitle(newTitle),
                triggerType: ["icon", "text"],
              }}
            >
              {title}
            </Title>
            <Select
              value={displayAssigneeLabel(assignee || 0)}
              onChange={(value) => setAssignee(Number(value))}
              options={[
                {
                  value: 0,
                  label: "Без ответственного",
                },
                ...memberOptions(selectedTeamMembers),
              ]}
            />
          </Flex>

          <Flex vertical>
            <Text>Описание</Text>
            <TextArea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Добавьте описание задачи"
              autoSize
            />
          </Flex>

          <Flex gap={8} vertical>
            <Text>Чеклист</Text>
            <Flex gap={8}>
              <Input
                value={checklistInput}
                onChange={(event) => setChecklistInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") addChecklistItem();
                }}
                placeholder="Добавить пункт чеклиста"
              />
              <Button onClick={addChecklistItem}>Добавить</Button>
            </Flex>

            <Flex gap={8} vertical>
              {checklist.map((item) => (
                <Flex justify="space-between" align="center" key={item.id}>
                  <Flex gap={4}>
                    <Checkbox
                      checked={item.completed}
                      onChange={() => toggleChecklistItem(item.id)}
                    />
                    <Text delete={item.completed}>{item.text}</Text>
                  </Flex>
                  <Flex gap={4}>
                    <Button
                      size="small"
                      onClick={() => {
                        const parentTaskId = taskCardSubtask?.parentTaskId || taskCardParent?.id;
                        if (parentTaskId) {
                          onCreateSubtaskFromChecklistItem(parentTaskId, item.text);
                        }
                      }}
                    >
                      Создать подзадачу
                    </Button>
                    <Button
                      variant="outlined"
                      color="red"
                      size="small"
                      onClick={() => removeChecklistItem(item.id)}
                      icon={<CloseOutlined />}
                    />
                  </Flex>
                </Flex>
              ))}
            </Flex>
          </Flex>

          <Flex gap={8} vertical>
            <Text>Сроки</Text>
            <Flex gap={4} align="center">
              <Text>Начало</Text>
              <DatePicker
                format="DD.MM.YYYY"
                value={start}
                onChange={(value) => setStart(value ?? undefined)}
                getPopupContainer={(node) => node.parentNode as HTMLElement}
              />
            </Flex>
            <Flex gap={4} align="center">
              <Text>Крайний срок</Text>
              <DatePicker
                format="DD.MM.YYYY"
                value={end}
                onChange={(value) => setEnd(value ?? undefined)}
                getPopupContainer={(node) => node.parentNode as HTMLElement}
              />
              {taskCardSubtask && (
                <Switch
                  checked={inSprint}
                  onChange={(checked) => setInSprint(checked)}
                  checkedChildren="В спринт"
                  unCheckedChildren="Не в спринт"
                />
              )}
            </Flex>
          </Flex>
        </Flex>
      )}
    </Modal>
  );
}
