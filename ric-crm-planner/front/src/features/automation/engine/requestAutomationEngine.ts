import { readAutomationConfig } from "../storage/automationStorage";
import { updateRequestStatus as updateStoredRequestStatus } from "../../requests/storage/requests";
import { getEventById } from "../../../storage/storage";
import type { Event } from "../../../types/event";
import type { Request as ReqType } from "../../../types/request";
import type { AutomationConfig, AutomationScope, AutomationTrigger } from "../types";
import { conditionsMatch } from "./conditionEvaluator";
import { executeRobot } from "./robotExecutor";
import type { RequestAutomationEvent } from "./requestAutomationTypes";
import { getStageStatus, getStatusStageId, isBackTransition } from "./stageResolver";

const REQUEST_AUTOMATION_SCOPES: AutomationScope[] = ["crm"];

async function getRequestEvent(request: ReqType) {
  if (!request.eventId) return undefined;
  return getEventById(Number(request.eventId)).catch(() => undefined);
}

async function runRobotsForStage(
  config: AutomationConfig,
  stageId: string,
  eventItem: RequestAutomationEvent<ReqType>,
  event?: Event
) {
  const robots = config.robots.filter(
    (robot) =>
      robot.enabled &&
      !robot.deleted &&
      robot.stageId === stageId &&
      conditionsMatch(robot.settings, eventItem.request, config, event)
  );

  for (const robot of robots) {
    await executeRobot(config, robot, eventItem, event);
  }
}

async function applyTrigger(
  config: AutomationConfig,
  trigger: AutomationTrigger,
  eventItem: RequestAutomationEvent<ReqType>,
  event?: Event
) {
  if (trigger.eventCode !== eventItem.code) return undefined;
  if (!conditionsMatch(trigger.settings, eventItem.request, config, event)) return undefined;
  if (!trigger.allowBackTransition && isBackTransition(config, eventItem.request.status, trigger.targetStageId)) return undefined;

  const targetStatus = getStageStatus(config, trigger.targetStageId);
  if (targetStatus && targetStatus !== eventItem.request.status) {
    const updated = await updateStoredRequestStatus(eventItem.request.id, targetStatus);
    if (updated) eventItem.request = updated;
  }

  return trigger.targetStageId;
}

async function runConfigAutomation(config: AutomationConfig, eventItem: RequestAutomationEvent<ReqType>) {
  const event = await getRequestEvent(eventItem.request);
  const enteredStageIds = new Set<string>();

  for (const trigger of config.triggers) {
    if (!trigger.enabled || trigger.deleted) continue;
    const stageId = await applyTrigger(config, trigger, eventItem, event);
    if (!stageId) continue;
    enteredStageIds.add(stageId);
  }

  const currentStageId = getStatusStageId(config, eventItem.request.status);
  if (currentStageId) enteredStageIds.add(currentStageId);

  for (const stageId of enteredStageIds) {
    await runRobotsForStage(config, stageId, eventItem, event);
  }
}

export async function runRequestAutomation(eventItem: RequestAutomationEvent<ReqType>) {
  if (!eventItem.request.eventId) return eventItem.request;

  const eventId = Number(eventItem.request.eventId);
  if (!Number.isFinite(eventId)) return eventItem.request;

  for (const scope of REQUEST_AUTOMATION_SCOPES) {
    const config = readAutomationConfig(scope, eventId);
    await runConfigAutomation(config, { ...eventItem, request: { ...eventItem.request } });
  }

  return eventItem.request;
}

async function runConfigStageRobots(config: AutomationConfig, eventItem: RequestAutomationEvent<ReqType>) {
  const event = await getRequestEvent(eventItem.request);
  const currentStageId = getStatusStageId(config, eventItem.request.status);
  if (!currentStageId) return;

  await runRobotsForStage(config, currentStageId, eventItem, event);
}

export async function runRequestStageRobots(eventItem: RequestAutomationEvent<ReqType>) {
  if (!eventItem.request.eventId) return eventItem.request;

  const eventId = Number(eventItem.request.eventId);
  if (!Number.isFinite(eventId)) return eventItem.request;

  for (const scope of REQUEST_AUTOMATION_SCOPES) {
    const config = readAutomationConfig(scope, eventId);
    await runConfigStageRobots(config, { ...eventItem, request: { ...eventItem.request } });
  }

  return eventItem.request;
}

export async function runRequestAutomationEvents(events: Array<RequestAutomationEvent<ReqType>>) {
  for (const eventItem of events) {
    await runRequestAutomation(eventItem);
  }
}
