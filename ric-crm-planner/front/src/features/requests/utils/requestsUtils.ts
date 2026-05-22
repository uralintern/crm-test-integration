import { ORGANIZER_REQUEST_STATUSES } from "../../../constants/requestProgress";
import {
  DASHBOARD_START_ANGLE,
  DASHBOARD_SWEEP_ANGLE,
  DISPLAYED_STATUSES_STORAGE_KEY,
} from "../config/requestsConfig";
import type { RequestsChartView, RequestsView, RequestRecord } from "../types";

export function isRequestsChartView(value: string | null): value is RequestsChartView {
  return value === "circle" || value === "line";
}

export function isRequestsView(value: string | null): value is RequestsView {
  return value === "list" || value === "diagram";
}

export function readDisplayedStatuses() {
  const fallback = [...ORGANIZER_REQUEST_STATUSES];
  const savedStatuses = window.localStorage.getItem(DISPLAYED_STATUSES_STORAGE_KEY);
  if (!savedStatuses) return fallback;

  try {
    const parsed = JSON.parse(savedStatuses);
    if (!Array.isArray(parsed)) return fallback;

    return ORGANIZER_REQUEST_STATUSES.filter((status) => parsed.includes(status));
  } catch {
    return fallback;
  }
}

function getArcPoint(cx: number, cy: number, radius: number, angle: number) {
  const radians = ((angle - 90) * Math.PI) / 180;
  return {
    x: cx + radius * Math.cos(radians),
    y: cy + radius * Math.sin(radians),
  };
}

export function getArcPath(startAngle: number, endAngle: number) {
  const start = getArcPoint(100, 100, 72, endAngle);
  const end = getArcPoint(100, 100, 72, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1";

  return `M ${start.x} ${start.y} A 72 72 0 ${largeArcFlag} 0 ${end.x} ${end.y}`;
}

export function getStatusSegmentPath(index: number, percent: number, accumulatedPercent: number) {
  const startAngle = DASHBOARD_START_ANGLE + (DASHBOARD_SWEEP_ANGLE * accumulatedPercent) / 100;
  const endAngle = startAngle + (DASHBOARD_SWEEP_ANGLE * percent) / 100;
  const gap = index === 0 ? 0 : 1.5;
  return getArcPath(startAngle + gap, endAngle - gap);
}

export function eventTitleFromRecord(request: RequestRecord) {
  return request.eventTitle || request.eventName || request.event || request.event_name || "-";
}

export function isOrganizerRole(role?: string) {
  const normalized = String(role || "").toLowerCase();
  return normalized === "organizer" || normalized.includes("admin") || normalized.includes("curator");
}

export function isProjectantRole(role?: string) {
  const normalized = String(role || "").toLowerCase();
  return normalized === "student" || normalized.includes("project");
}
