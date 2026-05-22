import type { AutomationRobot, AutomationScope, AutomationTrigger } from "../../types/automation";

export type {
  AutomationCommonSettings,
  AutomationConditionGroup,
  AutomationConditionMode,
  AutomationConditionOperator,
  AutomationConditionRule,
  AutomationConfig,
  AutomationRobot,
  AutomationRunMode,
  AutomationScope,
  AutomationStage,
  AutomationTiming,
  AutomationTrigger,
} from "../../types/automation";

export type RuleKind = "robot" | "trigger";

export type SelectedRule = {
  kind: RuleKind;
  id: string;
};

export type CatalogState = {
  kind: RuleKind;
  stageId: string;
};

export type CatalogItem = {
  code: string;
  title: string;
  description: string;
  targetStageId?: string;
  targetStatus?: string;
  subject?: string;
  message?: string;
};

export type CatalogGroup = {
  title: string;
  items: CatalogItem[];
};

export type RuleEntity = AutomationRobot | AutomationTrigger;

export type AutomationPanelProps = {
  scope: AutomationScope;
  lockedEventId?: number;
  className?: string;
  hideLocalSave?: boolean;
  hideEventSelector?: boolean;
  onDirtyChange?: (isDirty: boolean) => void;
};

export type AutomationPanelHandle = {
  save: () => Promise<boolean>;
  hasUnsavedChanges: () => boolean;
};
