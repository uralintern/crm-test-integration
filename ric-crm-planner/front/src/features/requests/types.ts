import type { RequestTransitionSource } from "../../constants/requestProgress";
import type { Request as RequestType } from "../../types/request";

export type RequestRecord = RequestType & {
  eventName?: string;
  event?: string;
  event_name?: string;
};

export type RequestTableRow = {
  id: number;
  studentName: string;
  event: string;
  specialization: string;
  status: string;
  raw: RequestRecord;
};

export type PendingTransition = {
  requestId: number;
  targetStatus: string;
  source: RequestTransitionSource;
  title: string;
  message: string;
};

export type RequestsView = "list" | "diagram";
export type RequestsChartView = "circle" | "line";
export type EventFilter = number | "all";
export type AnalyticsStatusKey = string;

export type AnalyticsStatus = {
  key: AnalyticsStatusKey;
  label: string;
  count: number;
  color: string;
  students: RequestRecord[];
  showStatus?: boolean;
};
