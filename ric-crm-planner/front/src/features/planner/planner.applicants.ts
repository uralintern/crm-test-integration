import { REQUEST_STATUS, isNegativeRequestStatus } from "../../constants/requestProgress";
import type { Request } from "../../types/request";
import type { ApplicantsTreeNode, ProjectApplicantsGroup } from "./planner.types";
import type { PlannerCatalogEvent } from "./planner.catalog";

type ApplicantAccumulator = {
  ownerId: number;
  name: string;
  status?: string;
  specialization?: string;
  desiredDirections: Map<string, { id?: number; title: string }>;
  requestIds: number[];
  latestRequestId: number;
};

type BuildProjectApplicantGroupsParams = {
  crmCatalog: PlannerCatalogEvent[];
  requests: Request[];
  closedEventIds: number[];
  userNameById: Map<number, string>;
  eventTitleById: Record<number, string>;
  directionTitleById: Record<number, string>;
};

function getApplicantName(request: Request, userNameById: Map<number, string>, ownerId: number) {
  return request.studentName || userNameById.get(ownerId) || `Участник #${ownerId}`;
}

function getDesiredDirection(request: Request, directionTitleById: Record<number, string>) {
  const directionId = Number(request.directionId);
  const hasDirection = Number.isFinite(directionId) && directionId > 0;
  const directionTitle =
    (hasDirection ? directionTitleById[directionId] : "") ||
    String(request.directionTitle || "").trim() ||
    (hasDirection ? `Направление #${directionId}` : "");

  if (!directionTitle) return null;
  return {
    key: hasDirection ? String(directionId) : directionTitle.toLowerCase(),
    value: {
      id: hasDirection ? directionId : undefined,
      title: directionTitle,
    },
  };
}

function upsertApplicant(
  applicantsByOwner: Map<number, ApplicantAccumulator>,
  ownerId: number,
  displayName: string,
  request: Request,
  directionTitleById: Record<number, string>
) {
  if (!applicantsByOwner.has(ownerId)) {
    applicantsByOwner.set(ownerId, {
      ownerId,
      name: displayName,
      status: request.status,
      specialization: request.specialization,
      desiredDirections: new Map(),
      requestIds: [request.id],
      latestRequestId: Number(request.id) || 0,
    });
  } else {
    const current = applicantsByOwner.get(ownerId);
    if (!current) return;
    if (!current.requestIds.includes(request.id)) current.requestIds.push(request.id);
    if ((Number(request.id) || 0) >= current.latestRequestId) {
      current.latestRequestId = Number(request.id) || current.latestRequestId;
      current.status = request.status;
      current.specialization = request.specialization || current.specialization;
      if (displayName) current.name = displayName;
    }
  }

  const current = applicantsByOwner.get(ownerId);
  const desiredDirection = getDesiredDirection(request, directionTitleById);
  if (current && desiredDirection) {
    current.desiredDirections.set(desiredDirection.key, desiredDirection.value);
  }
}

function mapApplicants(applicantsByOwner: Map<number, ApplicantAccumulator>) {
  return Array.from(applicantsByOwner.values())
    .map((applicant) => ({
      ownerId: applicant.ownerId,
      name: applicant.name,
      status: applicant.status,
      specialization: applicant.specialization,
      desiredDirections: Array.from(applicant.desiredDirections.values()).sort((a, b) => a.title.localeCompare(b.title, "ru")),
      requestIds: applicant.requestIds,
    }))
    .sort((a, b) => a.name.localeCompare(b.name, "ru"));
}

function hasPlannerAccessStatus(status?: string) {
  const normalizedStatus = String(status || "").trim().toLowerCase();
  if (isNegativeRequestStatus(status)) return false;
  return (
    normalizedStatus === REQUEST_STATUS.STARTED.toLowerCase() ||
    normalizedStatus === REQUEST_STATUS.JOINED_CHAT.toLowerCase()
  );
}

export function buildProjectApplicantGroups({
  crmCatalog,
  requests,
  closedEventIds,
  userNameById,
  eventTitleById,
  directionTitleById,
}: BuildProjectApplicantGroupsParams): ProjectApplicantsGroup[] {
  const applicantsByEvent = new Map<number, Map<number, ApplicantAccumulator>>();

  requests.forEach((request) => {
    const eventId = Number(request.eventId);
    const ownerId = Number(request.ownerId);
    if (!Number.isFinite(eventId) || !Number.isFinite(ownerId)) return;
    if (isNegativeRequestStatus(request.status)) return;
    if (closedEventIds.includes(eventId) && !hasPlannerAccessStatus(request.status)) return;

    if (!applicantsByEvent.has(eventId)) applicantsByEvent.set(eventId, new Map());
    const eventApplicants = applicantsByEvent.get(eventId);
    if (!eventApplicants) return;

    upsertApplicant(eventApplicants, ownerId, getApplicantName(request, userNameById, ownerId), request, directionTitleById);
  });

  const catalogGroups = crmCatalog.map((event): ProjectApplicantsGroup => ({
    key: `event:${event.id}`,
    eventId: event.id,
    eventTitle: event.title,
    directionOptions: event.directions,
    applicants: mapApplicants(applicantsByEvent.get(Number(event.id)) ?? new Map()),
  }));

  const catalogEventIds = new Set(crmCatalog.map((event) => Number(event.id)));
  const fallbackGroups = Array.from(applicantsByEvent.entries())
    .filter(([eventId]) => !catalogEventIds.has(Number(eventId)))
    .map(([eventId, applicantsByOwner]): ProjectApplicantsGroup => ({
      key: `event:${eventId}`,
      eventId,
      eventTitle: eventTitleById[eventId] || `Мероприятие #${eventId}`,
      directionOptions: [],
      applicants: mapApplicants(applicantsByOwner),
    }));

  return [...catalogGroups, ...fallbackGroups].sort((a, b) => a.eventTitle.localeCompare(b.eventTitle, "ru"));
}

export function buildApplicantsTree(
  projectApplicantGroups: ProjectApplicantsGroup[],
  closedEventIds: number[],
  hiddenEventIdSet: Set<number>
): ApplicantsTreeNode[] {
  return projectApplicantGroups.map((group) => {
    const eventId = typeof group.eventId === "number" ? group.eventId : undefined;
    return {
      key: group.key,
      eventId,
      eventClosed: typeof eventId === "number" ? closedEventIds.includes(eventId) : false,
      eventHidden: typeof eventId === "number" ? hiddenEventIdSet.has(eventId) : false,
      title: group.eventTitle,
      group,
    };
  });
}
