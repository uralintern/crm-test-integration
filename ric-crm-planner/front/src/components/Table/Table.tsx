import React, { useContext, useEffect, useRef } from "react";
import { FormOutlined, InfoCircleOutlined } from "@ant-design/icons";
import { Tooltip } from "antd";
import { AuthContext } from "../../context/AuthContext";
import "./table.scss";
import AppButton from "../UI/Button";

type Column = { key: string; title: string; width?: string };
type RowWithId = { id?: number | string };

interface Props<T> {
  columns: Column[];
  data: T[];
  badgeKeys?: string[];
  animatedIds?: Array<number | string>;
  onInfoClick?: (row: T) => void;
  onRowClick?: (row: T) => void;
  onEdit?: (row: T) => void;
  selectedId?: number;
  gridColumns?: string;
  renderCell?: (row: T, colKey: string) => React.ReactNode | undefined;
  editIcon?: React.ReactNode;
  editTooltip?: string;
}

function buildGridTemplate(columns: Column[], hasActionColumn: boolean, gridColumns?: string) {
  if (gridColumns && gridColumns.trim()) {
    return hasActionColumn ? `${gridColumns.trim()} 60px` : gridColumns.trim();
  }
  const cols = columns.map((column) => (column.width ? `minmax(${column.width}, ${column.width})` : "minmax(150px, 1fr)"));
  if (hasActionColumn) cols.push("60px");
  return cols.join(" ");
}

function getRowId(row: unknown): number | string | undefined {
  if (!row || typeof row !== "object") return undefined;
  const candidate = (row as RowWithId).id;
  if (typeof candidate === "number" || typeof candidate === "string") return candidate;
  return undefined;
}

function toDisplay(value: unknown): string {
  if (value == null) return "-";
  if (Array.isArray(value)) return value.map((item) => String(item)).join(", ");
  return String(value);
}

function canUseOrganizerActions(role?: string) {
  const normalized = String(role || "").toLowerCase();
  return normalized === "organizer" || normalized.includes("admin") || normalized.includes("curator");
}

export default function Table<T>({
  columns,
  data,
  badgeKeys = [],
  animatedIds = [],
  onRowClick,
  onEdit,
  onInfoClick,
  selectedId,
  gridColumns = "",
  renderCell,
  editIcon,
  editTooltip,
}: Props<T>) {
  const { user } = useContext(AuthContext);
  const isOrganizer = canUseOrganizerActions(user?.role);
  const hasActionColumn = Boolean((isOrganizer && onEdit) || onInfoClick);
  const columnKeys = columns.map((column) => column.key);
  const isEventMobileLayout = ["title", "startDate", "endDate", "organizer", "status"].every((key) => columnKeys.includes(key));
  const isDirectionMobileLayout = ["title", "organizer"].every((key) => columnKeys.includes(key)) && !isEventMobileLayout;
	  const isProjectMobileLayout = ["title", "curator"].every((key) => columnKeys.includes(key)) && !isEventMobileLayout;
	  const isRequestMobileLayout = ["studentName", "event", "specialization", "status"].every((key) => columnKeys.includes(key));
	  const hasApplyColumn = columnKeys.includes("apply");

  const template = buildGridTemplate(columns, hasActionColumn, gridColumns);
  const gridStyle = { "--table-grid": template } as React.CSSProperties;
  const rowRefs = useRef(new Map<string, HTMLDivElement>());

  useEffect(() => {
    if (!animatedIds.length) return;

    const uniqueIds = Array.from(new Set(animatedIds.map((id) => String(id))));

    uniqueIds.forEach((id) => {
      const node = rowRefs.current.get(id);
      if (!node || typeof node.animate !== "function") return;

      node.animate(
        [
          { transform: "translateX(0)" },
          { transform: "translateX(7px)" },
          { transform: "translateX(-6px)" },
          { transform: "translateX(5px)" },
          { transform: "translateX(-3px)" },
          { transform: "translateX(0)" },
        ],
        {
          duration: 550,
          easing: "ease-in-out",
        }
      );
    });
  }, [animatedIds]);

  return (
    <div className="custom-table-container">
      <div className="custom-table">
        <div className="table-grid table-grid-head" style={gridStyle}>
          {columns.map((column) => (
            <div key={column.key} className="head-cell text-small">
              {column.title}
            </div>
          ))}
          {hasActionColumn && <div className="head-cell head-cell-actions" />}
        </div>

        {data.length === 0 ? (
          <div className="table-placeholder">Нет данных</div>
        ) : (
          data.map((row, idx) => {
            const rowRecord = row as Record<string, unknown>;
            const statusRaw = rowRecord.status;
            const statusText = toDisplay(statusRaw);
            const normalizedStatus = String(statusRaw ?? "").trim().toLowerCase();
            const isActiveStatus = normalizedStatus === "активно";
            const isClosedEnrollmentStatus = normalizedStatus === "набор завершен";
            const statusCustom = renderCell?.(row, "status");
	            const eventApplyCustom = hasApplyColumn ? renderCell?.(row, "apply") : undefined;

            const editActionButton =
              isOrganizer && onEdit ? (
                <AppButton
                  className="edit-btn-icon"
                  onClick={(event) => {
                    event.stopPropagation();
                    onEdit(row);
                  }}
                >
                  {editIcon ?? <FormOutlined />}
                </AppButton>
              ) : null;

            const actionButton = editActionButton ? (
              editTooltip ? (
                <Tooltip title={editTooltip}>{editActionButton}</Tooltip>
              ) : (
                editActionButton
              )
            ) : onInfoClick ? (
                <AppButton
                  className="info-btn"
                  onClick={(event) => {
                    event.stopPropagation();
                    onInfoClick(row);
                  }}
                  aria-label="Информация"
                >
                  <InfoCircleOutlined />
                </AppButton>
              ) : null;

            const rowId = getRowId(row);

            return (
              <div
                key={rowId ?? idx}
                className={`row-box table-grid${getRowId(row) === selectedId ? " selected" : ""}${
                  isEventMobileLayout ? " row-box--event-mobile" : ""
                }${isDirectionMobileLayout ? " row-box--direction-mobile" : ""}${
                  isProjectMobileLayout ? " row-box--project-mobile" : ""
                }${isRequestMobileLayout ? " row-box--request-mobile" : ""}`}
                style={gridStyle}
                ref={(node) => {
                  const refKey = String(rowId ?? idx);
                  if (node) {
                    rowRefs.current.set(refKey, node);
                  } else {
                    rowRefs.current.delete(refKey);
                  }
                }}
                onClick={() => onRowClick?.(row)}
              >
                {columns.map((column) => {
                  if (renderCell) {
                    const custom = renderCell(row, column.key);
                    if (custom !== undefined) {
                      return (
                        <div key={column.key} className="cell" data-label={column.title}>
                          {custom}
                        </div>
                      );
                    }
                  }

                  if (column.key === "status") {
                    return (
                      <div key={column.key} className="cell status-cell" data-label={column.title}>
                        <span className={`cell-badge ${isClosedEnrollmentStatus ? "status-closed" : `status-${isActiveStatus ? "active" : "inactive"}`}`}>
                          {statusText}
                        </span>
                      </div>
                    );
                  }

                  const raw = rowRecord[column.key];
                  const isBadge = badgeKeys.includes(column.key);
                  const display = toDisplay(raw);

                  return (
                    <div key={column.key} className="cell" data-label={column.title}>
                      {isBadge ? <span className="cell-badge">{display}</span> : <div className="title-text">{display}</div>}
                    </div>
                  );
                })}

                {hasActionColumn && (
                  <div className="cell cell-actions cell-actions-desktop" data-label="Действие">
                    {actionButton}
                  </div>
                )}

	                {isEventMobileLayout && (
	                  <div className={`event-card-mobile${eventApplyCustom === undefined && actionButton ? " event-card-mobile--has-icon-action" : ""}`}>
                    <div className="event-card-mobile__main">
                      <div className="event-card-mobile__title">{toDisplay(rowRecord.title)}</div>

                      <div className="event-card-mobile__row event-card-mobile__row--dates">
                        <div className="event-card-mobile__pair">
                          <span className="event-card-mobile__label">Дата начала</span>
                          <span className="cell-badge">{toDisplay(rowRecord.startDate)}</span>
                        </div>
                        <div className="event-card-mobile__pair">
                          <span className="event-card-mobile__label">Дата окончания</span>
                          <span className="cell-badge">{toDisplay(rowRecord.endDate)}</span>
                        </div>
                      </div>

                      <div className="event-card-mobile__row event-card-mobile__row--meta">
                        <div className="event-card-mobile__pair">
                          <span className="event-card-mobile__label">Организатор</span>
                          <span className="event-card-mobile__value">{toDisplay(rowRecord.organizer)}</span>
                        </div>
                        <div className="event-card-mobile__pair">
                          <span className="event-card-mobile__label">Статус</span>
                          <span className={`cell-badge ${isClosedEnrollmentStatus ? "status-closed" : `status-${isActiveStatus ? "active" : "inactive"}`}`}>{statusText}</span>
                        </div>
                      </div>
                    </div>

	                    {(eventApplyCustom != null || actionButton) && (
	                      <div className={`event-card-mobile__action${eventApplyCustom != null ? " event-card-mobile__action--apply" : " event-card-mobile__action--icon"}`}>
	                        <div className="event-card-mobile__divider" />
	                        {eventApplyCustom != null ? eventApplyCustom : actionButton}
	                      </div>
	                    )}
	                  </div>
	                )}

	                {isDirectionMobileLayout && (
	                  <div className={`event-card-mobile${actionButton ? " event-card-mobile--has-icon-action" : ""}`}>
                    <div className="event-card-mobile__main">
                      <div className="event-card-mobile__title">{toDisplay(rowRecord.title)}</div>
                      <div className="event-card-mobile__row event-card-mobile__row--single">
                        <div className="event-card-mobile__pair">
                          <span className="event-card-mobile__label">Организатор</span>
                          <span className="event-card-mobile__value">{toDisplay(rowRecord.organizer)}</span>
                        </div>
                      </div>
                    </div>

	                    {actionButton && (
	                      <div className="event-card-mobile__action event-card-mobile__action--icon">
	                        <div className="event-card-mobile__divider" />
	                        {actionButton}
	                      </div>
                    )}
                  </div>
                )}

	                {isProjectMobileLayout && (
	                  <div className={`event-card-mobile${actionButton ? " event-card-mobile--has-icon-action" : ""}`}>
                    <div className="event-card-mobile__main">
                      <div className="event-card-mobile__title">{toDisplay(rowRecord.title)}</div>
                      <div className="event-card-mobile__row event-card-mobile__row--single">
                        <div className="event-card-mobile__pair">
                          <span className="event-card-mobile__label">Куратор</span>
                          <span className="event-card-mobile__value">{toDisplay(rowRecord.curator)}</span>
                        </div>
                      </div>
                    </div>

	                    {actionButton && (
	                      <div className="event-card-mobile__action event-card-mobile__action--icon">
	                        <div className="event-card-mobile__divider" />
	                        {actionButton}
                      </div>
                    )}
                  </div>
                )}

                {isRequestMobileLayout && (
                  <div className={`request-card-mobile${actionButton ? " request-card-mobile--has-action" : ""}`}>
                    {actionButton && <div className="request-card-mobile__action">{actionButton}</div>}
                    <div className="request-card-mobile__title">{toDisplay(rowRecord.studentName)}</div>

                    <div className="request-card-mobile__row request-card-mobile__row--single">
                      <div className="request-card-mobile__pair">
                        <span className="request-card-mobile__label">Мероприятие</span>
                        <span className="request-card-mobile__value">{toDisplay(rowRecord.event)}</span>
                      </div>
                    </div>

                    <div className="request-card-mobile__row request-card-mobile__row--single">
                      <div className="request-card-mobile__pair">
                        <span className="request-card-mobile__label">Специализация</span>
                        <span className="request-card-mobile__value">{toDisplay(rowRecord.specialization)}</span>
                      </div>
                    </div>

                    <div className="request-card-mobile__row request-card-mobile__row--single">
                      <div className="request-card-mobile__pair">
                        <span className="request-card-mobile__label">Статус</span>
                        <div className="request-card-mobile__status-body">
                          {statusCustom !== undefined ? statusCustom : <span className="request-card-mobile__value">{statusText}</span>}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
