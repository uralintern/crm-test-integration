import client from "../../../api/client";
import { readPlannerState } from "../../planner/storage/planner";
import {
  archiveEvent as archiveStoredEvent,
  forgetArchivedEventId,
  getAllUsers,
  getArchivedEventIds,
  getArchivedEvents as getStoredArchivedEvents,
  getDirectionsByEvent as getStoredDirectionsByEvent,
  getEventById as getStoredEventById,
  getEvents as getStoredEvents,
  rememberArchivedEventId,
  restoreEvent as restoreStoredEvent,
  saveEvent as saveStoredEvent,
} from "../../../storage/storage";
import type { ApplicationFormField, Event } from "../../../types/event";
import type { User } from "../../../types/user";

const USE_MOCK = client.USE_MOCK;
const LS_EVENT_EXTENSIONS = "ric_event_extensions_v1";

type UnknownRecord = Record<string, unknown>;

type BackendSpecialization = {
  id: number;
  name?: string;
  title?: string;
  description?: string;
};

type BackendEvent = {
  id?: number | string;
  title?: string;
  name?: string;
  description?: string;
  startDate?: string;
  start_date?: string;
  endDate?: string;
  end_date?: string;
  applyDeadline?: string;
  end_app_date?: string;
  leader?: number | string;
  organizer?: number | string;
  organizerIds?: Array<number | string>;
  organizerName?: string;
  archived?: boolean;
  is_archived?: boolean;
  orgChatUrl?: string;
  org_chat_url?: string;
  orgChatPeerId?: number | string;
  org_chat_peer_id?: number | string;
  stage?: string;
  specializations?: unknown[];
  specialization?: number | string;
  specializationId?: number | string;
  applicationFormFields?: ApplicationFormField[];
  application_form_fields?: ApplicationFormField[];
};

type BackendEventPayload = {
  name?: string;
  description: string;
  start_date?: string;
  end_date?: string;
  end_app_date?: string;
  stage: string;
  leader?: number;
  organizerIds?: number[];
  orgChatUrl?: string;
  orgChatPeerId?: number;
  specialization?: number;
  specializations?: number[];
  applicationFormFields?: ApplicationFormField[];
  is_archived?: boolean;
};

let specializationCache: BackendSpecialization[] | null = null;

function readEventExtensions(): Record<string, Partial<Event>> {
  const raw = localStorage.getItem(LS_EVENT_EXTENSIONS);
  if (!raw) return {};

  try {
    return JSON.parse(raw) as Record<string, Partial<Event>>;
  } catch {
    return {};
  }
}

function getEventExtension(id: number): Partial<Event> {
  return readEventExtensions()[String(id)] ?? {};
}

function writeEventExtension(id: number, patch: Partial<Event>) {
  if (!Number.isFinite(id) || id <= 0) return;

  const current = readEventExtensions();
  current[String(id)] = {
    ...(current[String(id)] ?? {}),
    ...patch,
  };
  localStorage.setItem(LS_EVENT_EXTENSIONS, JSON.stringify(current));
}

function replaceEventExtension(id: number, patch: Partial<Event>) {
  if (!Number.isFinite(id) || id <= 0) return;

  const current = readEventExtensions();
  current[String(id)] = { ...patch };
  localStorage.setItem(LS_EVENT_EXTENSIONS, JSON.stringify(current));
}

function asRecord(value: unknown): UnknownRecord {
  return value && typeof value === "object" ? (value as UnknownRecord) : {};
}

function toStringValue(value: unknown): string | undefined {
  if (typeof value === "string") return value;
  if (typeof value === "number") return String(value);
  return undefined;
}

function toNumber(value: unknown): number | undefined {
  if (typeof value === "number" && !Number.isNaN(value)) return value;
  if (typeof value === "string") {
    const n = Number(value);
    if (!Number.isNaN(n)) return n;
  }
  return undefined;
}

function getSpecName(spec: BackendSpecialization): string {
  return String(spec.name ?? spec.title ?? "").trim();
}

function computeStatus(endDate?: string) {
  if (!endDate) return "Неактивно";
  const end = new Date(endDate);
  return end >= new Date() ? "Активно" : "Неактивно";
}

function normalizeIdList(value: unknown): Array<number | string> | undefined {
  if (!Array.isArray(value)) return undefined;

  const ids = value
    .map((item) => {
      if (typeof item === "number" || typeof item === "string") return item;
      return asRecord(item).id;
    })
    .filter((item): item is number | string => typeof item === "number" || typeof item === "string");

  return ids.length ? ids : undefined;
}

function normalizeFormFields(value: unknown): ApplicationFormField[] | undefined {
  if (!Array.isArray(value)) return undefined;

  return value
    .map((item) => {
      const field = asRecord(item);
      const id = toStringValue(field.id)?.trim();
      const label = toStringValue(field.label)?.trim();
      if (!id || !label) return null;
      const type = field.type === "textarea" || field.type === "select" ? field.type : "text";
      const options = Array.isArray(field.options)
        ? field.options.map((option) => String(option).trim()).filter(Boolean)
        : undefined;

      return {
        id,
        label,
        type,
        options: type === "select" && options?.length ? options : undefined,
        required: Boolean(field.required),
        locked: Boolean(field.locked),
        system: Boolean(field.system),
      } satisfies ApplicationFormField;
    })
    .filter(Boolean) as ApplicationFormField[];
}

function normalizeBackendEvent(data: unknown): BackendEvent {
  const obj = asRecord(data);
  const applicationFields = normalizeFormFields(obj.applicationFormFields ?? obj.application_form_fields);

  return {
    id: typeof obj.id === "number" || typeof obj.id === "string" ? obj.id : undefined,
    title: toStringValue(obj.title),
    name: toStringValue(obj.name),
    description: toStringValue(obj.description),
    startDate: toStringValue(obj.startDate),
    start_date: toStringValue(obj.start_date),
    endDate: toStringValue(obj.endDate),
    end_date: toStringValue(obj.end_date),
    applyDeadline: toStringValue(obj.applyDeadline),
    end_app_date: toStringValue(obj.end_app_date),
    leader: typeof obj.leader === "number" || typeof obj.leader === "string" ? obj.leader : undefined,
    organizer: typeof obj.organizer === "number" || typeof obj.organizer === "string" ? obj.organizer : undefined,
    organizerIds: normalizeIdList(obj.organizerIds ?? obj.organizers ?? obj.organizer_ids),
    organizerName: toStringValue(obj.organizerName ?? obj.organizer_name),
    archived: Boolean(obj.archived),
    is_archived: Boolean(obj.is_archived),
    orgChatUrl: toStringValue(obj.orgChatUrl),
    org_chat_url: toStringValue(obj.org_chat_url),
    orgChatPeerId:
      typeof obj.orgChatPeerId === "number" || typeof obj.orgChatPeerId === "string" ? obj.orgChatPeerId : undefined,
    org_chat_peer_id:
      typeof obj.org_chat_peer_id === "number" || typeof obj.org_chat_peer_id === "string" ? obj.org_chat_peer_id : undefined,
    stage: toStringValue(obj.stage),
    specializations: Array.isArray(obj.specializations) ? obj.specializations : undefined,
    specialization:
      typeof obj.specialization === "number" || typeof obj.specialization === "string" ? obj.specialization : undefined,
    specializationId:
      typeof obj.specializationId === "number" || typeof obj.specializationId === "string" ? obj.specializationId : undefined,
    applicationFormFields: applicationFields,
    application_form_fields: applicationFields,
  };
}

function normalizeSpecList(data: BackendEvent, specs: BackendSpecialization[]): Array<{ id: number; title: string }> {
  if (Array.isArray(data.specializations) && data.specializations.length > 0) {
    return data.specializations
      .map((item) => {
        if (typeof item === "number" || typeof item === "string") {
          const idFromPrimitive = toNumber(item);
          if (typeof idFromPrimitive === "undefined") return null;
          const fromCache = specs.find((x) => x.id === idFromPrimitive);
          return {
            id: idFromPrimitive,
            title: (fromCache ? getSpecName(fromCache) : "") || String(idFromPrimitive),
          };
        }

        const specObj = asRecord(item);
        const id = toNumber(specObj.id ?? specObj.specializationId);
        if (typeof id === "undefined") return null;
        const title = toStringValue(specObj.title ?? specObj.name);
        const fromCache = specs.find((x) => x.id === id);
        return { id, title: title ? String(title) : (fromCache ? getSpecName(fromCache) : "") || String(id) };
      })
      .filter(Boolean) as Array<{ id: number; title: string }>;
  }

  const specId = toNumber(data.specialization ?? data.specializationId);
  if (typeof specId !== "undefined") {
    const found = specs.find((x) => Number(x.id) === Number(specId));
    return [{ id: specId, title: (found ? getSpecName(found) : "") || String(specId) }];
  }

  return [];
}

async function getSpecializations(): Promise<BackendSpecialization[]> {
  if (USE_MOCK) return [];
  if (specializationCache) return specializationCache;

  try {
    const raw = await client.get("/api/users/specializations/");
    const list = Array.isArray(raw) ? raw : [];
    specializationCache = list
      .map((item) => {
        const spec = asRecord(item);
        return {
          id: Number(spec.id),
          name: String(spec.name ?? spec.title ?? "").trim(),
          title: String(spec.title ?? spec.name ?? "").trim(),
          description: spec.description ? String(spec.description) : undefined,
        };
      })
      .filter((spec: BackendSpecialization) => Number.isFinite(spec.id) && getSpecName(spec));
    return specializationCache;
  } catch {
    specializationCache = [];
    return specializationCache;
  }
}

function extractUserDisplay(user: User): string {
  const obj = user as User & UnknownRecord;
  const name = user.name ?? toStringValue(obj.firstName ?? obj.first_name) ?? "";
  const surname = user.surname ?? toStringValue(obj.lastName ?? obj.last_name) ?? "";
  return `${surname} ${name}`.trim();
}

async function resolveOrganizer(event: BackendEvent): Promise<string | undefined> {
  if (event.organizerName && event.organizerName.trim()) return event.organizerName.trim();

  let organizerIds = event.organizerIds;
  const directOrganizer = event.organizer ?? event.leader;
  if (typeof directOrganizer === "string" && directOrganizer.trim() && Number.isNaN(Number(directOrganizer))) {
    return directOrganizer.trim();
  }
  let id: number | string | undefined = organizerIds?.[0] ?? event.leader ?? event.organizer;

  if (typeof id === "undefined" && typeof event.id !== "undefined") {
    try {
      const dirs = await getStoredDirectionsByEvent(Number(event.id));
      if (Array.isArray(dirs) && dirs.length > 0) id = dirs[0].leader ?? dirs[0].organizer;
    } catch {
    }
  }

  if (!organizerIds?.length && typeof id !== "undefined") organizerIds = [id];
  if (!organizerIds?.length) return undefined;

  try {
    const users = await getAllUsers();
    return organizerIds
      .map((organizerId) => {
        const user = users.find((item) => String(item.id) === String(organizerId));
        return user ? extractUserDisplay(user) || "Организатор" : "Организатор";
      })
      .filter(Boolean)
      .join(", ");
  } catch {
    return "Организатор";
  }
}

async function mapEventToUi(data: unknown): Promise<Event> {
  const event = normalizeBackendEvent(data);
  const specs = await getSpecializations();
  const plannerState = readPlannerState(USE_MOCK);
  const archivedIds = USE_MOCK ? new Set(getArchivedEventIds()) : new Set<number>();
  const eventId = Number(event.id ?? 0);
  const isArchived = event.archived || event.is_archived || archivedIds.has(eventId);
  const isEnrollmentClosed = plannerState.closedEventIds.includes(eventId);
  const organizerIds = event.organizerIds?.length
    ? event.organizerIds
    : typeof event.leader !== "undefined"
      ? [event.leader]
      : typeof event.organizer !== "undefined"
        ? [event.organizer]
        : undefined;

  const baseEvent: Event = {
    id: eventId,
    title: event.title ?? event.name ?? "",
    description: event.description ?? "",
    startDate: event.startDate ?? event.start_date,
    endDate: event.endDate ?? event.end_date,
    applyDeadline: event.applyDeadline ?? event.end_app_date,
    leader: organizerIds?.[0] != null ? String(organizerIds[0]) : undefined,
    organizerIds,
    specializations: normalizeSpecList(event, specs),
    status: isArchived ? "В архиве" : isEnrollmentClosed ? "Набор завершен" : computeStatus(event.endDate ?? event.end_date),
    organizer: await resolveOrganizer({ ...event, organizerIds }),
    archived: isArchived,
    orgChatUrl: event.orgChatUrl ?? event.org_chat_url,
    orgChatPeerId: event.orgChatPeerId ?? event.org_chat_peer_id,
    applicationFormFields: event.applicationFormFields ?? event.application_form_fields,
  };

  const extension = USE_MOCK ? getEventExtension(eventId) : {};

  return {
    ...baseEvent,
    ...extension,
    id: eventId,
    archived: baseEvent.archived || extension.archived,
    status: baseEvent.archived || extension.archived ? "В архиве" : extension.status ?? baseEvent.status,
    organizerIds: extension.organizerIds ?? baseEvent.organizerIds,
    organizer: extension.organizer ?? baseEvent.organizer,
    orgChatUrl: extension.orgChatUrl ?? baseEvent.orgChatUrl,
    orgChatPeerId: extension.orgChatPeerId ?? baseEvent.orgChatPeerId,
    applicationFormFields: extension.applicationFormFields ?? baseEvent.applicationFormFields,
  };
}

export async function getEvents(): Promise<Event[]> {
  const raw = USE_MOCK ? await getStoredEvents() : await client.get("/api/users/events/");
  const list = Array.isArray(raw) ? raw : [];
  const events = await Promise.all(list.map((event) => mapEventToUi(event)));
  const archivedIds = USE_MOCK ? new Set(getArchivedEventIds()) : new Set<number>();

  return events.filter((event) => !event.archived && !archivedIds.has(Number(event.id)));
}

export async function getArchivedEvents(): Promise<Event[]> {
  if (USE_MOCK) {
    const raw = await getStoredArchivedEvents();
    return Promise.all(raw.map((event) => mapEventToUi(event)));
  }

  try {
    const raw = await client.get("/api/users/events/?archived=true");
    const list = Array.isArray(raw) ? raw : [];
    return Promise.all(list.map((event) => mapEventToUi(event)));
  } catch {
    const archivedIds = getArchivedEventIds();
    const cached: Array<Partial<Event> & { id: number; archived: true }> = archivedIds
      .map((id): (Partial<Event> & { id: number; archived: true }) | null => {
        const extension = getEventExtension(Number(id));
        return extension.id || extension.title ? { ...extension, id: Number(id), archived: true } : null;
      })
      .filter((event): event is Partial<Event> & { id: number; archived: true } => Boolean(event));
    return Promise.all(cached.map((event) => mapEventToUi(event)));
  }
}

export async function getEventById(id: number): Promise<Event | undefined> {
  const data = USE_MOCK ? await getStoredEventById(id) : await client.get(`/api/users/events/${id}/`);
  if (!data) return undefined;
  return mapEventToUi(data);
}

const fmtEndApp = (value?: string) => {
  if (!value) return undefined;
  if (value.includes("T")) return value;
  return new Date(`${value}T23:59:59`).toISOString();
};

async function resolveSpecializationIds(data: Event): Promise<number[]> {
  const items = Array.isArray(data.specializations) ? data.specializations : [];
  if (items.length === 0) return [];

  if (USE_MOCK) {
    return Array.from(
      new Set(items.map((item) => toNumber(item.id)).filter((id): id is number => typeof id === "number"))
    );
  }

  const specs = await getSpecializations();
  const unresolved: string[] = [];
  const ids = await Promise.all(
    items.map(async (item) => {
      const directId = toNumber(item.id);
      if (typeof directId !== "undefined" && specs.some((spec) => spec.id === directId)) return directId;

      const title = String(item.title ?? "").trim();
      if (!title) {
        if (typeof directId !== "undefined") unresolved.push(String(directId));
        return undefined;
      }

      const found = specs.find((spec) => getSpecName(spec).toLowerCase() === title.toLowerCase());
      if (found) return found.id;

      unresolved.push(title);
      return undefined;
    })
  );

  const resolvedIds = Array.from(new Set(ids.filter((id): id is number => typeof id === "number")));

  if (resolvedIds.length === 0) {
    throw new Error("На сервере не найдены выбранные специализации. Выберите значения из выпадающего списка.");
  }

  if (unresolved.length > 0) {
    throw new Error(
      `Не удалось сопоставить специализации: ${unresolved.join(", ")}. Обновите страницу и выберите их заново.`
    );
  }

  return resolvedIds;
}

async function toBackendEvent(data: Event): Promise<BackendEventPayload> {
  const obj = data as Event & UnknownRecord;
  const stageValue = toStringValue(obj.stage);
  const payload: BackendEventPayload = {
    name: data.title,
    description: data.description ?? "",
    start_date: data.startDate,
    end_date: data.endDate,
    end_app_date: fmtEndApp(data.applyDeadline),
    stage: stageValue && stageValue.trim() ? stageValue : "-",
  };

  const leaderId = toNumber(data.organizerIds?.[0] ?? data.leader);
  if (typeof leaderId !== "undefined") payload.leader = leaderId;

  const organizerIds = (data.organizerIds ?? [])
    .map((id) => toNumber(id))
    .filter((id): id is number => typeof id === "number");
  if (organizerIds.length > 0) payload.organizerIds = organizerIds;
  if (typeof data.orgChatUrl === "string") payload.orgChatUrl = data.orgChatUrl.trim();
  const orgChatPeerId = toNumber(data.orgChatPeerId);
  if (typeof orgChatPeerId !== "undefined") payload.orgChatPeerId = orgChatPeerId;
  if (data.applicationFormFields) payload.applicationFormFields = data.applicationFormFields;

  const specializationIds = await resolveSpecializationIds(data);
  if (specializationIds.length > 0) {
    payload.specializations = specializationIds;
    payload.specialization = specializationIds[0];
  }

  return payload;
}

export async function saveEvent(data: Event): Promise<Event> {
  if (USE_MOCK) return saveStoredEvent({ ...data });

  const payload = await toBackendEvent(data);
  const saved = data.id
    ? await client.put(`/api/users/events/${data.id}/`, payload)
    : await client.post("/api/users/events/", payload);
  const mapped = await mapEventToUi(saved);
  const extension: Partial<Event> = {
    organizerIds: data.organizerIds ?? mapped.organizerIds,
    organizer: data.organizer ?? mapped.organizer,
    orgChatUrl: data.orgChatUrl ?? mapped.orgChatUrl,
    orgChatPeerId: data.orgChatPeerId ?? mapped.orgChatPeerId,
    applicationFormFields: data.applicationFormFields ?? mapped.applicationFormFields,
    archived: false,
    archivedAt: undefined,
  };
  forgetArchivedEventId(Number(mapped.id));
  replaceEventExtension(Number(mapped.id), extension);

  return {
    ...mapped,
    ...extension,
  };
}

export async function archiveEvent(id: number): Promise<unknown> {
  if (USE_MOCK) return archiveStoredEvent(id);

  const snapshot = await getEventById(Number(id)).catch(() => undefined);
  rememberArchivedEventId(id);
  writeEventExtension(Number(id), { ...(snapshot ?? {}), archived: true, archivedAt: new Date().toISOString() });

  try {
    return await client.patch(`/api/users/events/${id}/`, { archived: true, is_archived: true });
  } catch {
    return { ok: true };
  }
}

export async function removeEvent(id: number): Promise<unknown> {
  return archiveEvent(id);
}

export async function restoreEvent(id: number): Promise<Event | undefined> {
  const eventId = Number(id);

  if (USE_MOCK) {
    const restored = await restoreStoredEvent(eventId);
    return restored ? mapEventToUi(restored) : undefined;
  }

  writeEventExtension(eventId, { archived: false, archivedAt: undefined });
  forgetArchivedEventId(eventId);

  try {
    const restored = await client.patch(`/api/users/events/${eventId}/`, { archived: false, is_archived: false });
    return mapEventToUi(restored);
  } catch {
    const extension = getEventExtension(eventId);
    return mapEventToUi({ ...extension, id: eventId, archived: false, archivedAt: undefined });
  }
}
