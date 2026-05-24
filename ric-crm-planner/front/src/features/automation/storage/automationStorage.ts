import type {
  AutomationAttachment,
  AutomationCommonSettings,
  AutomationConditionGroup,
  AutomationConditionOperator,
  AutomationConfig,
  AutomationRobot,
  AutomationScope,
  AutomationStage,
  AutomationTrigger,
} from "../types";
import client from "../../../api/client";
import { DEFAULT_SETTINGS, ROBOT_TEMPLATES, STAGE_TEMPLATES, TRIGGER_TEMPLATES } from "./defaults";

const STORAGE_KEY = "ric_crm_automation_configs_v4";

type AutomationConfigs = Record<string, AutomationConfig>;

function nowIso() {
  return new Date().toISOString();
}

function configKey(scope: AutomationScope, eventId: number) {
  return `${scope}:${eventId}`;
}

function cloneSettings(settings: AutomationCommonSettings = DEFAULT_SETTINGS): AutomationCommonSettings {
  return {
    runMode: settings.runMode,
    timing: settings.timing,
    delayMinutes: settings.delayMinutes,
    condition: {
      mode: settings.condition.mode,
      rules: settings.condition.rules.map((rule) => ({ ...rule })),
    },
  };
}

function normalizeScope(value: unknown): AutomationScope | null {
  if (value === "crm" || value === "planner" || value === "requests") return value;
  if (value === "tasks") return "planner";
  return null;
}

function mergeItems<T extends { id: string }>(defaults: T[], saved: T[] = []) {
  const savedById = new Map(saved.map((item) => [item.id, item]));
  const mergedDefaults = defaults.map((item) => ({ ...item, ...savedById.get(item.id) }));
  const customItems = saved.filter((item) => !defaults.some((defaultItem) => defaultItem.id === item.id));
  return [...mergedDefaults, ...customItems];
}

function normalizeOperator(value: unknown): AutomationConditionOperator {
  if (
    value === "not_equals" ||
    value === "contains" ||
    value === "not_contains" ||
    value === "filled" ||
    value === "empty" ||
    value === "greater_or_equal" ||
    value === "less_or_equal" ||
    value === "in_range"
  ) {
    return value;
  }

  return "equals";
}

function normalizeConditionGroup(value: unknown): AutomationConditionGroup {
  if (!value || typeof value !== "object") return cloneSettings().condition;

  const condition = value as Partial<AutomationConditionGroup>;
  const mode = condition.mode === "any" ? "any" : "all";
  const rules = Array.isArray(condition.rules)
    ? condition.rules
        .map((rule, index) => {
          const item = rule as unknown as Record<string, unknown>;
          return {
            id: String(item.id || `condition-${Date.now()}-${index}`),
            field: String(item.field || "status"),
            operator: normalizeOperator(item.operator),
            value: String(item.value || ""),
            valueTo: typeof item.valueTo === "string" ? item.valueTo : undefined,
          };
        })
        .filter((rule) => rule.id)
    : [];

  return { mode, rules };
}


function normalizeAttachment(value: unknown): AutomationAttachment | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Record<string, unknown>;
  const id = Number(item.id);
  if (!Number.isFinite(id)) return null;
  return {
    id,
    name: String(item.name || item.fileName || "Файл"),
    size: Math.max(0, Number(item.size || 0)),
    contentType: typeof item.contentType === "string" ? item.contentType : undefined,
    createdAt: typeof item.createdAt === "string" ? item.createdAt : undefined,
  };
}

function normalizeSettings(settings?: Partial<AutomationCommonSettings>): AutomationCommonSettings {
  return {
    runMode: settings?.runMode === "parallel" ? "parallel" : "queue",
    timing: settings?.timing === "delayed" ? "delayed" : "immediate",
    delayMinutes: Math.max(0, Number(settings?.delayMinutes || 0)),
    condition: normalizeConditionGroup(settings?.condition),
  };
}

function normalizeStage(stage: AutomationStage): AutomationStage {
  return {
    id: String(stage.id),
    title: String(stage.title || stage.id),
    description: String(stage.description || ""),
  };
}

function normalizeRobot(robot: AutomationRobot, fallbackStageId: string): AutomationRobot {
  const id = String(robot.id);
  const stageId =
    (id === "crm-send-chat-link" || id === "request-send-chat-link") && robot.stageId === "application-joined-chat"
      ? "application-chat-link-sent"
      : String(robot.stageId || fallbackStageId);

  const action = String(robot.action || "notification.organizer");

  return {
    id,
    stageId,
    title: String(robot.title || "Робот"),
    description: String(robot.description || ""),
    action: action === "message.vk_interactive" ? "message.vk" : action,
    targetStageId: String(robot.targetStageId || fallbackStageId),
    targetStatus: String(robot.targetStatus || ""),
    enabled: Boolean(robot.enabled),
    deleted: Boolean(robot.deleted),
    settings: normalizeSettings(robot.settings),
    subject: String(robot.subject || robot.title || "Уведомление"),
    message: String(robot.message || robot.description || ""),
    attachments: Array.isArray(robot.attachments) ? (robot.attachments.map(normalizeAttachment).filter(Boolean) as AutomationAttachment[]) : [],
  };
}

function normalizeTrigger(trigger: AutomationTrigger, fallbackStageId: string): AutomationTrigger {
  const id = String(trigger.id);
  const stageId =
    (id === "crm-chat-link-opened" || id === "request-chat-link-opened") && trigger.stageId === "application-chat-link-sent"
      ? "application-joined-chat"
      : String(trigger.stageId || fallbackStageId);
  const targetStageId =
    id === "crm-chat-link-opened" || id === "request-chat-link-opened"
      ? "application-joined-chat"
      : String(trigger.targetStageId || fallbackStageId);

  return {
    id,
    stageId,
    title: String(trigger.title || "Триггер"),
    description: String(trigger.description || ""),
    eventCode: String(trigger.eventCode || "field.changed"),
    enabled: Boolean(trigger.enabled),
    deleted: Boolean(trigger.deleted),
    settings: normalizeSettings(trigger.settings),
    targetStageId,
    allowBackTransition: Boolean(trigger.allowBackTransition),
  };
}

export function createDefaultAutomationConfig(scope: AutomationScope, eventId: number): AutomationConfig {
  const stages = STAGE_TEMPLATES[scope].map((stage) => ({ ...stage }));
  const robots = ROBOT_TEMPLATES[scope].map((robot) => ({
    ...robot,
    enabled: true,
    settings: cloneSettings(),
  }));
  const triggers = TRIGGER_TEMPLATES[scope].map((trigger) => ({
    ...trigger,
    enabled: true,
    allowBackTransition: false,
    settings: cloneSettings(),
  }));

  return {
    scope,
    eventId,
    updatedAt: nowIso(),
    stages,
    robots,
    triggers,
  };
}

function mergeConfigWithDefaults(config: AutomationConfig): AutomationConfig {
  const normalizedScope = normalizeScope(config.scope) ?? "crm";
  const eventId = Number(config.eventId);
  const defaults = createDefaultAutomationConfig(normalizedScope, Number.isFinite(eventId) ? eventId : 0);
  const stages = mergeItems(defaults.stages, (config.stages || []).map(normalizeStage));
  const stageIds = new Set(stages.map((stage) => stage.id));
  const fallbackStageId = stages[0]?.id || "";

  const robots = mergeItems(defaults.robots, config.robots || [])
    .map((robot) => normalizeRobot(robot, fallbackStageId))
    .map((robot) => ({
      ...robot,
      stageId: stageIds.has(robot.stageId) ? robot.stageId : fallbackStageId,
      targetStageId: robot.targetStageId && stageIds.has(robot.targetStageId) ? robot.targetStageId : fallbackStageId,
    }));

  const triggers = mergeItems(defaults.triggers, config.triggers || [])
    .map((trigger) => normalizeTrigger(trigger, fallbackStageId))
    .map((trigger) => ({
      ...trigger,
      stageId: stageIds.has(trigger.stageId) ? trigger.stageId : fallbackStageId,
      targetStageId: stageIds.has(trigger.targetStageId) ? trigger.targetStageId : fallbackStageId,
    }));

  return {
    ...defaults,
    ...config,
    scope: normalizedScope,
    eventId: defaults.eventId,
    stages,
    robots,
    triggers,
    updatedAt: config.updatedAt || defaults.updatedAt,
  };
}

export function readAutomationConfigs(): AutomationConfigs {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};

    const parsed = JSON.parse(raw) as AutomationConfigs;
    return Object.fromEntries(
      Object.entries(parsed)
        .map(([key, config]) => {
          const scope = normalizeScope(config?.scope);
          const eventId = Number(config?.eventId);
          if (!scope || !Number.isFinite(eventId)) return null;
          const normalized = mergeConfigWithDefaults({ ...config, scope, eventId });
          return [key, normalized] as const;
        })
        .filter((item): item is readonly [string, AutomationConfig] => Boolean(item))
    );
  } catch {
    return {};
  }
}

export function readAutomationConfig(scope: AutomationScope, eventId: number): AutomationConfig {
  const configs = readAutomationConfigs();
  return configs[configKey(scope, eventId)] || createDefaultAutomationConfig(scope, eventId);
}

export function writeAutomationConfig(config: AutomationConfig) {
  const configs = readAutomationConfigs();
  const normalized = mergeConfigWithDefaults({ ...config, updatedAt: nowIso() });
  configs[configKey(normalized.scope, normalized.eventId)] = normalized;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(configs));
  return normalized;
}

export async function readAutomationConfigAsync(scope: AutomationScope, eventId: number): Promise<AutomationConfig> {
  if (client.USE_MOCK || scope === "requests") {
    return readAutomationConfig(scope, eventId);
  }

  const endpoint = scope === "planner" ? `/api/planner/automation/${eventId}/` : `/api/users/automation/${eventId}/`;
  const config = await client.get<AutomationConfig>(endpoint);
  return mergeConfigWithDefaults({
    ...config,
    scope,
    eventId,
  });
}

export async function writeAutomationConfigAsync(config: AutomationConfig): Promise<AutomationConfig> {
  const normalized = mergeConfigWithDefaults({ ...config, updatedAt: nowIso() });
  if (client.USE_MOCK || normalized.scope === "requests") {
    return writeAutomationConfig(normalized);
  }

  const endpoint =
    normalized.scope === "planner"
      ? `/api/planner/automation/${normalized.eventId}/`
      : `/api/users/automation/${normalized.eventId}/`;
  const saved = await client.put<AutomationConfig>(endpoint, normalized);
  return mergeConfigWithDefaults({
    ...saved,
    scope: normalized.scope,
    eventId: normalized.eventId,
  });
}

export async function uploadCrmAutomationAttachment(eventId: number, file: File): Promise<AutomationAttachment> {
  const formData = new FormData();
  formData.append("file", file);
  return client.post<AutomationAttachment>("/api/users/automation/" + eventId + "/attachments/", formData);
}
