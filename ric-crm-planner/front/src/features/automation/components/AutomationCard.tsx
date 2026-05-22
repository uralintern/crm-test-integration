import { Tag } from "antd";
import type { AutomationConfig, AutomationRobot, AutomationTrigger, RuleKind } from "../types";
import { TEXT } from "../config/text";
import { getStageTitle } from "../utils/rules";
import { getRuleIcon } from "./ruleIcon";

type AutomationCardProps = {
  kind: RuleKind;
  item: AutomationRobot | AutomationTrigger;
  selected: boolean;
  config: AutomationConfig;
  onSelect: () => void;
};

export function AutomationCard({ kind, item, selected, config, onSelect }: AutomationCardProps) {
  const code = kind === "robot" ? (item as AutomationRobot).action : (item as AutomationTrigger).eventCode;
  const targetStage =
    kind === "trigger" ? getStageTitle(config, (item as AutomationTrigger).targetStageId) : getStageTitle(config, item.stageId);

  return (
    <button
      type="button"
      className={`automation-card ${selected ? "is-selected" : ""} ${item.enabled ? "is-active" : "is-disabled"}`}
      onClick={onSelect}
    >
      <span className="automation-card__icon">{getRuleIcon(kind, code)}</span>
      <span className="automation-card__body">
        <strong>{item.title}</strong>
        <small>{kind === "trigger" ? `переместит в «${targetStage}»` : item.description}</small>
      </span>
      <Tag color={item.enabled ? "green" : "default"}>{item.enabled ? TEXT.active : TEXT.inactive}</Tag>
    </button>
  );
}
