import seedPlannerState from "../../../mock-data/planner-state.json";
import type { PlannerParentTask, PlannerState, PlannerSubtask, PlannerTeam } from "../../../types/planner";

const LS_PLANNER = "ric_planner_state_v1";
const LS_PLANNER_SEED_VERSION = "ric_mock_planner_seed_version";
const CURRENT_PLANNER_SEED_VERSION = "v1_practice_2025";

export const DEFAULT_KANBAN_COLUMNS = ["Запланировано", "В работе", "На проверке", "Готово"];

const EMPTY_STATE: PlannerState = {
  enrollmentClosed: false,
  closedEventIds: [],
  hiddenEventIds: [],
  participants: [],
  teams: [],
  parentTasks: [],
  subtasks: [],
  columns: DEFAULT_KANBAN_COLUMNS,
};

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value));
}

function ensurePlannerSeeded() {
  const storedVersion = localStorage.getItem(LS_PLANNER_SEED_VERSION);
  if (storedVersion !== CURRENT_PLANNER_SEED_VERSION) {
    localStorage.setItem(LS_PLANNER, JSON.stringify(seedPlannerState));
    localStorage.setItem(LS_PLANNER_SEED_VERSION, CURRENT_PLANNER_SEED_VERSION);
    return;
  }

  if (!localStorage.getItem(LS_PLANNER)) {
    localStorage.setItem(LS_PLANNER, JSON.stringify(seedPlannerState));
  }
}

export function readPlannerState(seed = true): PlannerState {
  if (seed) ensurePlannerSeeded();
  const raw = localStorage.getItem(LS_PLANNER);
  if (!raw) return clone(EMPTY_STATE);

  try {
    const parsed = JSON.parse(raw) as Partial<PlannerState> & { in_sprint?: boolean | number | string };
    const subtasks = Array.isArray(parsed.subtasks)
      ? parsed.subtasks.map((item) => {
          const subtask = item as PlannerSubtask & { in_sprint?: boolean | number | string };
          const rawSprint = typeof subtask.inSprint === "boolean" ? subtask.inSprint : subtask.in_sprint;
          const inSprint =
            typeof rawSprint === "boolean"
              ? rawSprint
              : rawSprint === 1 || rawSprint === "1" || String(rawSprint).toLowerCase() === "true";
          return { ...subtask, inSprint };
        })
      : [];

    const closedEventIds = Array.isArray(parsed.closedEventIds)
      ? parsed.closedEventIds.map((id) => Number(id)).filter((id) => Number.isFinite(id) && id > 0)
      : [];
    const hiddenEventIds = Array.isArray(parsed.hiddenEventIds)
      ? parsed.hiddenEventIds.map((id) => Number(id)).filter((id) => Number.isFinite(id) && id > 0)
      : [];

    return {
      enrollmentClosed: closedEventIds.length > 0 || Boolean(parsed.enrollmentClosed),
      closedEventIds,
      hiddenEventIds,
      participants: Array.isArray(parsed.participants) ? parsed.participants : [],
      teams: Array.isArray(parsed.teams) ? parsed.teams : [],
      parentTasks: Array.isArray(parsed.parentTasks) ? parsed.parentTasks : [],
      subtasks,
      columns: Array.isArray(parsed.columns) && parsed.columns.length > 0 ? parsed.columns : [...DEFAULT_KANBAN_COLUMNS],
    };
  } catch {
    return clone(EMPTY_STATE);
  }
}

export function writePlannerState(state: PlannerState) {
  localStorage.setItem(LS_PLANNER, JSON.stringify(state));
}

export function nextPlannerId(items: Array<{ id: number }>) {
  return items.reduce((acc, item) => Math.max(acc, Number(item.id) || 0), 0) + 1;
}

export function removeTeamCascade(state: PlannerState, teamId: number): PlannerState {
  const parentIds = new Set(
    state.parentTasks.filter((item: PlannerParentTask) => Number(item.teamId) === Number(teamId)).map((item: PlannerParentTask) => Number(item.id))
  );
  return {
    ...state,
    teams: state.teams.filter((item: PlannerTeam) => Number(item.id) !== Number(teamId)),
    parentTasks: state.parentTasks.filter((item: PlannerParentTask) => Number(item.teamId) !== Number(teamId)),
    subtasks: state.subtasks.filter(
      (item: PlannerSubtask) => Number(item.teamId) !== Number(teamId) && !parentIds.has(Number(item.parentTaskId))
    ),
  };
}

