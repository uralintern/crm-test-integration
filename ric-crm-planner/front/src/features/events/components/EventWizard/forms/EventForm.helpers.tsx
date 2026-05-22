import type { ReactNode } from "react";
import type { User } from "../../../../../types/user";

export interface SpecializationOption {
  id: number;
  title: string;
}

export type SaveState = "idle" | "synced";

export type EventDraft = {
  title: string;
  description: string;
  startDate: string;
  endDate: string;
  applyDeadline: string;
  orgChatUrl: string;
  orgChatPeerId: string;
  organizerIds: string[];
  specializations: SpecializationOption[];
};

export const CREATE_DRAFT_KEY = "ric_event_wizard_create_draft_v1";

export function FieldWrap({ name, errors, children }: { name: string; errors: Record<string, string>; children: ReactNode }) {
  return (
    <div className={`field-wrap ${errors[name] ? "error" : ""}`}>
      {children}
      {errors[name] && <div className="field-error">{errors[name]}</div>}
    </div>
  );
}

export function normalizeDateFieldValue(value?: string) {
  if (!value) return "";
  return value.includes("T") ? value.slice(0, 10) : value;
}

export function extractVkPeerId(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return "";

  const convoMatch = trimmed.match(/\/im\/convo\/(200000\d+)/i);
  if (convoMatch) return convoMatch[1];

  const peerMatch = trimmed.match(/[?&](?:peer_id|peer)=(200000\d+)/i);
  if (peerMatch) return peerMatch[1];

  const selChatMatch = trimmed.match(/[?&]sel=c(\d+)/i);
  if (selChatMatch) return String(2_000_000_000 + Number(selChatMatch[1]));

  const directMatch = trimmed.match(/^200000\d+$/);
  if (directMatch) return trimmed;

  return trimmed;
}

export function readCreateDraft(): EventDraft | null {
  const raw = localStorage.getItem(CREATE_DRAFT_KEY);
  if (!raw) return null;

  try {
    return JSON.parse(raw) as EventDraft;
  } catch {
    return null;
  }
}

export function extractErrorMessage(error: unknown) {
  if (typeof error === "string" && error.trim()) return error;

  if (error && typeof error === "object") {
    const record = error as Record<string, unknown>;
    if (typeof record.message === "string" && record.message.trim()) return record.message;

    const parts = Object.values(record)
      .flatMap((value) => {
        if (typeof value === "string") return [value];
        if (Array.isArray(value)) return value.filter((item): item is string => typeof item === "string");
        return [];
      })
      .filter((part) => part.trim());

    if (parts.length > 0) return parts.join(" ");
  }

  return "Ошибка при сохранении мероприятия";
}

export function getUserLabel(user: User) {
  const raw = user as User & Record<string, unknown>;
  const name = user.name ?? String(raw.firstName ?? raw.first_name ?? "");
  const surname = user.surname ?? String(raw.lastName ?? raw.last_name ?? "");
  return `${surname} ${name}`.trim() || String(user.id);
}
