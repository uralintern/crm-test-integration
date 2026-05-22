import type { CSSProperties } from "react";
import type { BoardItem } from "react-kanban-kit";
import type { PlannerSubtask } from "../../../../types/planner";
import { isDoneKanbanStatus } from "../../planner.utils";

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

const cardThemes = [
  { accent: "#7c3aed", soft: "#f3e8ff" },
  { accent: "#0ea5e9", soft: "#e0f2fe" },
  { accent: "#f97316", soft: "#ffedd5" },
  { accent: "#10b981", soft: "#d1fae5" },
  { accent: "#ef4444", soft: "#fee2e2" },
  { accent: "#6366f1", soft: "#e0e7ff" },
];

const columnThemes = ["#2563eb", "#f59e0b", "#8b5cf6", "#22c55e", "#ef4444", "#0f766e"];

export const getColumnId = (title: string) => `${COLUMN_PREFIX}${encodeURIComponent(title)}`;
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

const getInitials = (label: string) => {
  const name = label.split("-")[0]?.trim() || label.trim();
  const parts = name.split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";

  return parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
};

const getCardTheme = (subtaskId: number) => cardThemes[Math.abs(subtaskId) % cardThemes.length];

export const getColumnTheme = (title: string, index: number) => columnThemes[(title.length + index) % columnThemes.length];

export function renderSubtaskCard(
  card: BoardItem,
  isDraggable: boolean,
  displayAssigneeLabel: (id: number) => string,
  currentUserId: number,
  extraClass = ""
) {
  const subtask = getCardSubtask(card);
  const isDone = isDoneKanbanStatus(subtask?.status);
  const className = ["kanban-card", isDone ? "is-done" : "", !isDraggable ? "is-locked" : "", extraClass]
    .filter(Boolean)
    .join(" ");

  if (!subtask) {
    return (
      <div className={className}>
        <div className="kanban-card-title">{card.title}</div>
      </div>
    );
  }

  const theme = getCardTheme(subtask.id);
  const assigneeLabel = subtask.assigneeId ? displayAssigneeLabel(subtask.assigneeId) : "Не назначен";
  const isCurrentAssignee = Boolean(subtask.assigneeId && Number(subtask.assigneeId) === Number(currentUserId));
  const style = {
    "--kanban-card-accent": theme.accent,
    "--kanban-card-soft": theme.soft,
  } as CSSProperties;

  return (
    <div className={className} style={style}>
      <div className="kanban-card-code">Задача - {String(subtask.id).padStart(4, "0")}</div>
      <div className="kanban-card-title">{subtask.title}</div>
      <div className="kanban-card-meta">
        <span>{subtask.startDate}</span>
        <span>{subtask.endDate}</span>
      </div>
      <div className="kanban-card-footer">
        <div className="kanban-card-tags">
          <span>Спринт</span>
          <span>{subtask.status}</span>
        </div>
        <div className={`kanban-card-assignee${isCurrentAssignee ? " is-current-assignee" : ""}`} title={assigneeLabel}>
          {getInitials(assigneeLabel)}
        </div>
      </div>
    </div>
  );
}
