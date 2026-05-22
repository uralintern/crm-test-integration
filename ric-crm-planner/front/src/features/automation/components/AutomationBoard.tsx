import type { AutomationConfig, RuleKind, SelectedRule } from "../types";
import { TEXT } from "../config/text";
import { sortRulesByEnabled } from "../utils/rules";
import { StageLane } from "./StageLane";

type AutomationBoardProps = {
  config: AutomationConfig;
  selectedStageId: string;
  selectedRule: SelectedRule | null;
  onStageSelect: (stageId: string) => void;
  onAdd: (kind: RuleKind, stageId: string) => void;
  onRuleSelect: (rule: SelectedRule, stageId: string) => void;
};

export function AutomationBoard({
  config,
  selectedStageId,
  selectedRule,
  onStageSelect,
  onAdd,
  onRuleSelect,
}: AutomationBoardProps) {
  return (
    <div className="automation-board" aria-label="Стадии автоматизации">
      {config.stages.map((stage, index) => {
        const triggers = sortRulesByEnabled(
          config.triggers.filter((trigger) => trigger.stageId === stage.id && !trigger.deleted)
        );
        const robots = sortRulesByEnabled(config.robots.filter((robot) => robot.stageId === stage.id && !robot.deleted));
        const stageIsSelected = selectedStageId === stage.id;

        return (
          <section key={stage.id} className={`automation-stage ${stageIsSelected ? "is-selected" : ""}`}>
            <button type="button" className="automation-stage__head" onClick={() => onStageSelect(stage.id)}>
              <span className="automation-stage__index">{index + 1}</span>
              <div>
                <h3>{stage.title}</h3>
                <p>{stage.description}</p>
              </div>
            </button>

            <StageLane
              kind="trigger"
              title={TEXT.triggers}
              emptyText={TEXT.noTriggers}
              addText={TEXT.addTrigger}
              stageId={stage.id}
              items={triggers}
              selectedRule={selectedRule}
              onAdd={onAdd}
              onSelect={onRuleSelect}
              config={config}
            />

            <StageLane
              kind="robot"
              title={TEXT.robots}
              emptyText={TEXT.noRobots}
              addText={TEXT.addRobot}
              stageId={stage.id}
              items={robots}
              selectedRule={selectedRule}
              onAdd={onAdd}
              onSelect={onRuleSelect}
              config={config}
            />
          </section>
        );
      })}
    </div>
  );
}
