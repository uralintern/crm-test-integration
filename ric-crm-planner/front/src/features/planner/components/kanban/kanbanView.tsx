import type { CSSProperties } from "react";
import type { BoardItem } from "react-kanban-kit";
import type { PlannerSubtask } from "../../../../types/planner";
import { isDoneKanbanStatus } from "../../planner.utils";
import type { Dayjs } from "dayjs";
import dayjs from "dayjs";
import { Button, Flex, Tag } from "antd";

export const ROOT_ID = "root";
export const COLUMN_DRAG_TYPE = "application/x-ric-kanban-column";

const COLUMN_PREFIX = "column:";
const CARD_PREFIX = "subtask:";

export type KanbanCardContent = {
  subtask: PlannerSubtask;
};

export type KanbanColumnContent = {
  title: string;
};

const getCardTheme = (parentTaskId: number) => {
  const id = Number(parentTaskId) || 0;
  const hue = Math.abs((id * 2654435761) % 360);
  const accent = `hsl(${hue}, 65%, 45%)`;
  const soft = `hsl(${hue}, 90%, 96%)`;
  return { accent, soft };
};

const columnThemes = [
  "#2563eb",
  "#f59e0b",
  "#8b5cf6",
  "#22c55e",
  "#ef4444",
  "#0f766e",
];

export const getColumnId = (title: string) =>
  `${COLUMN_PREFIX}${encodeURIComponent(title)}`;
export const getCardId = (id: number) => `${CARD_PREFIX}${id}`;

export const getSubtaskIdFromCardId = (cardId: string) => {
  if (!cardId.startsWith(CARD_PREFIX)) return null;
  const id = Number(cardId.slice(CARD_PREFIX.length));
  return Number.isFinite(id) ? id : null;
};

export const getCardSubtask = (card: BoardItem) => {
  const content = card.content as Partial<KanbanCardContent> | undefined;
  return content?.subtask ?? null;
};

export const getColumnTitle = (column: BoardItem) => {
  const content = column.content as Partial<KanbanColumnContent> | undefined;
  return content?.title || column.title;
};

const formatDate = (date: Dayjs | undefined): string =>
  date ? dayjs(date).format("DD.MM.YYYY") : "Нет срока";

export const getColumnTheme = (title: string, index: number) =>
  columnThemes[(title.length + index) % columnThemes.length];

export function renderSubtaskCard(
  card: BoardItem,
  isDraggable: boolean,
  displayAssigneeLabel: (id: number) => string,
  _currentUserId: number,
  onCompleteSubtask?: (subtaskId: number) => void,
  extraClass = "",
) {
  const subtask = getCardSubtask(card);
  const isDone = isDoneKanbanStatus(subtask?.status);
  const className = [
    "kanban-card",
    isDone ? "is-done" : "",
    !isDraggable ? "is-locked" : "",
    extraClass,
  ]
    .filter(Boolean)
    .join(" ");

  if (!subtask) {
    return (
      <div className={className}>
        <div className="kanban-card-title">{card.title}</div>
      </div>
    );
  }

  const theme = getCardTheme(subtask.parentTaskId ?? subtask.id);
  const assigneeLabel = subtask.assigneeId
    ? displayAssigneeLabel(subtask.assigneeId)
    : "Не назначен";
  const style = {
    "--kanban-card-accent": theme.accent,
    "--kanban-card-soft": theme.soft,
  } as CSSProperties;

  return (
    <div className={className} style={style}>
      <div className="kanban-card-title">{subtask.title}</div>
      <div className="kanban-card-meta">
        <span>{formatDate(subtask.startDate)}</span>
        <span>{formatDate(subtask.endDate)}</span>
      </div>
      <Flex>
        <Flex gap={8} vertical>
          <Tag color={theme.accent}>{subtask.status}</Tag>
          <Tag>{assigneeLabel}</Tag>
          <Button
            onClick={(e) => {
              e.stopPropagation();
              if (onCompleteSubtask) {
                onCompleteSubtask(subtask.id);
              }
            }}
            disabled={isDone}
            color={isDone ? undefined : "green"}
            variant={isDone ? undefined : "solid"}
          >
            {isDone ? "Завершено" : "Завершить задачу"}
          </Button>
        </Flex>
      </Flex>
    </div>
  );
}
