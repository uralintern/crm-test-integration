import client from "../../../api/client";
import type { Direction } from "../../../types/direction";
import {
  getAllUsers,
  getDirectionById as _getDirectionById,
  getDirectionsByEvent as _getDirectionsByEvent,
  saveDirectionsForEvent as _saveDirectionsForEvent,
} from "../../../storage/storage";

const USE_MOCK = client.USE_MOCK;

type UnknownRecord = Record<string, unknown>;

type BackendDirection = {
  id?: number | string;
  title?: string;
  name?: string;
  description?: string;
  leader?: number | string | null;
  organizer?: number | string | null;
  organizerName?: string;
  eventId?: number | string;
  event?: number | string;
};

type BackendDirectionPayload = {
  id?: number | string;
  name: string;
  description: string;
  leader?: number;
};

type BackendUser = {
  id?: number | string;
  name?: string;
  firstName?: string;
  first_name?: string;
  surname?: string;
  lastName?: string;
  last_name?: string;
  role?: string;
};

function asRecord(value: unknown): UnknownRecord {
  return value && typeof value === "object" ? (value as UnknownRecord) : {};
}

function toStringValue(value: unknown): string | undefined {
  if (typeof value === "string") return value;
  if (typeof value === "number") return String(value);
  return undefined;
}

function isTempId(id: unknown) {
  if (id == null) return false;
  const n = Number(id);
  if (Number.isNaN(n)) return true;
  return String(n).length >= 12 || n > 1e11;
}

function mapToBackendPayload(d: Direction): BackendDirectionPayload {
  const payload: BackendDirectionPayload = {
    name: d.title ?? "",
    description: d.description ?? "",
  };

  const leaderVal = d.leader ?? d.organizer ?? undefined;
  if (typeof leaderVal === "number") {
    payload.leader = leaderVal;
  } else if (typeof leaderVal === "string") {
    const n = Number(leaderVal);
    if (!Number.isNaN(n)) payload.leader = n;
  }

  if (d.id && !isTempId(d.id)) payload.id = d.id;

  return payload;
}

function normalizeDirectionForSave(value: unknown): Direction {
  const dir = normalizeBackendDirection(value);
  const title = (dir.title ?? dir.name ?? "").trim();
  const description = (dir.description ?? "").trim();
  const eventId = toNumber(dir.eventId ?? dir.event);
  const leader = dir.leader ?? undefined;
  const organizer =
    typeof dir.organizer === "string"
      ? dir.organizer
      : typeof dir.organizer === "number"
      ? String(dir.organizer)
      : typeof leader === "number"
      ? String(leader)
      : typeof leader === "string"
      ? leader
      : undefined;

  return {
    id: Number(dir.id ?? 0),
    title,
    description,
    organizer,
    leader: leader ?? undefined,
    eventId,
  };
}

function toNumber(value: unknown): number | undefined {
  if (typeof value === "number" && !Number.isNaN(value)) return value;
  if (typeof value === "string") {
    const n = Number(value);
    if (!Number.isNaN(n)) return n;
  }
  return undefined;
}

function normalizeBackendDirection(value: unknown): BackendDirection {
  const obj = asRecord(value);
  return {
    id: toStringValue(obj.id) ?? (typeof obj.id === "number" ? obj.id : undefined),
    title: toStringValue(obj.title),
    name: toStringValue(obj.name),
    description: toStringValue(obj.description),
    leader: (typeof obj.leader === "number" || typeof obj.leader === "string" ? obj.leader : null) ?? null,
    organizer: (typeof obj.organizer === "number" || typeof obj.organizer === "string" ? obj.organizer : null) ?? null,
    organizerName: toStringValue(obj.organizerName),
    eventId: typeof obj.eventId === "number" || typeof obj.eventId === "string" ? obj.eventId : undefined,
    event: typeof obj.event === "number" || typeof obj.event === "string" ? obj.event : undefined,
  };
}

async function mapToUiDirections(raw: unknown[]): Promise<Direction[]> {
  const users = (await getAllUsers().catch(() => [])) as BackendUser[];
  const userNameById = new Map<number, string>();

  users.forEach((u) => {
    const display = `${u.surname ?? u.lastName ?? u.last_name ?? ""} ${u.name ?? u.firstName ?? u.first_name ?? ""}`.trim();
    const userId = toNumber(u.id);
    if (display && typeof userId !== "undefined") userNameById.set(userId, display);
  });

  return raw.map((item) => {
    const dir = normalizeBackendDirection(item);
    const leaderId = toNumber(dir.leader ?? dir.organizer);
    const organizerName =
      (typeof leaderId !== "undefined" ? userNameById.get(leaderId) : undefined) ??
      dir.organizerName ??
      (dir.organizer != null ? String(dir.organizer) : undefined);

    return {
      ...dir,
      id: Number(dir.id ?? 0),
      title: dir.title ?? dir.name ?? "",
      description: dir.description ?? "",
      organizer: organizerName,
      eventId: toNumber(dir.eventId ?? dir.event),
    } as Direction;
  });
}

export async function getDirectionsByEvent(eventId: number): Promise<Direction[]> {
  if (USE_MOCK) {
    const raw = await _getDirectionsByEvent(eventId);
    return mapToUiDirections(Array.isArray(raw) ? raw : []);
  }
  const raw = await client.get(`/api/users/events/${eventId}/directions/`);
  return mapToUiDirections(Array.isArray(raw) ? raw : []);
}

export async function getDirectionById(id: number): Promise<Direction | undefined> {
  if (USE_MOCK) {
    const one = await _getDirectionById(id);
    if (!one) return undefined;
    const mapped = await mapToUiDirections([one]);
    return mapped[0];
  }

  try {
    const list = await client.get("/api/users/directions/");
    const mapped = await mapToUiDirections(Array.isArray(list) ? list : []);
    return mapped.find((x) => Number(x.id) === Number(id));
  } catch {
    return undefined;
  }
}

export async function saveDirectionsForEvent(eventId: number, dirs: Direction[]) {
  if (USE_MOCK) {
    const normalized = dirs.map((d) => normalizeDirectionForSave(d));
    const saved = await _saveDirectionsForEvent(eventId, normalized);
    return mapToUiDirections(Array.isArray(saved) ? saved : []);
  }

  const existing = await getDirectionsByEvent(eventId).catch(() => []);
  const keepIds = new Set(
    dirs
      .map((direction) => direction.id)
      .filter((id): id is number => typeof id === "number" && !isTempId(id))
      .map((id) => Number(id))
  );
  await Promise.all(
    existing
      .filter((direction) => direction.id && !keepIds.has(Number(direction.id)))
      .map((direction) => client.del(`/api/users/events/${eventId}/directions/${direction.id}/`).catch(() => null))
  );

  const created: unknown[] = [];
  for (const d of dirs) {
    const payload = mapToBackendPayload(d);
    if (d.id && !isTempId(d.id)) {
      await client.put(`/api/users/events/${eventId}/directions/${d.id}/`, payload);
      created.push({ ...payload, id: d.id });
    } else {
      const res = await client.post(`/api/users/events/${eventId}/directions/`, payload);
      created.push(res);
    }
  }
  return mapToUiDirections(created);
}

