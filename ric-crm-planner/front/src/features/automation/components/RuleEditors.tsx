import { DeleteOutlined, RobotOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { Tooltip } from "antd";
import { ORGANIZER_REQUEST_STATUSES } from "../../../constants/requestProgress";
import AppButton from "../../../components/UI/Button";
import AppInput, { AppTextArea } from "../../../components/UI/Input";
import AppSelect from "../../../components/UI/Select";
import AppSwitch from "../../../components/UI/Switch";
import { DEFAULT_CONDITION, RUN_MODE_OPTIONS, TIMING_OPTIONS } from "../config/options";
import { TEXT } from "../config/text";
import type {
  AutomationCommonSettings,
  AutomationConfig,
  AutomationRobot,
  AutomationRunMode,
  AutomationTiming,
  AutomationTrigger,
  RuleKind,
} from "../types";
import { clampDelay, getStageTitle } from "../utils/rules";
import { ConditionBuilder } from "./ConditionBuilder";

type StageOption = { value: string; label: string };

type RobotEditorProps = {
  robot: AutomationRobot;
  stageOptions: StageOption[];
  onChange: (updater: (robot: AutomationRobot) => AutomationRobot) => void;
  onDelete: () => void;
};

export function RobotEditor({ robot, stageOptions, onChange, onDelete }: RobotEditorProps) {
  const isStatusChangeRobot = robot.action === "status.change";
  const statusOptions = ORGANIZER_REQUEST_STATUSES.map((status) => ({ value: status, label: status }));
  const targetStatus =
    robot.targetStatus ||
    stageOptions.find((option) => option.value === robot.targetStageId)?.label ||
    stageOptions.find((option) => option.value === robot.stageId)?.label ||
    "";

  return (
    <div className="automation-side__content">
      <EditorHeader
        kind="robot"
        title={robot.title}
        enabled={robot.enabled}
        onEnabledChange={(enabled) => onChange((item) => ({ ...item, enabled }))}
      />

      <div className="automation-form">
        <label>
          <span>{TEXT.title}</span>
          <AppInput value={robot.title} onChange={(event) => onChange((item) => ({ ...item, title: event.target.value }))} />
        </label>

        <label>
          <span>{TEXT.description}</span>
          <AppTextArea
            value={robot.description}
            autoSize={{ minRows: 2, maxRows: 4 }}
            onChange={(event) => onChange((item) => ({ ...item, description: event.target.value }))}
          />
        </label>

        <CommonSettingsEditor
          settings={robot.settings}
          stageOptions={stageOptions}
          onChange={(settings) => onChange((item) => ({ ...item, settings }))}
        />

        {isStatusChangeRobot ? (
          <label>
            <span>Статус для перевода</span>
            <AppSelect
              value={targetStatus}
              options={statusOptions}
              onChange={(value) =>
                onChange((item) => ({
                  ...item,
                  targetStatus: String(value),
                  targetStageId: stageOptions.find((option) => option.label === value)?.value || item.targetStageId,
                }))
              }
            />
          </label>
        ) : (
          <>
            <label>
              <span>{TEXT.subject}</span>
              <AppInput value={robot.subject} onChange={(event) => onChange((item) => ({ ...item, subject: event.target.value }))} />
            </label>

            <label>
              <span>{TEXT.message}</span>
              <AppTextArea
                value={robot.message}
                autoSize={{ minRows: 3, maxRows: 6 }}
                onChange={(event) => onChange((item) => ({ ...item, message: event.target.value }))}
              />
            </label>
          </>
        )}

        <ReadOnlyCode label={TEXT.actionCode} value={robot.action} />

        <AppButton className="automation-form__delete" onClick={onDelete}>
          <DeleteOutlined />
          <span>{TEXT.delete}</span>
        </AppButton>
      </div>
    </div>
  );
}

type TriggerEditorProps = {
  trigger: AutomationTrigger;
  config: AutomationConfig;
  stageOptions: StageOption[];
  onChange: (updater: (trigger: AutomationTrigger) => AutomationTrigger) => void;
  onDelete: () => void;
};

export function TriggerEditor({ trigger, config, stageOptions, onChange, onDelete }: TriggerEditorProps) {
  const currentStageTitle = getStageTitle(config, trigger.stageId);

  return (
    <div className="automation-side__content">
      <EditorHeader
        kind="trigger"
        title={trigger.title}
        enabled={trigger.enabled}
        onEnabledChange={(enabled) => onChange((item) => ({ ...item, enabled }))}
      />

      <div className="automation-form">
        <label>
          <span>{TEXT.title}</span>
          <AppInput value={trigger.title} onChange={(event) => onChange((item) => ({ ...item, title: event.target.value }))} />
        </label>

        <label>
          <span>{TEXT.description}</span>
          <AppTextArea
            value={trigger.description}
            autoSize={{ minRows: 2, maxRows: 4 }}
            onChange={(event) => onChange((item) => ({ ...item, description: event.target.value }))}
          />
        </label>

        <CommonSettingsEditor
          settings={trigger.settings}
          stageOptions={stageOptions}
          onChange={(settings) => onChange((item) => ({ ...item, settings }))}
        />

        <ReadOnlyCode label={TEXT.eventCode} value={trigger.eventCode} />
        <ReadOnlyCode label={TEXT.triggerStage} value={currentStageTitle} />

        <AppButton className="automation-form__delete" onClick={onDelete}>
          <DeleteOutlined />
          <span>{TEXT.delete}</span>
        </AppButton>
      </div>
    </div>
  );
}

type EditorHeaderProps = {
  kind: RuleKind;
  title: string;
  enabled: boolean;
  onEnabledChange: (enabled: boolean) => void;
};

function EditorHeader({ kind, title, enabled, onEnabledChange }: EditorHeaderProps) {
  return (
    <div className="automation-side__head">
      <span className={`automation-side__icon automation-side__icon--${kind}`}>
        {kind === "robot" ? <RobotOutlined /> : <ThunderboltOutlined />}
      </span>
      <div>
        <h3>{title}</h3>
        <p>{kind === "robot" ? "Робот выполнит действие на стадии" : "Триггер проверит событие на выбранном статусе"}</p>
      </div>
      <Tooltip title={enabled ? "Выключить" : "Включить"}>
        <AppSwitch compact checked={enabled} onChange={onEnabledChange} />
      </Tooltip>
    </div>
  );
}

type CommonSettingsEditorProps = {
  settings: AutomationCommonSettings;
  stageOptions: StageOption[];
  onChange: (settings: AutomationCommonSettings) => void;
};

function CommonSettingsEditor({ settings, stageOptions, onChange }: CommonSettingsEditorProps) {
  const updateSettings = (patch: Partial<AutomationCommonSettings>) => onChange({ ...settings, ...patch });

  return (
    <fieldset className="automation-form__fieldset">
      <legend>{TEXT.settings}</legend>

      <label>
        <span>{TEXT.runMode}</span>
        <AppSelect
          value={settings.runMode}
          onChange={(value) => updateSettings({ runMode: value as AutomationRunMode })}
          options={RUN_MODE_OPTIONS}
        />
      </label>

      <label>
        <span>{TEXT.timing}</span>
        <AppSelect
          value={settings.timing}
          onChange={(value) => updateSettings({ timing: value as AutomationTiming })}
          options={TIMING_OPTIONS}
        />
      </label>

      {settings.timing === "delayed" && (
        <label>
          <span>{TEXT.delayMinutes}</span>
          <AppInput
            type="number"
            min={0}
            value={String(settings.delayMinutes)}
            onChange={(event) => updateSettings({ delayMinutes: clampDelay(event.target.value) })}
          />
        </label>
      )}

      <ConditionBuilder
        condition={settings.condition || DEFAULT_CONDITION}
        stageOptions={stageOptions}
        onChange={(condition) => updateSettings({ condition })}
      />
    </fieldset>
  );
}

function ReadOnlyCode({ label, value }: { label: string; value: string }) {
  return (
    <div className="automation-form__code">
      <span>{label}</span>
      <code>{value}</code>
    </div>
  );
}
