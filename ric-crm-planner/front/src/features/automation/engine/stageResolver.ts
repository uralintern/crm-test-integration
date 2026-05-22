import { REQUEST_STATUS } from "../../../constants/requestProgress";
import type { AutomationConfig } from "../types";

const REQUEST_STAGE_IDS = [
  "application-submitted",
  "application-testing",
  "application-chat-link-sent",
  "application-joined-chat",
  "application-started",
] as const;

const STAGE_STATUS: Record<(typeof REQUEST_STAGE_IDS)[number], string> = {
  "application-submitted": REQUEST_STATUS.SUBMITTED,
  "application-testing": REQUEST_STATUS.TESTING,
  "application-chat-link-sent": REQUEST_STATUS.CHAT_LINK_SENT,
  "application-joined-chat": REQUEST_STATUS.JOINED_CHAT,
  "application-started": REQUEST_STATUS.STARTED,
};

export function getStageStatus(config: AutomationConfig, stageId: string) {
  const stageTitle = config.stages.find((stage) => stage.id === stageId)?.title;
  return stageTitle || STAGE_STATUS[stageId as keyof typeof STAGE_STATUS];
}

export function getStatusStageId(config: AutomationConfig, status?: string) {
  if (!status) return undefined;
  const byTitle = config.stages.find((stage) => stage.title === status)?.id;
  if (byTitle) return byTitle;
  return REQUEST_STAGE_IDS.find((stageId) => STAGE_STATUS[stageId] === status);
}

export function isBackTransition(config: AutomationConfig, currentStatus: string | undefined, targetStageId: string) {
  const currentStageId = getStatusStageId(config, currentStatus);
  if (!currentStageId) return false;
  const currentIndex = config.stages.findIndex((stage) => stage.id === currentStageId);
  const targetIndex = config.stages.findIndex((stage) => stage.id === targetStageId);
  return currentIndex >= 0 && targetIndex >= 0 && targetIndex < currentIndex;
}
