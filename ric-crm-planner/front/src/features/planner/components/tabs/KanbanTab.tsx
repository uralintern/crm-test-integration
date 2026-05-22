import { useMemo, useState, type CSSProperties, type ComponentProps, type DragEvent } from "react";
import { Kanban, type BoardData } from "react-kanban-kit";
import type { PlannerSubtask } from "../../../../types/planner";
import AppButton from "../../../../components/UI/Button";
import AppInput from "../../../../components/UI/Input";
import {
  COLUMN_DRAG_TYPE,
  ROOT_ID,
  getCardId,
  getColumnId,
  getColumnTheme,
  getColumnTitle,
  getSubtaskIdFromCardId,
  renderSubtaskCard,
  type KanbanCardContent,
  type KanbanColumnContent,
} from "../kanban/kanbanView";

type ReactKanbanProps = ComponentProps<typeof Kanban>;
type CardMove = Parameters<NonNullable<ReactKanbanProps["onCardMove"]>>[0];
type KanbanTabProps = {
  newColumn: string;
  columns: string[];
  filteredSubtasks: PlannerSubtask[];
  canEditTeam: (teamId: number) => boolean;
  displayAssigneeLabel: (id: number) => string;
  currentUserId: number;
  onNewColumnChange: (value: string) => void;
  onAddColumn: () => void;
  onRemoveColumn: (title: string) => void;
  onOpenTaskCard: (type: "parent" | "subtask", id: number) => void;
  onMoveSubtask: (subtaskId: number, column: string, position: number) => void;
  onMoveColumn: (sourceTitle: string, targetTitle: string) => void;
};

export default function KanbanTab({
  newColumn,
  columns,
  filteredSubtasks,
  canEditTeam,
  displayAssigneeLabel,
  currentUserId,
  onNewColumnChange,
  onAddColumn,
  onRemoveColumn,
  onOpenTaskCard,
  onMoveSubtask,
  onMoveColumn,
}: KanbanTabProps) {
  const [draggingColumn, setDraggingColumn] = useState<string | null>(null);
  const [dragOverColumn, setDragOverColumn] = useState<string | null>(null);

  const { dataSource, columnTitleById } = useMemo(() => {
    const columnTitleMap = new Map<string, string>();
    const source: BoardData = {
      [ROOT_ID]: {
        id: ROOT_ID,
        title: "Root",
        parentId: null,
        children: columns.map(getColumnId),
        totalChildrenCount: columns.length,
      },
    };

    columns.forEach((title) => {
      const id = getColumnId(title);
      columnTitleMap.set(id, title);
      source[id] = {
        id,
        title,
        parentId: ROOT_ID,
        children: [],
        totalChildrenCount: 0,
        content: { title } satisfies KanbanColumnContent,
      };
    });

    filteredSubtasks
      .filter((subtask) => subtask.inSprint)
      .forEach((subtask) => {
        const columnTitle = columns.includes(subtask.status) ? subtask.status : columns[0];
        if (!columnTitle) return;

        const columnId = getColumnId(columnTitle);
        const cardId = getCardId(subtask.id);
        source[cardId] = {
          id: cardId,
          title: subtask.title,
          parentId: columnId,
          children: [],
          totalChildrenCount: 0,
          type: "card",
          isDraggable: canEditTeam(subtask.teamId),
          content: { subtask } satisfies KanbanCardContent,
        };
        source[columnId]?.children.push(cardId);
      });

    columns.forEach((title) => {
      const id = getColumnId(title);
      const column = source[id];
      if (!column) return;
      column.totalChildrenCount = column.children.length;
    });

    return { dataSource: source, columnTitleById: columnTitleMap };
  }, [canEditTeam, columns, filteredSubtasks]);

  const configMap = useMemo<ReactKanbanProps["configMap"]>(
    () => ({
      card: {
        isDraggable: true,
        render: ({ data, isDraggable }) => renderSubtaskCard(data, isDraggable, displayAssigneeLabel, currentUserId),
      },
    }),
    [currentUserId, displayAssigneeLabel]
  );

  const handleCardMove = (move: CardMove) => {
    const subtaskId = getSubtaskIdFromCardId(move.cardId);
    const nextColumn = columnTitleById.get(move.toColumnId);
    if (subtaskId == null || !nextColumn) return;
    onMoveSubtask(subtaskId, nextColumn, move.position);
  };

  const resetColumnDrag = () => {
    setDraggingColumn(null);
    setDragOverColumn(null);
  };

  const handleColumnDragStart = (event: DragEvent<HTMLDivElement>, title: string) => {
    event.stopPropagation();
    setDraggingColumn(title);
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData(COLUMN_DRAG_TYPE, title);
  };

  const handleColumnDragOver = (event: DragEvent<HTMLDivElement>, title: string) => {
    if (!draggingColumn || draggingColumn === title) return;
    event.preventDefault();
    event.stopPropagation();
    event.dataTransfer.dropEffect = "move";
    if (dragOverColumn !== title) setDragOverColumn(title);
  };

  const handleColumnDrop = (event: DragEvent<HTMLDivElement>, title: string) => {
    event.preventDefault();
    event.stopPropagation();
    const sourceTitle = draggingColumn || event.dataTransfer.getData(COLUMN_DRAG_TYPE);
    if (sourceTitle && sourceTitle !== title) onMoveColumn(sourceTitle, title);
    resetColumnDrag();
  };

  return (
    <div className="planner-stack">
      <div className="planner-card">
        <div className="planner-inline-form">
          <AppInput value={newColumn} onChange={(event) => onNewColumnChange(event.target.value)} placeholder="Новый статус" />
          <AppButton className="primary" onClick={onAddColumn}>
            Добавить
          </AppButton>
        </div>
      </div>

      <Kanban
        dataSource={dataSource}
        configMap={configMap}
        rootClassName="kanban-board kanban-board-kit"
        cardWrapperClassName="kanban-card-wrapper"
        cardsGap={8}
        virtualization={false}
        allowColumnAdder={false}
        allowListFooter={(column) => column.totalChildrenCount === 0}
        renderListFooter={() => <div className="kanban-empty">Нет задач в спринте</div>}
        renderColumnHeader={(column) => {
          const title = getColumnTitle(column);
          const columnIndex = columns.findIndex((columnTitle) => columnTitle === title);
          const style = {
            "--kanban-column-accent": getColumnTheme(title, Math.max(columnIndex, 0)),
          } as CSSProperties;
          const titleClassName = [
            "kanban-column-title",
            draggingColumn === title ? "is-dragging" : "",
            dragOverColumn === title ? "is-drag-over" : "",
          ]
            .filter(Boolean)
            .join(" ");

          return (
            <div
              className={titleClassName}
              style={style}
              draggable
              onDragStart={(event) => handleColumnDragStart(event, title)}
              onDragOver={(event) => handleColumnDragOver(event, title)}
              onDrop={(event) => handleColumnDrop(event, title)}
              onDragEnd={(event) => {
                event.stopPropagation();
                resetColumnDrag();
              }}
            >
              <span className="kanban-column-heading">
                <span className="kanban-column-marker" />
                <span>{title}</span>
              </span>
              <div className="kanban-column-actions">
                <span className="kanban-column-count">{column.totalChildrenCount}</span>
                <span className="kanban-column-drag-hint" aria-hidden="true">
                  {"↔"}
                </span>
                <AppButton
                  type="button"
                  className="kanban-column-remove"
                  draggable={false}
                  onPointerDown={(event) => event.stopPropagation()}
                  onClick={(event) => {
                    event.stopPropagation();
                    onRemoveColumn(title);
                  }}
                  title="Удалить колонку"
                  aria-label="Удалить колонку"
                >
                  {"×"}
                </AppButton>
              </div>
            </div>
          );
        }}
        renderCardDragPreview={(card) => renderSubtaskCard(card, true, displayAssigneeLabel, currentUserId, "drag-preview")}
        onCardClick={(event, card) => {
          event.stopPropagation();
          const subtaskId = getSubtaskIdFromCardId(card.id);
          if (subtaskId == null) return;
          onOpenTaskCard("subtask", subtaskId);
        }}
        onCardMove={handleCardMove}
      />
    </div>
  );
}

