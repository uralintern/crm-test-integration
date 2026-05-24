import { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useState } from "react";
import { CloseOutlined, RobotOutlined, SaveOutlined, SettingOutlined } from "@ant-design/icons";
import { Empty, Spin, Tag } from "antd";
import { getEvents } from "../../events/api/events";
import { useToast } from "../../../components/Toast/ToastProvider";
import AppButton from "../../../components/UI/Button";
import AppSelect from "../../../components/UI/Select";
import {
  createDefaultAutomationConfig,
  readAutomationConfigAsync,
  writeAutomationConfigAsync,
} from "../storage/automationStorage";
import { SCOPE_TEXT, TEXT } from "../config/text";
import type {
  AutomationConfig,
  AutomationPanelHandle,
  AutomationPanelProps,
  AutomationRobot,
  AutomationTrigger,
  CatalogItem,
  CatalogState,
  RuleKind,
  SelectedRule,
} from "../types";
import type { Event } from "../../../types/event";
import { getEventStorageKey, getEventTitle, getStageStorageKey, readStoredEventId, readStoredStageId } from "../utils/storageKeys";
import { makeRobot, makeTrigger } from "../utils/rules";
import { AutomationBoard } from "./AutomationBoard";
import { CatalogPanel } from "./CatalogPanel";
import { RobotEditor, TriggerEditor } from "./RuleEditors";
import "../styles/automation-panel.scss";

const AutomationPanel = forwardRef<AutomationPanelHandle, AutomationPanelProps>(function AutomationPanel(
  { scope, lockedEventId, className = "", hideLocalSave = false, hideEventSelector = false, onDirtyChange },
  ref
) {
  const { showToast } = useToast();
  const [events, setEvents] = useState<Event[]>([]);
  const [selectedEventId, setSelectedEventId] = useState<number | null>(lockedEventId ?? null);
  const [selectedStageId, setSelectedStageId] = useState("");
  const [config, setConfig] = useState<AutomationConfig | null>(null);
  const [selectedRule, setSelectedRule] = useState<SelectedRule | null>(null);
  const [catalogState, setCatalogState] = useState<CatalogState | null>(null);
  const [loading, setLoading] = useState(false);
  const [savedSnapshot, setSavedSnapshot] = useState("");

  const configSnapshot = useMemo(() => (config ? JSON.stringify(config) : ""), [config]);
  const hasUnsavedChanges = Boolean(config && savedSnapshot && configSnapshot !== savedSnapshot);

  useEffect(() => {
    onDirtyChange?.(hasUnsavedChanges);
  }, [hasUnsavedChanges, onDirtyChange]);

  useEffect(() => {
    let mounted = true;
    setLoading(true);

    getEvents()
      .then((items) => {
        if (mounted) setEvents(items);
      })
      .catch(() => {
        if (mounted) showToast("error", TEXT.loadError);
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [showToast]);

  useEffect(() => {
    if (lockedEventId) {
      setSelectedEventId(lockedEventId);
      return;
    }

    if (events.length === 0) {
      setSelectedEventId(null);
      return;
    }

    setSelectedEventId((current) => {
      const savedEventId = readStoredEventId(scope, events);
      if (savedEventId) return savedEventId;
      if (current && events.some((event) => Number(event.id) === Number(current))) return current;
      return Number(events[0]?.id) || null;
    });
  }, [events, lockedEventId, scope]);

  useEffect(() => {
    if (lockedEventId || !selectedEventId) return;
    window.localStorage.setItem(getEventStorageKey(scope), String(selectedEventId));
  }, [lockedEventId, scope, selectedEventId]);

  useEffect(() => {
    if (!selectedEventId) {
      setConfig(null);
      return;
    }

    let mounted = true;
    setLoading(true);
    readAutomationConfigAsync(scope, selectedEventId)
      .then((nextConfig) => {
        if (!mounted) return;
        setConfig(nextConfig);
        setSavedSnapshot(JSON.stringify(nextConfig));
        setSelectedStageId(readStoredStageId(scope, selectedEventId, nextConfig) || nextConfig.stages[0]?.id || "");
        setSelectedRule(null);
        setCatalogState(null);
      })
      .catch(() => {
        if (mounted) showToast("error", TEXT.loadError);
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [scope, selectedEventId, showToast]);

  useEffect(() => {
    if (!selectedEventId || !selectedStageId) return;
    window.localStorage.setItem(getStageStorageKey(scope, selectedEventId), selectedStageId);
  }, [scope, selectedEventId, selectedStageId]);

  useEffect(() => {
    if (!config) return;
    if (config.stages.some((stage) => stage.id === selectedStageId)) return;
    setSelectedStageId(config.stages[0]?.id || "");
  }, [config, selectedStageId]);

  const selectedEvent = useMemo(
    () => events.find((event) => Number(event.id) === Number(selectedEventId)),
    [events, selectedEventId]
  );

  const stageOptions = useMemo(
    () => config?.stages.map((stage) => ({ value: stage.id, label: stage.title })) ?? [],
    [config?.stages]
  );

  const selectedRobot = useMemo(
    () => config?.robots.find((robot) => selectedRule?.kind === "robot" && robot.id === selectedRule.id),
    [config?.robots, selectedRule]
  );

  const selectedTrigger = useMemo(
    () => config?.triggers.find((trigger) => selectedRule?.kind === "trigger" && trigger.id === selectedRule.id),
    [config?.triggers, selectedRule]
  );

  const boardStats = useMemo(() => {
    if (!config) return { robots: 0, triggers: 0, active: 0 };
    const visibleRobots = config.robots.filter((robot) => !robot.deleted);
    const visibleTriggers = config.triggers.filter((trigger) => !trigger.deleted);
    const active = visibleRobots.filter((robot) => robot.enabled).length + visibleTriggers.filter((trigger) => trigger.enabled).length;
    return { robots: visibleRobots.length, triggers: visibleTriggers.length, active };
  }, [config]);

  const updateRobot = (robotId: string, updater: (robot: AutomationRobot) => AutomationRobot) => {
    setConfig((current) =>
      current ? { ...current, robots: current.robots.map((robot) => (robot.id === robotId ? updater(robot) : robot)) } : current
    );
  };

  const updateTrigger = (triggerId: string, updater: (trigger: AutomationTrigger) => AutomationTrigger) => {
    setConfig((current) =>
      current
        ? { ...current, triggers: current.triggers.map((trigger) => (trigger.id === triggerId ? updater(trigger) : trigger)) }
        : current
    );
  };

  const deleteRule = (rule: SelectedRule) => {
    setConfig((current) => {
      if (!current) return current;
      return rule.kind === "robot"
        ? {
            ...current,
            robots: current.robots.map((robot) => (robot.id === rule.id ? { ...robot, enabled: false, deleted: true } : robot)),
          }
        : {
            ...current,
            triggers: current.triggers.map((trigger) =>
              trigger.id === rule.id ? { ...trigger, enabled: false, deleted: true } : trigger
            ),
          };
    });
    setSelectedRule(null);
  };

  const addCatalogRule = (item: CatalogItem) => {
    if (!catalogState) return;

    if (catalogState.kind === "robot") {
      const nextRule = makeRobot(catalogState.stageId, item);
      setConfig((current) => (current ? { ...current, robots: [...current.robots, nextRule] } : current));
      setSelectedRule({ kind: "robot", id: nextRule.id });
    } else {
      const nextRule = makeTrigger(catalogState.stageId, item);
      setConfig((current) => (current ? { ...current, triggers: [...current.triggers, nextRule] } : current));
      setSelectedRule({ kind: "trigger", id: nextRule.id });
    }

    setSelectedStageId(catalogState.stageId);
    setCatalogState(null);
  };

  const handleSave = useCallback(async () => {
    if (!config || !selectedEventId) return false;
    const nextConfig = {
      ...config,
      scope,
      eventId: selectedEventId,
      stages: config.stages.length > 0 ? config.stages : createDefaultAutomationConfig(scope, selectedEventId).stages,
    };
    setLoading(true);
    try {
      const normalized = await writeAutomationConfigAsync(nextConfig);
      setConfig(normalized);
      setSavedSnapshot(JSON.stringify(normalized));
      onDirtyChange?.(false);
      showToast("success", TEXT.saved);
      return true;
    } catch {
      showToast("error", TEXT.saveError);
      return false;
    } finally {
      setLoading(false);
    }
  }, [config, onDirtyChange, scope, selectedEventId, showToast]);

  useImperativeHandle(
    ref,
    () => ({
      save: handleSave,
      hasUnsavedChanges: () => hasUnsavedChanges,
    }),
    [handleSave, hasUnsavedChanges]
  );

  const openCatalog = (kind: RuleKind, stageId: string) => {
    setSelectedStageId(stageId);
    setSelectedRule(null);
    setCatalogState({ kind, stageId });
  };

  const openRule = (rule: SelectedRule, stageId: string) => {
    setSelectedStageId(stageId);
    setCatalogState(null);
    setSelectedRule(rule);
  };

  const closeSidePanel = () => {
    setSelectedRule(null);
    setCatalogState(null);
  };

  const selectStage = (stageId: string) => {
    setSelectedStageId(stageId);
    setSelectedRule(null);
    setCatalogState(null);
  };

  const scopeText = SCOPE_TEXT[scope];

  return (
    <section className={`automation-panel automation-panel--${scope} ${className}`.trim()}>
      <div className="automation-panel__head">
        <div className="automation-panel__title">
          <span className="automation-panel__icon">
            <SettingOutlined />
          </span>
          <div>
            <div className="automation-panel__eyebrow">
              <Tag color="blue">{scopeText.badge}</Tag>
              <span>Автоматизация стадий</span>
            </div>
            <h2>{scopeText.title}</h2>
            <p>{scopeText.subtitle}</p>
          </div>
        </div>

        {(!hideEventSelector || !hideLocalSave) && (
          <div className="automation-panel__actions">
            {!hideEventSelector && (
              <label className="automation-panel__event">
                <span>{TEXT.event}</span>
                {lockedEventId ? (
                  <strong>{getEventTitle(selectedEvent)}</strong>
                ) : (
                  <AppSelect
                    value={selectedEventId ?? undefined}
                    placeholder={TEXT.event}
                    disabled={loading || events.length === 0}
                    onChange={(value) => setSelectedEventId(Number(value))}
                    options={events.map((event) => ({ value: Number(event.id), label: getEventTitle(event) }))}
                    showSearch
                    optionFilterProp="label"
                  />
                )}
              </label>
            )}

            {!hideLocalSave && (
              <AppButton className="automation-panel__save" onClick={handleSave} disabled={!config || loading}>
                <SaveOutlined />
                <span>{TEXT.save}</span>
              </AppButton>
            )}
          </div>
        )}
      </div>

      {loading ? (
        <div className="automation-panel__empty">
          <Spin />
        </div>
      ) : !config || !selectedEventId ? (
        <div className="automation-panel__empty">
          <Empty description={events.length === 0 ? TEXT.noEvents : scopeText.empty} />
        </div>
      ) : (
        <>
          <div className="automation-panel__summary">
            <div>
              <strong>{boardStats.active}</strong>
              <span>активных правил</span>
            </div>
            <div>
              <strong>{boardStats.triggers}</strong>
              <span>триггеров</span>
            </div>
            <div>
              <strong>{boardStats.robots}</strong>
              <span>роботов</span>
            </div>
          </div>

          <label className="automation-stage-picker">
            <span>Выберите статус</span>
            <AppSelect
              value={selectedStageId}
              onChange={(value) => selectStage(String(value))}
              options={config.stages.map((stage) => ({ value: stage.id, label: stage.title }))}
              showSearch
              optionFilterProp="label"
            />
          </label>

          <div className="automation-workspace">
            <AutomationBoard
              config={config}
              selectedStageId={selectedStageId}
              selectedRule={selectedRule}
              onStageSelect={selectStage}
              onAdd={openCatalog}
              onRuleSelect={openRule}
            />

            <aside className={`automation-side ${selectedRule || catalogState ? "is-open" : ""}`}>
              <AppButton className="automation-side__close" onClick={closeSidePanel} aria-label={TEXT.close}>
                <CloseOutlined />
              </AppButton>

              {catalogState ? (
                <CatalogPanel scope={scope} catalogState={catalogState} config={config} onSelect={addCatalogRule} />
              ) : selectedRobot && selectedRule?.kind === "robot" ? (
                <RobotEditor
                  robot={selectedRobot}
                  stageOptions={stageOptions}
                  eventId={selectedEventId}
                  onChange={(updater) => updateRobot(selectedRobot.id, updater)}
                  onDelete={() => deleteRule(selectedRule)}
                />
              ) : selectedTrigger && selectedRule?.kind === "trigger" ? (
                <TriggerEditor
                  trigger={selectedTrigger}
                  config={config}
                  stageOptions={stageOptions}
                  onChange={(updater) => updateTrigger(selectedTrigger.id, updater)}
                  onDelete={() => deleteRule(selectedRule)}
                />
              ) : (
                <div className="automation-side__placeholder">
                  <span>
                    <RobotOutlined />
                  </span>
                  <h3>{TEXT.selected}</h3>
                  <p>{TEXT.selectedHint}</p>
                </div>
              )}
            </aside>
          </div>
        </>
      )}
    </section>
  );
});

export default AutomationPanel;

