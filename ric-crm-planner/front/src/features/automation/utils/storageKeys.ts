import type { Event } from "../../../types/event";
import type { AutomationConfig, AutomationScope } from "../types";

const AUTOMATION_SELECTED_EVENT_STORAGE_PREFIX = "automation-selected-event";
const AUTOMATION_SELECTED_STAGE_STORAGE_PREFIX = "automation-selected-stage";

export function getEventTitle(event?: Event) {
  return event?.title?.trim() || `Мероприятие #${event?.id ?? ""}`;
}

export function getEventStorageKey(scope: AutomationScope) {
  return `${AUTOMATION_SELECTED_EVENT_STORAGE_PREFIX}:${scope}`;
}

export function getStageStorageKey(scope: AutomationScope, eventId: number) {
  return `${AUTOMATION_SELECTED_STAGE_STORAGE_PREFIX}:${scope}:${eventId}`;
}

export function readStoredEventId(scope: AutomationScope, events: Event[]) {
  const savedEventId = Number(window.localStorage.getItem(getEventStorageKey(scope)));
  if (!Number.isFinite(savedEventId)) return null;

  return events.some((event) => Number(event.id) === savedEventId) ? savedEventId : null;
}

export function readStoredStageId(scope: AutomationScope, eventId: number, config: AutomationConfig) {
  const savedStageId = window.localStorage.getItem(getStageStorageKey(scope, eventId));
  if (!savedStageId) return "";

  return config.stages.some((stage) => stage.id === savedStageId) ? savedStageId : "";
}
