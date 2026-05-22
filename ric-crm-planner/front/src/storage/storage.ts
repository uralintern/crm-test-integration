import client from "../api/client";
import seedDirections from "../mock-data/directions.json";
import seedEvents from "../mock-data/events.json";
import seedProfile from "../mock-data/profile.json";
import seedProjects from "../mock-data/projects.json";
import seedUsers from "../mock-data/users.json";
import { CURRENT_MOCK_SEED_VERSION, LS_MOCK_SEED_VERSION } from "./mockSeed";
import { readPlannerState, writePlannerState } from "../features/planner/storage/planner";
import type { Direction } from "../types/direction";
import type { Event } from "../types/event";
import type { Project } from "../types/project";
import type { User } from "../types/user";

const USE_MOCK = client.USE_MOCK;
type UnknownRecord = Record<string, unknown>;
type LocalUser = User & UnknownRecord;

const LS_EVENTS = "ric_mock_events";
const LS_DIRECTIONS = "ric_mock_directions";
const LS_PROJECTS = "ric_mock_projects";
const LS_PROFILES = "ric_mock_profiles";
const LS_USERS = "users";
const LS_ARCHIVED_EVENT_IDS = "ric_archived_event_ids";

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value));
}

function readLS<T>(key: string, fallback: T): T {
  const raw = localStorage.getItem(key);
  if (!raw) return clone(fallback);
  try {
    return JSON.parse(raw) as T;
  } catch {
    return clone(fallback);
  }
}

function writeLS<T>(key: string, value: T) {
  localStorage.setItem(key, JSON.stringify(value));
}

function nextId(items: Array<{ id?: number }>): number {
  const max = items.reduce((acc, x) => Math.max(acc, Number(x.id || 0)), 0);
  return max + 1;
}

function toNumber(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function mapUserRecord(raw: unknown): User | null {
  if (!raw || typeof raw !== "object") return null;
  const record = raw as UnknownRecord;
  const profile = record.profile && typeof record.profile === "object" ? (record.profile as UnknownRecord) : {};
  const id = toNumber(record.id ?? record.pk);
  if (!id) return null;

  const email = String(record.email ?? profile.email ?? "");
  const name = String(record.name ?? record.firstName ?? record.first_name ?? profile.name ?? "");
  const surname = String(record.surname ?? record.lastName ?? record.last_name ?? profile.surname ?? "");
  const role = String(record.role ?? profile.role ?? "");
  const isSuperuser = Boolean(record.isSuperuser ?? record.is_superuser);
  const isStaff = Boolean(record.isStaff ?? record.is_staff);

  return {
    id,
    email,
    name,
    surname,
    role: role || "student",
    isSuperuser,
    isStaff,
  };
}

function ensureMockSeeded() {
  const storedVersion = localStorage.getItem(LS_MOCK_SEED_VERSION);
  if (storedVersion !== CURRENT_MOCK_SEED_VERSION) {
    writeLS(LS_EVENTS, seedEvents);
    writeLS(LS_DIRECTIONS, seedDirections);
    writeLS(LS_PROJECTS, seedProjects);
    writeLS(LS_PROFILES, seedProfile || {});
    writeLS(LS_USERS, []);
    localStorage.removeItem("currentUser");
    localStorage.removeItem(LS_ARCHIVED_EVENT_IDS);
    localStorage.setItem(LS_MOCK_SEED_VERSION, CURRENT_MOCK_SEED_VERSION);
    return;
  }

  if (!localStorage.getItem(LS_EVENTS)) writeLS(LS_EVENTS, seedEvents);
  if (!localStorage.getItem(LS_DIRECTIONS)) writeLS(LS_DIRECTIONS, seedDirections);
  if (!localStorage.getItem(LS_PROJECTS)) writeLS(LS_PROJECTS, seedProjects);
  if (!localStorage.getItem(LS_PROFILES)) writeLS(LS_PROFILES, seedProfile || {});
}

function mockEvents(): Event[] {
  ensureMockSeeded();
  return readLS<Event[]>(LS_EVENTS, seedEvents as Event[]);
}

function mockDirections(): Direction[] {
  ensureMockSeeded();
  return readLS<Direction[]>(LS_DIRECTIONS, seedDirections as Direction[]);
}

function mockProjects(): Project[] {
  ensureMockSeeded();
  return readLS<Project[]>(LS_PROJECTS, seedProjects as Project[]);
}

function writeMockEvents(items: Event[]) {
  writeLS(LS_EVENTS, items);
}

function writeMockDirections(items: Direction[]) {
  writeLS(LS_DIRECTIONS, items);
}

function writeMockProjects(items: Project[]) {
  writeLS(LS_PROJECTS, items);
}

function uniqueNumbers(values: unknown[]): number[] {
  return Array.from(
    new Set(
      values
        .map((value) => Number(value))
        .filter((value) => Number.isFinite(value) && value > 0)
    )
  );
}

function hideArchivedEventInPlanner(id: number) {
  const state = readPlannerState(USE_MOCK);
  writePlannerState({
    ...state,
    hiddenEventIds: uniqueNumbers([...state.hiddenEventIds, id]),
  });
}

export function getArchivedEventIds(): number[] {
  const storedIds = readLS<number[]>(LS_ARCHIVED_EVENT_IDS, []);
  const archivedMockIds = USE_MOCK
    ? mockEvents()
        .filter((event) => event.archived)
        .map((event) => Number(event.id))
    : [];

  return uniqueNumbers([...storedIds, ...archivedMockIds]);
}

export function isEventArchived(id: number): boolean {
  return getArchivedEventIds().includes(Number(id));
}

export function rememberArchivedEventId(id: number) {
  const eventId = Number(id);
  if (!Number.isFinite(eventId) || eventId <= 0) return;

  writeLS(LS_ARCHIVED_EVENT_IDS, uniqueNumbers([...getArchivedEventIds(), eventId]));
  hideArchivedEventInPlanner(eventId);
}

export function forgetArchivedEventId(id: number) {
  const eventId = Number(id);
  if (!Number.isFinite(eventId) || eventId <= 0) return;

  writeLS(
    LS_ARCHIVED_EVENT_IDS,
    getArchivedEventIds().filter((archivedId) => Number(archivedId) !== eventId)
  );

  const state = readPlannerState(USE_MOCK);
  writePlannerState({
    ...state,
    hiddenEventIds: state.hiddenEventIds.filter((hiddenId) => Number(hiddenId) !== eventId),
  });
}

export async function archiveEvent(id: number): Promise<Event | undefined> {
  const eventId = Number(id);
  const events = mockEvents();
  const idx = events.findIndex((event) => Number(event.id) === eventId);

  rememberArchivedEventId(eventId);

  if (idx < 0) return undefined;

  const archivedEvent: Event = {
    ...events[idx],
    archived: true,
    archivedAt: new Date().toISOString(),
  };

  events[idx] = archivedEvent;
  writeMockEvents(events);
  return archivedEvent;
}

export async function getArchivedEvents(): Promise<Event[]> {
  const archivedIds = new Set(getArchivedEventIds());
  return mockEvents().filter((event) => event.archived || archivedIds.has(Number(event.id)));
}

export async function restoreEvent(id: number): Promise<Event | undefined> {
  const eventId = Number(id);
  const events = mockEvents();
  const idx = events.findIndex((event) => Number(event.id) === eventId);

  forgetArchivedEventId(eventId);

  if (idx < 0) return undefined;

  const restoredEvent: Event = {
    ...events[idx],
    archived: false,
    archivedAt: undefined,
  };

  events[idx] = restoredEvent;
  writeMockEvents(events);

  return restoredEvent;
}

export async function getEvents(): Promise<Event[]> {
  if (USE_MOCK) {
    const archivedIds = new Set(getArchivedEventIds());
    return mockEvents().filter((event) => !event.archived && !archivedIds.has(Number(event.id)));
  }
  return client.get("/api/users/events/");
}

export async function getEventById(id: number): Promise<Event | undefined> {
  if (USE_MOCK) {
    return mockEvents().find((x) => Number(x.id) === Number(id));
  }
  try {
    return await client.get(`/api/users/events/${id}/`);
  } catch {
    return undefined;
  }
}

export async function saveEvent(ev: Event): Promise<Event> {
  if (!USE_MOCK) {
    if (ev.id) return client.put(`/api/users/events/${ev.id}/`, ev);
    return client.post("/api/users/events/", ev);
  }

  const events = mockEvents();
  if (ev.id) {
    const idx = events.findIndex((x) => Number(x.id) === Number(ev.id));
    if (idx >= 0) {
      events[idx] = { ...events[idx], ...ev };
      writeMockEvents(events);
      return events[idx];
    }
  }

  const created: Event = { ...ev, id: nextId(events as Array<{ id?: number }>) } as Event;
  events.push(created);
  writeMockEvents(events);
  return created;
}

export async function removeEvent(id: number): Promise<{ ok: true }> {
  if (!USE_MOCK) {
    rememberArchivedEventId(id);
    await client.patch(`/api/users/events/${id}/`, { archived: true, is_archived: true });
    return { ok: true };
  }

  await archiveEvent(id);
  return { ok: true };
}

export async function getDirectionsByEvent(eventId: number): Promise<Direction[]> {
  if (USE_MOCK) {
    return mockDirections().filter((x) => Number(x.eventId) === Number(eventId));
  }
  return client.get(`/api/users/events/${eventId}/directions/`);
}

export async function getDirectionById(id: number): Promise<Direction | undefined> {
  if (USE_MOCK) {
    return mockDirections().find((x) => Number(x.id) === Number(id));
  }
  try {
    const all: Direction[] = await client.get("/api/users/directions/");
    return all.find((d) => Number(d.id) === Number(id));
  } catch {
    return undefined;
  }
}

export async function saveDirectionsForEvent(eventId: number, dirs: Direction[]): Promise<Direction[]> {
  if (!USE_MOCK) {
    const results: Direction[] = [];
    const isTempId = (id: unknown) => {
      if (id == null) return false;
      const n = Number(id);
      if (Number.isNaN(n)) return true;
      return String(n).length >= 12 || n > 1e11;
    };

    for (const d of dirs) {
      if (d.id && !isTempId(d.id)) {
        results.push(await client.put(`/api/users/events/${eventId}/directions/${d.id}/`, d));
      } else {
        results.push(await client.post(`/api/users/events/${eventId}/directions/`, d));
      }
    }
    return results;
  }

  const existing = mockDirections().filter((x) => Number(x.eventId) !== Number(eventId));
  const current = mockDirections().filter((x) => Number(x.eventId) === Number(eventId));

  let idCounter = nextId(current as Array<{ id?: number }>);
  const persisted = dirs.map((d) => {
    const id = d.id && Number(d.id) > 0 ? Number(d.id) : idCounter++;
    return {
      ...d,
      id,
      eventId,
    } as Direction;
  });

  writeMockDirections([...existing, ...persisted]);
  return persisted;
}

export async function getProjectsByDirection(directionId: number): Promise<Project[]> {
  if (USE_MOCK) {
    return mockProjects().filter((x) => Number(x.directionId) === Number(directionId));
  }

  try {
    const all = await client.get<Project[]>("/api/users/projects/");
    if (!Array.isArray(all)) return [];
    return all.filter((x) => Number(x.directionId) === Number(directionId));
  } catch {
    return [];
  }
}

export async function saveProjectsForDirection(directionId: number, projects: Project[]): Promise<Project[]> {
  if (!USE_MOCK) {
    const out: Project[] = [];
    for (const p of projects) {
      if (p.id) out.push(await client.put(`/api/users/projects/${p.id}/`, p));
      else out.push(await client.post("/api/users/projects/", { ...p, direction_id: directionId }));
    }
    return out;
  }

  const current = mockProjects().filter((x) => Number(x.directionId) !== Number(directionId));
  const own = mockProjects().filter((x) => Number(x.directionId) === Number(directionId));

  let idCounter = nextId(own as Array<{ id?: number }>);
  const persisted = projects.map((p) => {
    const id = p.id && Number(p.id) > 0 ? Number(p.id) : idCounter++;
    return {
      ...p,
      id,
      directionId,
    } as Project;
  });

  writeMockProjects([...current, ...persisted]);
  return persisted;
}

export async function getAllUsers(): Promise<User[]> {
  if (!USE_MOCK) {
    if (!localStorage.getItem("currentUser")) return [];
    try {
      const raw = await client.get<unknown[]>("/api/users/");
      if (!Array.isArray(raw)) return [];
      return raw.map(mapUserRecord).filter((user): user is User => Boolean(user));
    } catch {
      return [];
    }
  }

  const base = clone(seedUsers as User[]);
  const local = readLS<LocalUser[]>(LS_USERS, []);
  const byId = new Map<number, User>();

  [...base, ...local].forEach((u) => {
    if (u && typeof u.id !== "undefined") byId.set(Number(u.id), u as User);
  });

  return Array.from(byId.values());
}

export async function saveUser(user: User): Promise<User> {
  if (!USE_MOCK) return client.post("/api/users/register/", user);

  const users = await getAllUsers();
  const id = user.id ?? nextId(users as Array<{ id?: number }>);
  const created = { ...user, id };
  writeLS(LS_USERS, [...users.filter((u) => Number(u.id) !== Number(id)), created]);
  return created;
}

export async function getProfile(userId: number): Promise<UnknownRecord | undefined> {
  if (!USE_MOCK) {
    if (!localStorage.getItem("currentUser")) return undefined;
    try {
      return await client.get("/api/users/profile/");
    } catch {
      return undefined;
    }
  }

  const profiles = readLS<Record<string, UnknownRecord>>(LS_PROFILES, seedProfile || {});
  return profiles[String(userId)] || {};
}

export async function saveProfile(userId: number, profile: UnknownRecord) {
  if (!USE_MOCK) return client.put("/api/users/profile/", profile);

  const profiles = readLS<Record<string, UnknownRecord>>(LS_PROFILES, seedProfile || {});
  profiles[String(userId)] = { ...(profiles[String(userId)] || {}), ...profile };
  writeLS(LS_PROFILES, profiles);
  return profiles[String(userId)];
}



