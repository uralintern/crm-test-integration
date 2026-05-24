export type AutomationScope = "crm" | "planner" | "requests";

export type AutomationRunMode = "queue" | "parallel";

export type AutomationTiming = "immediate" | "delayed";

export type AutomationConditionMode = "all" | "any";

export type AutomationConditionOperator =
  | "equals"
  | "not_equals"
  | "contains"
  | "not_contains"
  | "filled"
  | "empty"
  | "greater_or_equal"
  | "less_or_equal"
  | "in_range";

export interface AutomationConditionRule {
  id: string;
  field: string;
  operator: AutomationConditionOperator;
  value: string;
  valueTo?: string;
}

export interface AutomationConditionGroup {
  mode: AutomationConditionMode;
  rules: AutomationConditionRule[];
}

export interface AutomationStage {
  id: string;
  title: string;
  description: string;
}

export interface AutomationCommonSettings {
  runMode: AutomationRunMode;
  timing: AutomationTiming;
  delayMinutes: number;
  condition: AutomationConditionGroup;
}

export interface AutomationAttachment {
  id: number;
  name: string;
  size: number;
  contentType?: string;
  createdAt?: string;
}

export interface AutomationRobot {
  id: string;
  stageId: string;
  title: string;
  description: string;
  action: string;
  targetStageId?: string;
  targetStatus?: string;
  enabled: boolean;
  deleted?: boolean;
  settings: AutomationCommonSettings;
  subject: string;
  message: string;
  attachments?: AutomationAttachment[];
}

export interface AutomationTrigger {
  id: string;
  stageId: string;
  title: string;
  description: string;
  eventCode: string;
  enabled: boolean;
  deleted?: boolean;
  settings: AutomationCommonSettings;
  targetStageId: string;
  allowBackTransition: boolean;
}

export interface AutomationConfig {
  scope: AutomationScope;
  eventId: number;
  updatedAt: string;
  stages: AutomationStage[];
  triggers: AutomationTrigger[];
  robots: AutomationRobot[];
}
