import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type FC,
} from "react";
import { Gantt, ViewMode, type Task } from "gantt-task-react";
import dayjs, { type Dayjs } from "dayjs";
import type {
  PlannerParentTask,
  PlannerSubtask,
  PlannerTeam,
} from "../../../../types/planner";
import { isDoneKanbanStatus } from "../../planner.utils";
import "gantt-task-react/dist/index.css";
import AppButton from "../../../../components/UI/Button";
import { Button, Card, Flex, Select, Space, Statistic, Typography } from "antd";
import { FilterOutlined, TeamOutlined } from "@ant-design/icons";

type PlannerGanttTask = Task & {
  plannerType: "parent" | "subtask";
  plannerId: number;
  assigneeLabel?: string;
  statusLabel?: string;
  childrenCount?: number;
  isDone?: boolean;
};

type GanttTabProps = {
  activeTeamName: string;
  parents: PlannerParentTask[];
  subtasks: PlannerSubtask[];
  displayAssigneeLabel: (id: number) => string;
  onOpenTaskCard: (type: "parent" | "subtask", id: number) => void;

  assigneeFilter: string;
  assigneeFilterOptions: Array<{
    value: string;
    label: string;
    disabled?: boolean;
  }>;
  onAssigneeFilterChange: (value: string) => void;
  visibleTeams: PlannerTeam[];
  teamFilter: string;
  onTeamFilterChange: (value: string) => void;
};

const { Text, Title } = Typography;

const viewModes = [
  { id: ViewMode.Day, label: "День" },
  { id: ViewMode.Week, label: "Неделя" },
  { id: ViewMode.Month, label: "Месяц" },
] as const;

const LIST_CELL_WIDTH = 300;
const MOBILE_LIST_CELL_WIDTH = 148;
const PRE_STEPS_COUNT = 1;

function normalizeGanttRange(
  start: Dayjs,
  end: Dayjs,
): { start: Dayjs; end: Dayjs } {
  let s = start.startOf("day");
  let e = end.startOf("day");
  if (!s.isValid() || !e.isValid()) {
    const t = dayjs();
    s = t.startOf("day");
    e = s;
  }
  if (e.isBefore(s)) e = s;
  return { start: s, end: e };
}

function cloneTasksForGanttView(tasks: PlannerGanttTask[]): PlannerGanttTask[] {
  return tasks.map((t) => {
    const { start, end } = normalizeGanttRange(dayjs(t.start), dayjs(t.end));
    return {
      ...t,
      start: start.toDate(),
      end: end.toDate(),
    };
  });
}

function getColumnWidth(mode: ViewMode): number {
  switch (mode) {
    case ViewMode.Day:
      return 52;
    case ViewMode.Month:
      return 110;
    default:
      return 84;
  }
}

function addToDate(
  date: Dayjs,
  quantity: number,
  scale: "day" | "month" | "year",
): Dayjs {
  return date.add(quantity, scale);
}

function startOfDate(date: Dayjs, scale: "day" | "month" | "year"): Dayjs {
  return date.startOf(scale);
}

function getMonday(date: Dayjs): Dayjs {
  const d = date;
  const day = d.day();
  const diff = d.date() - day + (day === 0 ? -6 : 1);
  return d.date(diff).startOf("day");
}

function getGanttDateCount(
  tasks: PlannerGanttTask[],
  mode: ViewMode,
  preStepsCount: number,
): number {
  if (tasks.length === 0) return 1;

  let start = dayjs(tasks[0].start);
  let end = dayjs(tasks[0].start);
  tasks.forEach((task) => {
    if (dayjs(task.start).isBefore(start)) start = dayjs(task.start);
    if (dayjs(task.end).isAfter(end)) end = dayjs(task.end);
  });

  switch (mode) {
    case ViewMode.Month:
      start = dayjs(
        startOfDate(addToDate(start, -1 * preStepsCount, "month"), "month"),
      );
      end = dayjs(startOfDate(addToDate(end, 1, "year"), "year"));
      break;
    case ViewMode.Week:
      start = dayjs(
        addToDate(
          getMonday(startOfDate(start, "day")),
          -7 * preStepsCount,
          "day",
        ),
      );
      end = dayjs(startOfDate(addToDate(end, 1.5, "month"), "day"));
      break;
    case ViewMode.Day:
      start = dayjs(
        addToDate(startOfDate(start, "day"), -1 * preStepsCount, "day"),
      );
      end = dayjs(addToDate(startOfDate(end, "day"), 19, "day"));
      break;
    default:
      return 1;
  }

  let current = start;
  let count = 1;
  while (current.isBefore(end) && count < 1000) {
    if (mode === ViewMode.Month) current = current.add(1, "month");
    else if (mode === ViewMode.Week) current = current.add(7, "day");
    else current = current.add(1, "day");
    count += 1;
  }

  return count;
}

const SUBTASK_EMERALD = {
  backgroundColor: "#10b981",
  backgroundSelectedColor: "#059669",
  progressColor: "#10b981",
  progressSelectedColor: "#059669",
} as const;

const PARENT_BLUE = {
  backgroundColor: "#4f7cff",
  backgroundSelectedColor: "#315de0",
  progressColor: "#4f7cff",
  progressSelectedColor: "#315de0",
} as const;

const DONE_GRAY = {
  backgroundColor: "#94a3b8",
  backgroundSelectedColor: "#64748b",
  progressColor: "#94a3b8",
  progressSelectedColor: "#64748b",
} as const;

const DONE_GANTT_FILLS = new Set([
  "#94a3b8",
  "#64748b",
  "rgb(148, 163, 184)",
  "rgb(100, 116, 139)",
]);

function isDoneGanttFill(value?: string) {
  return DONE_GANTT_FILLS.has(
    String(value || "")
      .trim()
      .toLowerCase(),
  );
}

const TooltipContent: FC<{
  task: Task;
  fontSize: string;
  fontFamily: string;
}> = ({ task, fontFamily, fontSize }) => {
  const plannerTask = task as PlannerGanttTask;
  return (
    <div className="planner-gantt-tooltip" style={{ fontFamily, fontSize }}>
      <div className="planner-gantt-tooltip__title">{plannerTask.name}</div>
      <div className="planner-gantt-tooltip__row">
        {dayjs(plannerTask.start).format("DD.MM.YYYY")} -{" "}
        {dayjs(plannerTask.end).format("DD.MM.YYYY")}
      </div>
      {plannerTask.assigneeLabel && (
        <div className="planner-gantt-tooltip__row">
          Ответственный: {plannerTask.assigneeLabel}
        </div>
      )}
      {plannerTask.statusLabel && (
        <div className="planner-gantt-tooltip__row">
          Статус: {plannerTask.statusLabel}
        </div>
      )}
      <div className="planner-gantt-tooltip__hint">
        Кликни по задаче, чтобы открыть карточку.
      </div>
    </div>
  );
};

export default function GanttTab({
  activeTeamName,
  parents,
  subtasks,
  displayAssigneeLabel,
  onOpenTaskCard,
  assigneeFilter,
  assigneeFilterOptions,
  onAssigneeFilterChange,
  visibleTeams,
  teamFilter,
  onTeamFilterChange,
}: GanttTabProps) {
  const surfaceRef = useRef<HTMLDivElement | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>(ViewMode.Week);
  const [collapsedParents, setCollapsedParents] = useState<string[]>([]);
  const [surfaceWidth, setSurfaceWidth] = useState(0);

  const tasks = useMemo<PlannerGanttTask[]>(() => {
    return parents.flatMap((parent, parentIndex) => {
      const childSubtasks = subtasks.filter(
        (subtask) => Number(subtask.parentTaskId) === Number(parent.id),
      );

      const { start: pStart, end: pEnd } = normalizeGanttRange(
        dayjs(parent.startDate),
        dayjs(parent.endDate),
      );

      const parentTask: PlannerGanttTask = {
        id: `parent-${parent.id}`,
        type: "project",
        name: parent.title,
        start: pStart.toDate(),
        end: pEnd.toDate(),
        progress: 0,
        hideChildren: collapsedParents.includes(`parent-${parent.id}`),
        isDisabled: true,
        displayOrder: (parentIndex + 1) * 100,
        plannerType: "parent",
        plannerId: parent.id,
        childrenCount: childSubtasks.length,
        styles: { ...PARENT_BLUE },
      };

      const subtaskTasks = childSubtasks.map<PlannerGanttTask>(
        (subtask, subtaskIndex) => {
          const { start: sStart, end: sEnd } = normalizeGanttRange(
            dayjs(subtask.startDate),
            dayjs(subtask.endDate),
          );
          const isDone = isDoneKanbanStatus(subtask.status);
          return {
            id: `subtask-${subtask.id}`,
            type: "task",
            name: subtask.title,
            start: sStart.toDate(),
            end: sEnd.toDate(),
            progress: 0,
            isDisabled: true,
            project: parentTask.id,
            displayOrder: (parentIndex + 1) * 100 + subtaskIndex + 1,
            plannerType: "subtask",
            plannerId: subtask.id,
            assigneeLabel: subtask.assigneeId
              ? displayAssigneeLabel(subtask.assigneeId)
              : "Не назначен",
            statusLabel: subtask.status,
            isDone,
            styles: isDone ? { ...DONE_GRAY } : { ...SUBTASK_EMERALD },
          };
        },
      );

      return [parentTask, ...subtaskTasks];
    });
  }, [collapsedParents, displayAssigneeLabel, parents, subtasks]);

  const ganttTasks = useMemo(() => cloneTasksForGanttView(tasks), [tasks]);
  const listCellWidth =
    surfaceWidth > 0 && surfaceWidth <= 640
      ? MOBILE_LIST_CELL_WIDTH
      : LIST_CELL_WIDTH;

  const columnWidth = useMemo(() => {
    const baseWidth = getColumnWidth(viewMode);
    if (!surfaceWidth || ganttTasks.length === 0) return baseWidth;

    const timelineWidth = Math.max(surfaceWidth - listCellWidth, 0);
    if (!timelineWidth) return baseWidth;

    const dateCount = getGanttDateCount(ganttTasks, viewMode, PRE_STEPS_COUNT);
    return Math.max(baseWidth, Math.floor(timelineWidth / dateCount));
  }, [ganttTasks, listCellWidth, surfaceWidth, viewMode]);

  const replaceWeekLabels = useCallback(() => {
    if (viewMode !== ViewMode.Week) return;
    surfaceRef.current?.querySelectorAll("text").forEach((node) => {
      const value = node.textContent?.trim() || "";
      const match = value.match(/^W(\d+)$/);
      if (match) node.textContent = `Нед. ${match[1]}`;
    });
  }, [viewMode]);

  const renderDoneLines = useCallback(() => {
    const svg = surfaceRef.current?.querySelector<SVGSVGElement>("svg");
    if (!svg) return;

    svg
      .querySelectorAll(".planner-gantt-done-line")
      .forEach((node) => node.remove());

    const usedRects = new Set<string>();
    svg.querySelectorAll<SVGRectElement>("rect").forEach((rect) => {
      const fill =
        rect.getAttribute("fill") ||
        rect.style.fill ||
        window.getComputedStyle(rect).fill;
      if (!isDoneGanttFill(fill)) return;

      const x = Number(rect.getAttribute("x"));
      const y = Number(rect.getAttribute("y"));
      const width = Number(rect.getAttribute("width"));
      const height = Number(rect.getAttribute("height"));
      if (
        ![x, y, width, height].every(Number.isFinite) ||
        width <= 8 ||
        height <= 4
      )
        return;

      const key = `${x}:${y}:${width}:${height}`;
      if (usedRects.has(key)) return;
      usedRects.add(key);

      const line = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "line",
      );
      line.setAttribute("class", "planner-gantt-done-line");
      line.setAttribute("x1", String(x - 8));
      line.setAttribute("x2", String(x + width + 8));
      line.setAttribute("y1", String(y + height / 2));
      line.setAttribute("y2", String(y + height / 2));
      svg.appendChild(line);
    });
  }, []);

  useLayoutEffect(() => {
    const element = surfaceRef.current;
    if (!element) return;

    let frameId = 0;
    const updateWidth = () => {
      const nextWidth = Math.floor(
        element.getBoundingClientRect().width || element.clientWidth || 0,
      );
      if (nextWidth > 0) {
        setSurfaceWidth((prev) => (prev === nextWidth ? prev : nextWidth));
      }
    };
    const scheduleUpdate = () => {
      window.cancelAnimationFrame(frameId);
      frameId = window.requestAnimationFrame(updateWidth);
    };

    updateWidth();
    scheduleUpdate();

    const resizeObserver = new ResizeObserver(scheduleUpdate);
    resizeObserver.observe(element);
    window.addEventListener("resize", scheduleUpdate);

    return () => {
      window.cancelAnimationFrame(frameId);
      resizeObserver.disconnect();
      window.removeEventListener("resize", scheduleUpdate);
    };
  }, [tasks.length]);

  useEffect(() => {
    const element = surfaceRef.current;
    if (!element || viewMode !== ViewMode.Week) return;

    replaceWeekLabels();
    const frame = window.requestAnimationFrame(replaceWeekLabels);
    const observer = new MutationObserver(replaceWeekLabels);
    observer.observe(element, {
      childList: true,
      subtree: true,
      characterData: true,
    });

    return () => {
      window.cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [columnWidth, ganttTasks, replaceWeekLabels, viewMode]);

  useEffect(() => {
    const element = surfaceRef.current;
    if (!element) return;

    renderDoneLines();
    const frame = window.requestAnimationFrame(renderDoneLines);
    const timer = window.setTimeout(renderDoneLines, 80);

    return () => {
      window.cancelAnimationFrame(frame);
      window.clearTimeout(timer);
    };
  }, [columnWidth, ganttTasks, renderDoneLines, viewMode]);

  const handleGanttExpanderClick = useCallback((task: Task) => {
    const taskId = String(task.id);
    setCollapsedParents((prev) =>
      task.hideChildren
        ? [...prev, taskId]
        : prev.filter((id) => id !== taskId),
    );
  }, []);

  const TaskListHeader: FC<{
    headerHeight: number;
    rowWidth: string;
    fontFamily: string;
    fontSize: string;
  }> = ({ headerHeight, rowWidth, fontFamily, fontSize }) => (
    <div
      className="planner-gantt-list-header"
      style={{
        minWidth: rowWidth,
        height: headerHeight - 2,
        fontFamily,
        fontSize,
      }}
    >
      <div>Задача</div>
    </div>
  );

  const TaskListTable: FC<{
    rowHeight: number;
    rowWidth: string;
    fontFamily: string;
    fontSize: string;
    locale: string;
    tasks: Task[];
    selectedTaskId: string;
    setSelectedTask: (taskId: string) => void;
    onExpanderClick: (task: Task) => void;
  }> = ({
    rowHeight,
    rowWidth,
    fontFamily,
    fontSize,
    tasks,
    selectedTaskId,
    setSelectedTask,
    onExpanderClick,
  }) => (
    <div
      className="planner-gantt-list"
      style={{
        minWidth: rowWidth,
        fontFamily,
        fontSize,
      }}
    >
      {tasks.map((task) => {
        const plannerTask = task as PlannerGanttTask;
        const isParent = plannerTask.plannerType === "parent";
        const isSelected = selectedTaskId === plannerTask.id;
        const canExpand = task.type === "project";
        const expander = canExpand ? (task.hideChildren ? "▸" : "▾") : "";
        const metaText = isParent
          ? plannerTask.childrenCount
            ? `${plannerTask.childrenCount} подзадач`
            : "Без подзадач"
          : plannerTask.statusLabel || "Подзадача";
        return (
          <Button
            key={plannerTask.id}
            className={`planner-gantt-list-row ${isParent ? "is-parent" : "is-child"} ${isSelected ? "is-selected" : ""}`}
            style={{ maxWidth: rowWidth, height: rowHeight }}
            onClick={(event) => {
              event.stopPropagation();
              setSelectedTask(plannerTask.id);

              if (canExpand) onExpanderClick(task);
            }}
          >
            <div className="planner-gantt-list-row__title">
              <div className="planner-gantt-list-row__main">
                <span
                  className={`planner-gantt-expander ${canExpand ? "is-visible" : "is-hidden"}`}
                >
                  {expander || "•"}
                </span>
                <span className="planner-gantt-list-row__name">
                  {plannerTask.name}
                </span>
              </div>
              <span className="planner-gantt-list-row__meta">{metaText}</span>
            </div>
          </Button>
        );
      })}
    </div>
  );

  return (
    <div className="planner-stack backlog-tab">
      <Card className="planner-card backlog-hero">
        <Flex justify="space-between" gap={16} wrap align="center">
          <Space vertical size={4}>
            <Text className="teams-eyebrow">Диаграмма Ганта команды</Text>
            <Title level={3} className="backlog-title">
              {activeTeamName || "Выберите команду"}
            </Title>
          </Space>
          <Space size={[12, 12]} wrap>
            <Statistic title="Большие задачи" value={parents.length} />
            <Statistic title="Подзадачи" value={subtasks.length} />
          </Space>
        </Flex>

        <Flex style={{ marginTop: 16 }} gap={12}>
          <Flex style={{ width: "50%" }} vertical>
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
          <Flex style={{ width: "50%" }} vertical>
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

      <div className="planner-card planner-gantt-card">
        <div className="planner-gantt-head">
          <div className="planner-gantt-head__copy">
            <h3 className="h3">Диаграмма Ганта</h3>
          </div>

          <div className="planner-gantt-head__controls">
            <div
              className="planner-gantt-switcher"
              role="tablist"
              aria-label="Масштаб диаграммы Ганта"
            >
              {viewModes.map((mode) => (
                <AppButton
                  key={mode.id}
                  type="button"
                  className={viewMode === mode.id ? "is-active" : ""}
                  onClick={() => setViewMode(mode.id)}
                >
                  {mode.label}
                </AppButton>
              ))}
            </div>
          </div>
        </div>

        {tasks.length === 0 ? (
          <div className="planner-empty-inline">Нет задач для отображения.</div>
        ) : (
          <div className="planner-gantt-surface" ref={surfaceRef}>
            <Gantt
              key={`${viewMode}-${columnWidth}`}
              tasks={ganttTasks}
              viewMode={viewMode}
              locale="ru"
              listCellWidth={`${listCellWidth}px`}
              columnWidth={columnWidth}
              rowHeight={44}
              barFill={72}
              preStepsCount={PRE_STEPS_COUNT}
              fontFamily="Inter, sans-serif"
              todayColor="rgba(79, 124, 255, 0.10)"
              TooltipContent={TooltipContent}
              TaskListHeader={TaskListHeader}
              TaskListTable={TaskListTable}
              onExpanderClick={handleGanttExpanderClick}
              onClick={(task) => {
                const plannerTask = task as PlannerGanttTask;
                onOpenTaskCard(plannerTask.plannerType, plannerTask.plannerId);
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
