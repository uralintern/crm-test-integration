import client from "../../../api/client";
import { REQUEST_STATUS, isNegativeRequestStatus } from "../../../constants/requestProgress";
import { readPlannerState, writePlannerState } from "../storage/planner";
import type { PlannerParticipant, PlannerState } from "../../../types/planner";
import type { Request } from "../../../types/request";
import type { User } from "../../../types/user";

const USE_MOCK = client.USE_MOCK;

export type PlannerTeamDesk = {
  teamId: number;
  teamName: string;
  curatorId?: number;
  memberIds: number[];
  parentTasks: PlannerState["parentTasks"];
  subtasks: PlannerState["subtasks"];
  columns: string[];
  updatedAt?: string;
};

export type PlannerTeamDeskSocketMessage = {
  type: "desk.updated" | "desk.snapshot";
  teamId: number;
  action?: string;
  desk: PlannerTeamDesk;
};

type BackendPlanner = {
  enrollmentClosed?: boolean;
  enrollment_closed?: boolean;
  closedEventIds?: Array<number | string>;
  closed_event_ids?: Array<number | string>;
  hiddenEventIds?: Array<number | string>;
  hidden_event_ids?: Array<number | string>;
  participants?: Array<{ id?: number | string; fullName?: string; full_name?: string }>;
  teams?: PlannerState["teams"];
  parentTasks?: PlannerState["parentTasks"];
  parent_tasks?: PlannerState["parentTasks"];
  subtasks?: PlannerState["subtasks"];
  columns?: string[];
};

type BackendPlannerTeamDesk = {
  teamId?: number | string;
  team_id?: number | string;
  teamName?: string;
  team_name?: string;
  curatorId?: number | string;
  curator_id?: number | string;
  memberIds?: Array<number | string>;
  member_ids?: Array<number | string>;
  parentTasks?: unknown[];
  parent_tasks?: unknown[];
  subtasks?: unknown[];
  columns?: string[];
  updatedAt?: string;
  updated_at?: string;
};

type BackendPlannerTeam = Partial<PlannerState["teams"][number]> & {
  title?: string;
  name?: string;
  curator_id?: number | string;
  member_ids?: Array<number | string>;
  memberRoles?: Record<string, string>;
  member_roles?: Record<string, string>;
  event_id?: number | string;
  direction_id?: number | string;
  project_id?: number | string;
  source_request_ids?: Array<number | string>;
  created_by?: number | string;
  updated_at?: string;
};

type BackendPlannerParentTask = Partial<PlannerState["parentTasks"][number]> & {
  team_id?: number | string;
  assigneeId?: number | string;
  assignee_id?: number | string;
  created_by?: number | string;
  updated_at?: string;
};

type BackendPlannerSubtask = Partial<PlannerState["subtasks"][number]> & {
  team_id?: number | string;
  parent_task_id?: number | string;
  assigneeId?: number | string;
  assignee_id?: number | string;
  inSprint?: boolean;
  in_sprint?: boolean | number | string;
  created_by?: number | string;
  updated_at?: string;
};

function toNumber(value: unknown): number | undefined {
  if (typeof value === "number" && !Number.isNaN(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    if (!Number.isNaN(parsed)) return parsed;
  }
  return undefined;
}

export function hasStartedWork(status?: string) {
  return String(status || "").trim().toLowerCase() === REQUEST_STATUS.STARTED.toLowerCase();
}

export function hasPlannerAccessStatus(status?: string) {
  const normalizedStatus = String(status || "").trim().toLowerCase();
  if (isNegativeRequestStatus(status)) return false;
  return (
    normalizedStatus === REQUEST_STATUS.ENROLLMENT_CLOSED.toLowerCase() ||
    normalizedStatus === REQUEST_STATUS.STARTED.toLowerCase() ||
    normalizedStatus === REQUEST_STATUS.JOINED_CHAT.toLowerCase()
  );
}

function mapBackendTeams(teams: unknown, fallback: PlannerState): PlannerState["teams"] {
  if (!Array.isArray(teams)) return fallback.teams;

  return teams.map((item) => {
    const team = item as BackendPlannerTeam;
    return {
      ...team,
      id: toNumber(team.id) ?? 0,
      name: String(team.name ?? team.title ?? ""),
      curatorId: toNumber(team.curatorId ?? team.curator_id),
      memberIds: Array.isArray(team.memberIds ?? team.member_ids)
        ? (team.memberIds ?? team.member_ids ?? []).map((id) => Number(id)).filter((id) => Number.isFinite(id))
        : [],
      memberRoles:
        team.memberRoles && typeof team.memberRoles === "object"
          ? team.memberRoles
          : team.member_roles && typeof team.member_roles === "object"
            ? team.member_roles
            : {},
      confirmed: Boolean(team.confirmed),
      eventId: toNumber(team.eventId ?? team.event_id),
      directionId: toNumber(team.directionId ?? team.direction_id),
      projectId: toNumber(team.projectId ?? team.project_id),
      sourceRequestIds: Array.isArray(team.sourceRequestIds ?? team.source_request_ids)
        ? (team.sourceRequestIds ?? team.source_request_ids ?? []).map((id) => Number(id)).filter((id) => Number.isFinite(id))
        : [],
      createdBy: toNumber(team.createdBy ?? team.created_by),
      updatedAt: String(team.updatedAt ?? team.updated_at ?? ""),
    };
  });
}

function mapBackendParentTasks(parentTasks: unknown, fallback: PlannerState): PlannerState["parentTasks"] {
  if (!Array.isArray(parentTasks)) return fallback.parentTasks;

  return parentTasks.map((item) => {
    const task = item as BackendPlannerParentTask;
    return {
      ...task,
      id: toNumber(task.id) ?? 0,
      teamId: toNumber(task.teamId ?? task.team_id) ?? 0,
      title: String(task.title ?? ""),
      assigneeId: toNumber(task.assigneeId ?? task.assignee_id),
      startDate: String(task.startDate ?? ""),
      endDate: String(task.endDate ?? ""),
      createdBy: toNumber(task.createdBy ?? task.created_by),
      updatedAt: String(task.updatedAt ?? task.updated_at ?? ""),
    };
  });
}


function mapBackendTeamDesk(raw: unknown): PlannerTeamDesk {
  const desk = (raw || {}) as BackendPlannerTeamDesk;
  const teamId = toNumber(desk.teamId ?? desk.team_id) ?? 0;
  const fallback: PlannerState = {
    enrollmentClosed: false,
    closedEventIds: [],
    hiddenEventIds: [],
    participants: [],
    teams: [],
    parentTasks: [],
    subtasks: [],
    columns: [],
  };

  const parentTasks = mapBackendParentTasks(desk.parentTasks ?? desk.parent_tasks, fallback).map((task) => ({
    ...task,
    teamId: Number(task.teamId) || teamId,
  }));

  const subtasks = Array.isArray(desk.subtasks)
    ? desk.subtasks.map((item) => {
        const subtask = item as BackendPlannerSubtask;
        return {
          ...subtask,
          id: toNumber(subtask.id) ?? 0,
          teamId: toNumber(subtask.teamId ?? subtask.team_id) ?? teamId,
          parentTaskId: toNumber(subtask.parentTaskId ?? subtask.parent_task_id) ?? 0,
          title: String(subtask.title ?? ""),
          role: String(subtask.role ?? ""),
          assigneeId: toNumber(subtask.assigneeId ?? subtask.assignee_id),
          startDate: String(subtask.startDate ?? ""),
          endDate: String(subtask.endDate ?? ""),
          inSprint: Boolean(subtask.inSprint ?? subtask.in_sprint),
          status: String(subtask.status ?? ""),
          createdBy: toNumber(subtask.createdBy ?? subtask.created_by),
          updatedAt: String(subtask.updatedAt ?? subtask.updated_at ?? ""),
        };
      })
    : [];

  return {
    teamId,
    teamName: String(desk.teamName ?? desk.team_name ?? ""),
    curatorId: toNumber(desk.curatorId ?? desk.curator_id),
    memberIds: Array.isArray(desk.memberIds ?? desk.member_ids)
      ? (desk.memberIds ?? desk.member_ids ?? []).map((id) => Number(id)).filter((id) => Number.isFinite(id))
      : [],
    parentTasks,
    subtasks,
    columns: Array.isArray(desk.columns) ? desk.columns : [],
    updatedAt: String(desk.updatedAt ?? desk.updated_at ?? ""),
  };
}

export function parsePlannerTeamDeskSocketMessage(raw: string): PlannerTeamDeskSocketMessage | null {
  try {
    const data = JSON.parse(raw) as { type?: string; teamId?: number | string; team_id?: number | string; action?: string; desk?: unknown };
    if (data.type !== "desk.updated" && data.type !== "desk.snapshot") return null;
    if (!data.desk) return null;

    const desk = mapBackendTeamDesk(data.desk);
    const teamId = toNumber(data.teamId ?? data.team_id) ?? desk.teamId;
    if (!teamId) return null;

    return {
      type: data.type,
      teamId,
      action: data.action,
      desk: { ...desk, teamId },
    };
  } catch {
    return null;
  }
}

export function mergeTeamDeskIntoPlannerState(state: PlannerState, desk: PlannerTeamDesk): PlannerState {
  const teamId = Number(desk.teamId);
  if (!Number.isFinite(teamId) || teamId <= 0) return state;

  const teams = state.teams.some((team) => Number(team.id) === teamId)
    ? state.teams.map((team) =>
        Number(team.id) === teamId
          ? {
              ...team,
              name: desk.teamName || team.name,
              curatorId: desk.curatorId,
              memberIds: desk.memberIds,
              updatedAt: desk.updatedAt || team.updatedAt,
            }
          : team
      )
    : [
        ...state.teams,
        {
          id: teamId,
          name: desk.teamName || `Команда #${teamId}`,
          curatorId: desk.curatorId,
          memberIds: desk.memberIds,
          confirmed: false,
          updatedAt: desk.updatedAt,
        },
      ];

  return {
    ...state,
    teams,
    parentTasks: [...state.parentTasks.filter((task) => Number(task.teamId) !== teamId), ...desk.parentTasks],
    subtasks: [...state.subtasks.filter((subtask) => Number(subtask.teamId) !== teamId), ...desk.subtasks],
    columns: desk.columns.length ? desk.columns : state.columns,
  };
}

export function getPlannerTeamDeskSocketUrl(teamId: number): string {
  const baseUrl = client.API_BASE || window.location.origin;
  const url = new URL(baseUrl, window.location.origin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = `/ws/planner/teams/${teamId}/`;
  url.search = "";
  url.hash = "";
  return url.toString();
}
function mapBackendPlanner(raw: unknown): PlannerState {
  const fallback = readPlannerState(false);
  if (!raw || typeof raw !== "object") return fallback;

  const planner = raw as BackendPlanner;
  const fallbackSubtasksById = new Map<number, PlannerState["subtasks"][number]>(
    fallback.subtasks.map((subtask) => [Number(subtask.id), subtask])
  );
  const mappedSubtasks = Array.isArray(planner.subtasks)
    ? planner.subtasks.map((item) => {
        const subtask = item as BackendPlannerSubtask;
        const id = Number((subtask as { id?: number | string }).id ?? 0);
        const fallbackSubtask = fallbackSubtasksById.get(id);
        const rawSprint = typeof subtask.inSprint === "boolean" ? subtask.inSprint : subtask.in_sprint;
        const inSprint =
          typeof rawSprint === "boolean"
            ? rawSprint
            : typeof rawSprint === "undefined"
              ? fallbackSubtask?.inSprint ?? false
              : rawSprint === 1 || rawSprint === "1" || String(rawSprint).toLowerCase() === "true";
        return {
          ...fallbackSubtask,
          ...subtask,
          id: id || (fallbackSubtask?.id ?? 0),
          teamId: toNumber(subtask.teamId) ?? fallbackSubtask?.teamId ?? 0,
          parentTaskId: toNumber(subtask.parentTaskId) ?? fallbackSubtask?.parentTaskId ?? 0,
          title: String(subtask.title ?? fallbackSubtask?.title ?? ""),
          role: String(subtask.role ?? fallbackSubtask?.role ?? ""),
          assigneeId: toNumber(subtask.assigneeId ?? subtask.assignee_id),
          startDate: String(subtask.startDate ?? fallbackSubtask?.startDate ?? ""),
          endDate: String(subtask.endDate ?? fallbackSubtask?.endDate ?? ""),
          inSprint,
          status: String(subtask.status ?? fallbackSubtask?.status ?? ""),
          createdBy: toNumber(subtask.createdBy ?? subtask.created_by) ?? fallbackSubtask?.createdBy,
          updatedAt: String(subtask.updatedAt ?? subtask.updated_at ?? fallbackSubtask?.updatedAt ?? ""),
        };
      })
    : fallback.subtasks;

  const closedEventIds = Array.isArray(planner.closedEventIds ?? planner.closed_event_ids)
    ? (planner.closedEventIds ?? planner.closed_event_ids ?? [])
        .map((id) => toNumber(id))
        .filter((id): id is number => typeof id === "number" && Number.isFinite(id) && id > 0)
    : fallback.closedEventIds;
  const hiddenEventIds = Array.isArray(planner.hiddenEventIds ?? planner.hidden_event_ids)
    ? (planner.hiddenEventIds ?? planner.hidden_event_ids ?? [])
        .map((id) => toNumber(id))
        .filter((id): id is number => typeof id === "number" && Number.isFinite(id) && id > 0)
    : fallback.hiddenEventIds;

  return {
    enrollmentClosed: closedEventIds.length > 0 || Boolean(planner.enrollmentClosed ?? planner.enrollment_closed ?? false),
    closedEventIds,
    hiddenEventIds,
    participants: Array.isArray(planner.participants)
      ? planner.participants
          .map((participant) => ({
            id: toNumber(participant.id) ?? 0,
            fullName: String(participant.fullName ?? participant.full_name ?? ""),
          }))
          .filter((participant) => participant.id > 0 && participant.fullName)
      : fallback.participants,
    teams: mapBackendTeams(planner.teams, fallback),
    parentTasks: mapBackendParentTasks(planner.parentTasks ?? planner.parent_tasks, fallback),
    subtasks: mappedSubtasks,
    columns: Array.isArray(planner.columns) && planner.columns.length > 0 ? planner.columns : fallback.columns,
  };
}

function toBackendPlannerWorkspace(state: PlannerState) {
  return {
    enrollment_closed: state.closedEventIds.length > 0,
    closed_event_ids: state.closedEventIds,
    hidden_event_ids: state.hiddenEventIds,
    participants: state.participants.map((participant) => ({
      id: participant.id,
      full_name: participant.fullName,
    })),
    teams: state.teams,
    columns: state.columns,
  };
}

function toBackendTeamDesk(state: PlannerState, teamId: number) {
  const team = state.teams.find((item) => Number(item.id) === Number(teamId));
  return {
    team_id: teamId,
    team_name: team?.name ?? "",
    curator_id: team?.curatorId ?? null,
    member_ids: team?.memberIds ?? [],
    updated_at: team?.updatedAt ?? "",
    parent_tasks: state.parentTasks.filter((task) => Number(task.teamId) === Number(teamId)),
    subtasks: state.subtasks.filter((subtask) => Number(subtask.teamId) === Number(teamId)),
    columns: state.columns,
  };
}

export async function getPlannerState(): Promise<PlannerState> {
  if (USE_MOCK) return readPlannerState(true);
  try {
    const raw = await client.get<unknown>("/api/users/planner/");
    const mapped = mapBackendPlanner(raw);
    writePlannerState(mapped);
    return mapped;
  } catch {
    return readPlannerState(false);
  }
}

export async function savePlannerWorkspaceState(state: PlannerState): Promise<PlannerState> {
  writePlannerState(state);
  if (USE_MOCK) return state;
  try {
    await client.patch("/api/users/planner/", toBackendPlannerWorkspace(state));
  } catch {
  }
  return state;
}

export async function savePlannerTeamDesk(state: PlannerState, teamId: number): Promise<PlannerState> {
  writePlannerState(state);
  if (USE_MOCK) return state;
  try {
    await client.put(`/api/planner/teams/${teamId}/desk/`, toBackendTeamDesk(state, teamId));
  } catch {
  }
  return state;
}

export async function savePlannerState(state: PlannerState, activeTeamId?: number | null): Promise<PlannerState> {
  writePlannerState(state);
  if (USE_MOCK) return state;

  await savePlannerWorkspaceState(state);
  if (activeTeamId != null && Number.isFinite(activeTeamId) && activeTeamId > 0) {
    await savePlannerTeamDesk(state, activeTeamId);
  }
  return state;
}

export type PlannerInviteResult = {
  sent: number;
  failed: number;
  skipped: number;
};

export type PlannerInviteRecipientMode = "all" | "joined" | "declined";

export async function sendPlannerInviteMessages(
  eventId: number,
  recipientMode: PlannerInviteRecipientMode = "joined"
): Promise<PlannerInviteResult | null> {
  if (USE_MOCK) return null;
  return client.post<PlannerInviteResult>(`/api/integrations/vk/events/${eventId}/planner-invite/`, {
    recipient_mode: recipientMode,
  });
}

function isStudent(user: User) {
  const role = String(user.role || "").toLowerCase();
  return role === "student" || role.includes("project");
}

export function buildParticipantsFromRequests(users: User[], requests: Request[], closedEventIds: number[] = []): PlannerParticipant[] {
  const students = users.filter(isStudent);
  const userNameById = new Map<number, string>(
    students.map((user) => [Number(user.id), `${user.surname || ""} ${user.name || ""}`.trim() || user.email])
  );
  const requestNameById = new Map<number, string>();
  requests.forEach((request) => {
    const ownerId = toNumber(request.ownerId);
    const studentName = String(request.studentName || "").trim();
    if (typeof ownerId === "undefined" || !studentName) return;
    requestNameById.set(ownerId, studentName);
  });
  const validStudentIds = new Set<number>(students.map((user) => Number(user.id)));
  const closedEventIdSet = new Set(
    closedEventIds.map((id) => Number(id)).filter((id) => Number.isFinite(id) && id > 0)
  );

  const ids = new Set<number>();
  requests.forEach((request) => {
    if (isNegativeRequestStatus(request.status)) return;
    if (!hasPlannerAccessStatus(request.status)) return;
    const ownerId = toNumber(request.ownerId);
    const eventId = toNumber(request.eventId);
    if (typeof ownerId === "undefined") return;
    if (closedEventIdSet.size > 0 && (typeof eventId === "undefined" || !closedEventIdSet.has(eventId))) return;
    if (validStudentIds.has(ownerId)) ids.add(ownerId);
  });

  return Array.from(ids).map((id) => ({
    id,
    fullName: userNameById.get(id) || requestNameById.get(id) || `Участник #${id}`,
  }));
}

function uniqParticipants(items: PlannerParticipant[]): PlannerParticipant[] {
  const byId = new Map<number, PlannerParticipant>();
  items.forEach((item) => {
    if (!item || !item.id) return;
    byId.set(Number(item.id), {
      id: Number(item.id),
      fullName: String(item.fullName || "").trim() || `Участник #${item.id}`,
    });
  });
  return Array.from(byId.values());
}

export function syncParticipants(state: PlannerState, incoming: PlannerParticipant[]): PlannerState {
  const keepFromTeams = new Set<number>();
  state.teams.forEach((team) => team.memberIds.forEach((id) => keepFromTeams.add(Number(id))));

  const merged = uniqParticipants([
    ...incoming,
    ...Array.from(keepFromTeams).map((id) => ({
      id,
      fullName: state.participants.find((participant) => Number(participant.id) === id)?.fullName || `Участник #${id}`,
    })),
  ]);

  return { ...state, participants: merged };
}

