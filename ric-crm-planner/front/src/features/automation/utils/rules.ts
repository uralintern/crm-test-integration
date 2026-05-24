import type {
  AutomationConditionOperator,
  AutomationConditionRule,
  AutomationConfig,
  AutomationRobot,
  AutomationTrigger,
  CatalogItem,
} from "../types";
import { DEFAULT_COMMON_SETTINGS, DEFAULT_CONDITION } from "../config/options";

export function clampDelay(value: string) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) return 0;
  return Math.round(parsed);
}

export function getStageTitle(config: AutomationConfig, stageId: string) {
  return config.stages.find((stage) => stage.id === stageId)?.title || stageId;
}

export function sortRulesByEnabled<T extends { enabled: boolean }>(items: T[]) {
  return [...items].sort((a, b) => Number(b.enabled) - Number(a.enabled));
}

export function createConditionRule(): AutomationConditionRule {
  return {
    id: `condition-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    field: "status",
    operator: "equals",
    value: "",
  };
}

export function operatorNeedsValue(operator: AutomationConditionOperator) {
  return operator !== "filled" && operator !== "empty";
}

function cloneDefaultSettings() {
  return { ...DEFAULT_COMMON_SETTINGS, condition: { ...DEFAULT_CONDITION, rules: [] } };
}

export function makeRobot(stageId: string, item: CatalogItem): AutomationRobot {
  return {
    id: `robot-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    stageId,
    title: item.title,
    description: item.description,
    action: item.code,
    targetStageId: item.targetStageId || stageId,
    targetStatus: item.targetStatus || "",
    enabled: true,
    settings: cloneDefaultSettings(),
    subject: item.subject || item.title,
    message: item.message || item.description,
    attachments: [],
  };
}

export function makeTrigger(stageId: string, item: CatalogItem): AutomationTrigger {
  return {
    id: `trigger-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    stageId,
    title: item.title,
    description: item.description,
    eventCode: item.code,
    enabled: true,
    settings: cloneDefaultSettings(),
    targetStageId: stageId,
    allowBackTransition: false,
  };
}
