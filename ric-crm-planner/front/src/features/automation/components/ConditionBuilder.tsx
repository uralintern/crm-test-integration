import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import AppButton from "../../../components/UI/Button";
import AppInput from "../../../components/UI/Input";
import AppSelect from "../../../components/UI/Select";
import {
  CONDITION_FIELD_OPTIONS,
  CONDITION_MODE_OPTIONS,
  CONDITION_OPERATOR_OPTIONS,
} from "../config/options";
import { TEXT } from "../config/text";
import type {
  AutomationConditionGroup,
  AutomationConditionMode,
  AutomationConditionOperator,
  AutomationConditionRule,
} from "../types";
import { createConditionRule, operatorNeedsValue } from "../utils/rules";

type StageOption = { value: string; label: string };

type ConditionBuilderProps = {
  condition: AutomationConditionGroup;
  stageOptions: StageOption[];
  onChange: (condition: AutomationConditionGroup) => void;
};

export function ConditionBuilder({ condition, stageOptions, onChange }: ConditionBuilderProps) {
  const updateRule = (ruleId: string, patch: Partial<AutomationConditionRule>) => {
    onChange({
      ...condition,
      rules: condition.rules.map((rule) => (rule.id === ruleId ? { ...rule, ...patch } : rule)),
    });
  };

  const removeRule = (ruleId: string) => {
    onChange({
      ...condition,
      rules: condition.rules.filter((rule) => rule.id !== ruleId),
    });
  };

  const addRule = () => {
    onChange({
      ...condition,
      rules: [...condition.rules, createConditionRule()],
    });
  };

  return (
    <div className="automation-conditions">
      <div className="automation-conditions__head">
        <span>{TEXT.condition}</span>
        <AppSelect
          value={condition.mode}
          options={CONDITION_MODE_OPTIONS}
          onChange={(value) => onChange({ ...condition, mode: value as AutomationConditionMode })}
        />
      </div>

      {condition.rules.length === 0 ? (
        <div className="automation-conditions__empty">{TEXT.noConditions}</div>
      ) : (
        <div className="automation-conditions__list">
          {condition.rules.map((rule) => {
            const needsValue = operatorNeedsValue(rule.operator);
            const isRange = rule.operator === "in_range";
            const valueOptions = rule.field === "status" ? stageOptions : undefined;

            return (
              <div className="automation-condition-row" key={rule.id}>
                <AppSelect
                  value={rule.field}
                  options={CONDITION_FIELD_OPTIONS}
                  onChange={(value) => updateRule(rule.id, { field: String(value), value: "", valueTo: undefined })}
                />
                <AppSelect
                  value={rule.operator}
                  options={CONDITION_OPERATOR_OPTIONS}
                  onChange={(value) => updateRule(rule.id, { operator: value as AutomationConditionOperator })}
                />
                {needsValue && valueOptions ? (
                  <AppSelect
                    value={rule.value || undefined}
                    placeholder="Значение"
                    options={valueOptions}
                    onChange={(value) => updateRule(rule.id, { value: String(value) })}
                  />
                ) : needsValue ? (
                  <AppInput
                    value={rule.value}
                    placeholder="Значение"
                    onChange={(event) => updateRule(rule.id, { value: event.target.value })}
                  />
                ) : (
                  <div className="automation-condition-row__skip">Без значения</div>
                )}
                {isRange && (
                  <AppInput
                    value={rule.valueTo || ""}
                    placeholder="До"
                    onChange={(event) => updateRule(rule.id, { valueTo: event.target.value })}
                  />
                )}
                <AppButton
                  className="automation-condition-row__remove"
                  onClick={() => removeRule(rule.id)}
                  aria-label="Удалить условие"
                >
                  <DeleteOutlined />
                </AppButton>
              </div>
            );
          })}
        </div>
      )}

      <AppButton className="automation-conditions__add" onClick={addRule}>
        <PlusOutlined />
        <span>{TEXT.addCondition}</span>
      </AppButton>
    </div>
  );
}
