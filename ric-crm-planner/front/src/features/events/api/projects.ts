import client from "../../../api/client";
import {
  getAllUsers,
  getProjectsByDirection as _getProjectsByDirection,
  saveProjectsForDirection as _saveProjectsForDirection,
} from "../../../storage/storage";
import type { Project } from "../../../types/project";

const USE_MOCK = client.USE_MOCK;

type BackendUser = {
  id?: number | string;
  name?: string;
  firstName?: string;
  first_name?: string;
  surname?: string;
  lastName?: string;
  last_name?: string;
};

type BackendProject = {
  id?: number | string;
  title?: string;
  name?: string;
  description?: string;
  teams?: number | string | null;
  directionId?: number | string;
  direction?: number | string;
  curatorId?: number | string;
  curator?: number | string | null;
  curatorName?: string;
};

function isTempId(id: unknown) {
  if (id == null) return false;
  const n = Number(id);
  if (Number.isNaN(n)) return true;
  return String(n).length >= 12 || n > 1e11;
}

function toNumber(value: unknown): number | undefined {
  if (typeof value === "number" && !Number.isNaN(value)) return value;
  if (typeof value === "string") {
    const n = Number(value);
    if (!Number.isNaN(n)) return n;
  }
  return undefined;
}

function displayName(user: BackendUser): string {
  return `${user?.surname ?? user?.lastName ?? user?.last_name ?? ""} ${user?.name ?? user?.firstName ?? user?.first_name ?? ""}`.trim();
}

async function getUserMaps() {
  const users = (await getAllUsers().catch(() => [])) as BackendUser[];
  const userNameById = new Map<number, string>();

  users.forEach((u) => {
    const id = Number(u.id);
    const name = displayName(u);
    if (!Number.isNaN(id)) userNameById.set(id, name || String(id));
  });

  return { userNameById };
}

function mapBackendProject(item: BackendProject, userNameById: Map<number, string>): Project {
  const curatorId = toNumber(item.curatorId ?? item.curator);
  return {
    id: Number(item.id ?? 0),
    title: item.title ?? item.name ?? "",
    description: item.description ?? "",
    teams: typeof item.teams === "number" ? item.teams : toNumber(item.teams),
    directionId: toNumber(item.directionId ?? item.direction),
    curatorId,
    curator:
      (typeof curatorId !== "undefined" ? userNameById.get(curatorId) : undefined) ??
      (item.curatorName ? String(item.curatorName) : undefined) ??
      (item.curator != null ? String(item.curator) : undefined),
  };
}

export async function getProjectsByDirection(directionId: number): Promise<Project[]> {
  if (USE_MOCK) return _getProjectsByDirection(directionId);

  const { userNameById } = await getUserMaps();
  const raw = (await client.get("/api/users/projects/")) as unknown;
  const list = (Array.isArray(raw) ? raw : []) as BackendProject[];

  return list
    .filter((x) => Number(x.directionId ?? x.direction) === Number(directionId))
    .map((x) => mapBackendProject(x, userNameById));
}

export async function updateProjectCurator(projectId: number, curatorId: number): Promise<Project | null> {
  if (USE_MOCK || !projectId || !curatorId) return null;

  const { userNameById } = await getUserMaps();
  const updated = await client.patch<BackendProject>(`/api/users/projects/${projectId}/`, { curator: curatorId });
  return mapBackendProject(updated, userNameById);
}

export async function saveProjectsForDirection(directionId: number, projects: Project[]) {
  if (USE_MOCK) return _saveProjectsForDirection(directionId, projects);

  const { userNameById } = await getUserMaps();
  const existing = await getProjectsByDirection(directionId).catch(() => []);
  const keepIds = new Set(
    projects
      .map((project) => project.id)
      .filter((id): id is number => typeof id === "number" && !isTempId(id))
      .map((id) => Number(id))
  );
  await Promise.all(
    existing
      .filter((project) => project.id && !keepIds.has(Number(project.id)))
      .map((project) => client.del(`/api/users/projects/${project.id}/`).catch(() => null))
  );

  const results: Project[] = [];

  for (const p of projects) {
    const payload: Record<string, unknown> = {
      name: p.title ?? "",
      description: p.description ?? "",
    };

    if (p.id && !isTempId(p.id)) {
      const updated = await client.put<BackendProject>(`/api/users/projects/${p.id}/`, payload);
      results.push(mapBackendProject(updated, userNameById));
    } else {
      const created = await client.post<BackendProject>("/api/users/projects/", {
        ...payload,
        direction_id: directionId,
      });
      results.push(mapBackendProject(created, userNameById));
    }
  }

  return results;
}

