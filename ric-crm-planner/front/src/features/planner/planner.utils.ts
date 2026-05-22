import type { User } from "../../types/user";
import { DEFAULT_KANBAN_COLUMNS } from "./storage/planner";

export const fullName = (user: User) => `${user.surname || ""} ${user.name || ""}`.trim();

export const PLANNED_KANBAN_STATUS = DEFAULT_KANBAN_COLUMNS[0] || "Запланировано";
export const DONE_KANBAN_STATUS = DEFAULT_KANBAN_COLUMNS[DEFAULT_KANBAN_COLUMNS.length - 1] || "Готово";

export function isDoneKanbanStatus(value?: string) {
  return String(value || "").trim().toLowerCase() === DONE_KANBAN_STATUS.toLowerCase();
}

export function roleFlags(roleRaw?: string) {
  const role = String(roleRaw || "").toLowerCase();
  return {
    isOrganizer: role === "organizer" || role.includes("admin"),
    isCurator: role.includes("curator"),
    isStudent: role === "student" || role.includes("project"),
  };
}

export function isFallbackParticipantName(value: string) {
  return /^Участник #\d+$/.test(value);
}

