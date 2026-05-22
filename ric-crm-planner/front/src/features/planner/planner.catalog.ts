import { getEventById, getEvents } from "../events/api/events";
import { getDirectionById, getDirectionsByEvent } from "../events/api/directions";
import { getProjectsByDirection } from "../events/api/projects";
import type { Request } from "../../types/request";

export type PlannerCatalogProject = {
  id: number;
  title: string;
};

export type PlannerCatalogDirection = {
  id: number;
  title: string;
  projects: PlannerCatalogProject[];
};

export type PlannerCatalogEvent = {
  id: number;
  title: string;
  directions: PlannerCatalogDirection[];
};

export type PlannerTitleMaps = {
  eventTitleById: Record<number, string>;
  directionTitleById: Record<number, string>;
  projectTitleById: Record<number, string>;
};

export async function loadPlannerCrmCatalog(): Promise<PlannerCatalogEvent[]> {
  const events = await getEvents().catch(() => []);

  return Promise.all(
    (events || []).map(async (event) => {
      const directions = await getDirectionsByEvent(Number(event.id)).catch(() => []);
      const mappedDirections = await Promise.all(
        (directions || []).map(async (direction) => {
          const projects = await getProjectsByDirection(Number(direction.id)).catch(() => []);
          return {
            id: Number(direction.id),
            title: String(direction.title || "").trim() || `Направление #${direction.id}`,
            projects: (projects || []).map((project) => ({
              id: Number(project.id),
              title: String(project.title || "").trim() || `Проект #${project.id}`,
            })),
          };
        })
      );

      return {
        id: Number(event.id),
        title: String(event.title || "").trim() || `Мероприятие #${event.id}`,
        directions: mappedDirections,
      } satisfies PlannerCatalogEvent;
    })
  );
}

export function getPlannerTitleMapsFromCatalog(catalog: PlannerCatalogEvent[]): PlannerTitleMaps {
  return {
    eventTitleById: Object.fromEntries(catalog.map((event) => [event.id, event.title])),
    directionTitleById: Object.fromEntries(
      catalog.flatMap((event) => event.directions.map((direction) => [direction.id, direction.title]))
    ),
    projectTitleById: Object.fromEntries(
      catalog.flatMap((event) =>
        event.directions.flatMap((direction) => direction.projects.map((project) => [project.id, project.title]))
      )
    ),
  };
}

export async function loadMissingPlannerTitles(requests: Request[]): Promise<PlannerTitleMaps> {
  const nextEventTitles: Record<number, string> = {};
  const nextDirectionTitles: Record<number, string> = {};
  const nextProjectTitles: Record<number, string> = {};

  requests.forEach((request) => {
    const eventId = Number(request.eventId);
    const projectId = Number(request.projectId);
    if (Number.isFinite(eventId) && request.eventTitle?.trim()) nextEventTitles[eventId] = request.eventTitle.trim();
    if (Number.isFinite(projectId) && request.projectTitle?.trim()) nextProjectTitles[projectId] = request.projectTitle.trim();
  });

  const missingEventIds = Array.from(
    new Set(
      requests
        .map((request) => Number(request.eventId))
        .filter((id) => Number.isFinite(id) && !nextEventTitles[id])
    )
  );
  const missingDirectionIds = Array.from(
    new Set(
      requests
        .map((request) => Number(request.directionId))
        .filter((id) => Number.isFinite(id) && !nextDirectionTitles[id])
    )
  );

  const projectIdsByDirection = new Map<number, Set<number>>();
  requests.forEach((request) => {
    const directionId = Number(request.directionId);
    const projectId = Number(request.projectId);
    if (!Number.isFinite(directionId) || !Number.isFinite(projectId)) return;
    if (!projectIdsByDirection.has(directionId)) projectIdsByDirection.set(directionId, new Set<number>());
    projectIdsByDirection.get(directionId)?.add(projectId);
  });

  const missingProjectByDirection = Array.from(projectIdsByDirection.entries())
    .map(([directionId, projectIds]) => ({
      directionId,
      projectIds: Array.from(projectIds).filter((projectId) => !nextProjectTitles[projectId]),
    }))
    .filter((item) => item.projectIds.length > 0);

  if (missingEventIds.length > 0) {
    const events = await Promise.all(missingEventIds.map((id) => getEventById(id).catch(() => undefined)));
    events.forEach((event, index) => {
      const id = missingEventIds[index];
      const title = event?.title?.trim();
      if (title) nextEventTitles[id] = title;
    });
  }

  if (missingDirectionIds.length > 0) {
    const directions = await Promise.all(missingDirectionIds.map((id) => getDirectionById(id).catch(() => undefined)));
    directions.forEach((direction, index) => {
      const id = missingDirectionIds[index];
      const title = direction?.title?.trim();
      if (title) nextDirectionTitles[id] = title;
    });
  }

  if (missingProjectByDirection.length > 0) {
    const lists = await Promise.all(
      missingProjectByDirection.map(async ({ directionId, projectIds }) => {
        const projects = await getProjectsByDirection(directionId).catch(() => []);
        const filtered = Array.isArray(projects) ? projects.filter((project) => projectIds.includes(Number(project.id))) : [];
        return filtered
          .map((project) => ({ id: Number(project.id), title: String(project.title || "").trim() }))
          .filter((project) => project.id && project.title);
      })
    );
    lists.flat().forEach((project) => {
      nextProjectTitles[project.id] = project.title;
    });
  }

  return {
    eventTitleById: nextEventTitles,
    directionTitleById: nextDirectionTitles,
    projectTitleById: nextProjectTitles,
  };
}
