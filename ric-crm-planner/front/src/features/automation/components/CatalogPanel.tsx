import { ArrowRightOutlined, RobotOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { ROBOT_CATALOG, TRIGGER_CATALOG } from "../catalogs";
import { TEXT } from "../config/text";
import type { AutomationConfig, AutomationScope, CatalogItem, CatalogState } from "../types";
import { getStageTitle } from "../utils/rules";
import { getRuleIcon } from "./ruleIcon";

type CatalogPanelProps = {
  scope: AutomationScope;
  catalogState: CatalogState;
  config: AutomationConfig;
  onSelect: (item: CatalogItem) => void;
};

export function CatalogPanel({ scope, catalogState, config, onSelect }: CatalogPanelProps) {
  const groups = catalogState.kind === "robot" ? ROBOT_CATALOG[scope] : TRIGGER_CATALOG[scope];
  const stageTitle = getStageTitle(config, catalogState.stageId);

  return (
    <div className="automation-side__content">
      <div className="automation-side__head">
        <span className={`automation-side__icon automation-side__icon--${catalogState.kind}`}>
          {catalogState.kind === "robot" ? <RobotOutlined /> : <ThunderboltOutlined />}
        </span>
        <div>
          <h3>{catalogState.kind === "robot" ? TEXT.catalogTitleRobot : TEXT.catalogTitleTrigger}</h3>
          <p>Стадия: {stageTitle}</p>
        </div>
      </div>

      <div className="automation-catalog">
        {groups.map((group) => (
          <section key={group.title} className="automation-catalog__group">
            <h4>{group.title}</h4>
            {group.items.map((item) => (
              <button key={item.code} type="button" className="automation-catalog__item" onClick={() => onSelect(item)}>
                <span>{getRuleIcon(catalogState.kind, item.code)}</span>
                <div>
                  <strong>{item.title}</strong>
                  <small>{item.description}</small>
                </div>
                <ArrowRightOutlined />
              </button>
            ))}
          </section>
        ))}
      </div>
    </div>
  );
}
