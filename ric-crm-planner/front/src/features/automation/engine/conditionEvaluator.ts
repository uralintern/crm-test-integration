import type { Event } from "../../../types/event";
import type { Request as ReqType } from "../../../types/request";
import type {
  AutomationCommonSettings,
  AutomationConfig,
  AutomationConditionGroup,
  AutomationConditionRule,
} from "../types";
import { getStageStatus } from "./stageResolver";

function toComparable(value: unknown) {
  if (value == null) return "";
  if (Array.isArray(value)) return value.map((item) => String(item)).join(", ");
  return String(value).trim();
}

function lower(value: unknown) {
  return toComparable(value).toLowerCase();
}

function getCustomField(request: ReqType, keys: string[]) {
  const customFields = request.customFields || {};
  const normalized = Object.entries(customFields).map(([key, value]) => [key.toLowerCase(), value] as const);
  for (const key of keys) {
    const found = normalized.find(([candidate]) => candidate === key.toLowerCase());
    if (found) return found[1];
  }
  return undefined;
}

function getRequestValue(request: ReqType, keys: string[]) {
  const source = request as unknown as Record<string, unknown>;
  for (const key of keys) {
    if (typeof source[key] !== "undefined") return source[key];
  }
  return undefined;
}

function getConditionFieldValue(rule: AutomationConditionRule, request: ReqType, event?: Event) {
  switch (rule.field) {
    case "status":
      return request.status;
    case "event":
      return request.eventTitle || event?.title || request.eventId;
    case "direction":
      return request.directionTitle || request.directionId;
    case "project":
      return request.projectTitle || request.projectId;
    case "specialization":
      return request.specialization || request.specializationId;
    case "university":
      return request.university || getCustomField(request, ["university", "университет"]);
    case "course":
      return request.course || getCustomField(request, ["course", "курс"]);
    case "vk":
      return getCustomField(request, ["vk", "аккаунт vk", "аккаунт в вк", "вк"]);
    case "application_date":
      return request.createdAt;
    case "testing_result":
      return (
        getRequestValue(request, ["testingResult", "testing_result", "testScore", "test_score", "score"]) ??
        getCustomField(request, ["testing_result", "результат тестирования", "тестирование"])
      );
    case "responsible":
      return event?.organizer || event?.leader || event?.organizerIds?.join(", ");
    default:
      return getCustomField(request, [rule.field]) ?? "";
  }
}

function getExpectedValue(rule: AutomationConditionRule, config: AutomationConfig) {
  if (rule.field === "status") return getStageStatus(config, rule.value) || rule.value;
  return rule.value;
}

function conditionMatches(rule: AutomationConditionRule, request: ReqType, config: AutomationConfig, event?: Event) {
  const actual = getConditionFieldValue(rule, request, event);
  const expected = getExpectedValue(rule, config);
  const actualText = lower(actual);
  const expectedText = lower(expected);

  switch (rule.operator) {
    case "filled":
      return actualText.length > 0;
    case "empty":
      return actualText.length === 0;
    case "equals":
      return actualText === expectedText;
    case "not_equals":
      return actualText !== expectedText;
    case "contains":
      return actualText.includes(expectedText);
    case "not_contains":
      return !actualText.includes(expectedText);
    case "greater_or_equal":
      return Number(actual) >= Number(rule.value);
    case "less_or_equal":
      return Number(actual) <= Number(rule.value);
    case "in_range": {
      const number = Number(actual);
      return number >= Number(rule.value) && number <= Number(rule.valueTo);
    }
    default:
      return false;
  }
}

export function conditionsMatch(settings: AutomationCommonSettings, request: ReqType, config: AutomationConfig, event?: Event) {
  const condition: AutomationConditionGroup = settings.condition || { mode: "all", rules: [] };
  const rules = condition.rules || [];
  if (rules.length === 0) return true;
  const checks = rules.map((rule) => conditionMatches(rule, request, config, event));
  return condition.mode === "any" ? checks.some(Boolean) : checks.every(Boolean);
}
