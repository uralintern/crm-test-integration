import { PlusOutlined, RobotOutlined, ThunderboltOutlined } from "@ant-design/icons";
import AppButton from "../../../components/UI/Button";
import type { AutomationConfig, AutomationRobot, AutomationTrigger, RuleKind, SelectedRule } from "../types";
import { AutomationCard } from "./AutomationCard";

type StageLaneProps = {
  kind: RuleKind;
  title: string;
  emptyText: string;
  addText: string;
  stageId: string;
  items: Array<AutomationRobot | AutomationTrigger>;
  selectedRule: SelectedRule | null;
  onAdd: (kind: RuleKind, stageId: string) => void;
  onSelect: (rule: SelectedRule, stageId: string) => void;
  config: AutomationConfig;
};

export function StageLane({
  kind,
  title,
  emptyText,
  addText,
  stageId,
  items,
  selectedRule,
  onAdd,
  onSelect,
  config,
}: StageLaneProps) {
  return (
    <div className={`automation-lane automation-lane--${kind}`}>
      <div className="automation-lane__title">
        {kind === "trigger" ? <ThunderboltOutlined /> : <RobotOutlined />}
        <span>{title}</span>
      </div>

      <div className="automation-lane__list">
        {items.map((item) => {
          const ruleId = { kind, id: item.id };
          const isSelected = selectedRule?.kind === kind && selectedRule.id === item.id;

          return (
            <AutomationCard
              key={item.id}
              kind={kind}
              item={item}
              selected={isSelected}
              config={config}
              onSelect={() => onSelect(ruleId, stageId)}
            />
          );
        })}

        {items.length === 0 && <div className="automation-lane__empty">{emptyText}</div>}

        <AppButton className="automation-lane__add" onClick={() => onAdd(kind, stageId)}>
          <PlusOutlined />
          <span>{addText}</span>
        </AppButton>
      </div>
    </div>
  );
}
