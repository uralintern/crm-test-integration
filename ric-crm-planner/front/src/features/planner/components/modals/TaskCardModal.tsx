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
} from "antd";
import { CloseOutlined } from "@ant-design/icons";

const { TextArea } = Input;
const { Text, Title } = Typography;

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
  onUpdateParentTask: (
    taskId: number,
    updates: Partial<Pick<PlannerParentTask, "title" | "description" | "checklist" | "startDate" | "endDate">>,
  ) => void;
  onUpdateSubtask: (
    subtaskId: number,
    updates: Partial<Pick<PlannerSubtask, "title" | "description" | "checklist" | "startDate" | "endDate">>,
  ) => void;
};

export default function TaskCardModal({
  isOpen,
  taskCardParent,
  taskCardSubtask,
  displayAssigneeLabel,
  onClose,
  onUpdateParentTask,
  onUpdateSubtask,
}: TaskCardModalProps) {
  const activeTask = taskCardSubtask || taskCardParent;
  const startDate = taskCardSubtask?.startDate || taskCardParent?.startDate;
  const endDate = taskCardSubtask?.endDate || taskCardParent?.endDate;

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [start, setStart] = useState<Dayjs | undefined>();
  const [end, setEnd] = useState<Dayjs | undefined>();
  const [checklistInput, setChecklistInput] = useState("");
  const [checklist, setChecklist] = useState<PlannerTaskChecklistItem[]>([]);

  useEffect(() => {
    if (!isOpen || !activeTask) return;

    setTitle(activeTask.title || "");
    setDescription(activeTask.description || "");
    setStart(startDate ? dayjs(startDate) : undefined);
    setEnd(endDate ? dayjs(endDate) : undefined);
    setChecklistInput("");
    setChecklist(activeTask.checklist || []);
  }, [activeTask, endDate, isOpen, startDate]);

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
    setChecklist((items) =>
      items.map((item) =>
        item.id === itemId ? { ...item, completed: !item.completed } : item,
      ),
    );
  };

  const removeChecklistItem = (itemId: number) => {
    setChecklist((items) => items.filter((item) => item.id !== itemId));
  };

  const saveTaskCard = () => {
    if (!activeTask) {
      onClose();
      return;
    }

    const updates = {
      title: title.trim() || activeTask.title,
      description: description.trim(),
      checklist,
      startDate: start,
      endDate: end,
    };

    if (taskCardSubtask) {
      onUpdateSubtask(taskCardSubtask.id, updates);
    } else if (taskCardParent) {
      onUpdateParentTask(taskCardParent.id, updates);
    }

    onClose();
  };

  return (
    <Modal open={isOpen} onCancel={onClose} onOk={saveTaskCard} okText="Сохранить" cancelText="Отмена">
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
            {activeTask.assigneeId && (
              <Text type="secondary">Исполнитель: {displayAssigneeLabel(activeTask.assigneeId)}</Text>
            )}
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

            <Flex gap={4} vertical>
              {checklist.map((item) => (
                <Flex justify="space-between" align="center" key={item.id}>
                  <Flex gap={4}>
                    <Checkbox
                      checked={item.completed}
                      onChange={() => toggleChecklistItem(item.id)}
                    />
                    <Text delete={item.completed}>{item.text}</Text>
                  </Flex>
                  <Button
                    variant="outlined"
                    color="red"
                    size="small"
                    onClick={() => removeChecklistItem(item.id)}
                    icon={<CloseOutlined />}
                  />
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
            </Flex>
          </Flex>
        </Flex>
      )}
    </Modal>
  );
}
