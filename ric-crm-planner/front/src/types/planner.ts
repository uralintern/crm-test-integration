import { Dayjs } from "dayjs";

export interface PlannerParticipant {
  id: number;
  fullName: string;
}

export interface PlannerTeam {
  id: number;
  name: string;
  curatorId?: number;
  memberIds: number[];
  memberRoles?: Record<string, string>;
  confirmed: boolean;
  eventId?: number;
  directionId?: number;
  projectId?: number;
  sourceRequestIds?: number[];
  createdBy?: number;
  updatedAt?: string;
}

export interface PlannerTaskChecklistItem {
  id: number;
  text: string;
  completed: boolean;
}

export interface PlannerParentTask {
  id: number;
  teamId: number;
  title: string;
  description?: string;
  checklist?: PlannerTaskChecklistItem[];
  assigneeId?: number;
  startDate?: Dayjs;
  endDate?: Dayjs;
  createdBy?: number;
  updatedAt?: string;
}

export interface PlannerSubtask {
  id: number;
  teamId: number;
  parentTaskId: number;
  title: string;
  role: string;
  assigneeId?: number;
  startDate?: Dayjs;
  endDate?: Dayjs;
  inSprint: boolean;
  status: string;
  description?: string;
  checklist?: PlannerTaskChecklistItem[];
  createdBy?: number;
  updatedAt?: string;
}

export interface PlannerState {
  enrollmentClosed: boolean;
  closedEventIds: number[];
  hiddenEventIds: number[];
  participants: PlannerParticipant[];
  teams: PlannerTeam[];
  parentTasks: PlannerParentTask[];
  subtasks: PlannerSubtask[];
  columns: string[];
}
