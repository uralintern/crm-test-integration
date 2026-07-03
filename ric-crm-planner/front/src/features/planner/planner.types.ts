import type { Dayjs } from "dayjs";

export type PlannerTab = "teams" | "backlog" | "kanban" | "gantt";

export type ParentEditDraft = {
  title: string;
  assigneeId?: number;
  startDate?: Dayjs;
  endDate?: Dayjs;
};

export type SubtaskEditDraft = {
  title: string;
  assigneeId?: number;
  startDate?: Dayjs;
  endDate?: Dayjs;
  status: string;
  inSprint: boolean;
};

export type ProjectApplicantsGroup = {
  key: string;
  eventId?: number;
  eventTitle: string;
  directionOptions: Array<{
    id: number;
    title: string;
    projects: Array<{ id: number; title: string }>;
  }>;
  applicants: Array<{
    ownerId: number;
    name: string;
    status?: string;
    specialization?: string;
    desiredDirections: Array<{ id?: number; title: string }>;
    requestIds: number[];
  }>;
};

export type ApplicantsTreeNode = {
  key: string;
  eventId?: number;
  eventClosed?: boolean;
  eventHidden?: boolean;
  title: string;
  group: ProjectApplicantsGroup;
};

export type TaskCardState = { type: "parent" | "subtask"; id: number } | null;
