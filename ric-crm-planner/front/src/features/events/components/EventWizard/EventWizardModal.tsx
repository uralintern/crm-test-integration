import { SettingOutlined } from "@ant-design/icons";
import { Modal as AntModal } from "antd";
import { createContext, useContext, useRef, useState } from "react";
import "./event-wizard.scss";

import EventForm from "./forms/EventForm";
import DirectionForm from "./forms/DirectionForm";
import ProjectForm from "./forms/ProjectForm";
import FormBuilderForm from "./forms/FormBuilderForm";
import AutomationPanel from "../../../automation/components/AutomationPanel";
import { useToast } from "../../../../components/Toast/ToastProvider";

import type { AutomationPanelHandle } from "../../../automation/types";
import type { DirectionModel, WizardContextState, WizardMode, WizardPage, WizardTab } from "./types";
import type { Event } from "../../../../types/event";
import AppButton from "../../../../components/UI/Button";

export interface WizardLaunchContext {
  type?: string;
  eventId?: number;
  directionId?: number;
  projectId?: number;
}

interface Props {
  mode: WizardMode;
  page?: WizardPage;
  context?: WizardLaunchContext;
  initialEventId?: number;
  initialDirectionId?: number;
  onClose: () => void;
}

export const WizardContext = createContext<WizardContextState | null>(null);

export function useWizard() {
  const ctx = useContext(WizardContext);
  if (!ctx) throw new Error("useWizard must be used inside WizardContext");
  return ctx;
}

export default function EventWizardModal({
  mode,
  page,
  context,
  initialEventId,
  initialDirectionId,
  onClose,
}: Props) {
  const resolvedPage: WizardPage =
    page ??
    (context?.type === "event"
      ? "events"
      : context?.type === "direction"
        ? "directions"
        : context?.type === "projects" || context?.type === "project"
          ? "projects"
          : "events");

  const initialTab: WizardTab =
    resolvedPage === "projects" ? "projects" : resolvedPage === "directions" ? "directions" : "event";

  const [activeTab, setActiveTab] = useState<WizardTab>(initialTab);
  const [isEventSaved, setIsEventSaved] = useState(false);
  const [savedEvent, setSavedEvent] = useState<Event | null>(null);
  const [savedDirections, setSavedDirections] = useState<DirectionModel[]>([]);
  const [isDirectionsSaved, setIsDirectionsSaved] = useState(false);
  const [eventIdState, setEventIdState] = useState<number | undefined>(initialEventId ?? context?.eventId);
  const [automationOpen, setAutomationOpen] = useState(false);
  const [hasUnsavedDirections, setHasUnsavedDirections] = useState(false);
  const [hasUnsavedProjects, setHasUnsavedProjects] = useState(false);
  const [hasUnsavedAutomation, setHasUnsavedAutomation] = useState(false);
  const automationPanelRef = useRef<AutomationPanelHandle | null>(null);
  const { showToast } = useToast();

  const automationEventId = Number(eventIdState ?? savedEvent?.id ?? 0) || null;

  const saveEvent = (data: Event) => {
    setSavedEvent(data);
    setIsEventSaved(true);
    if (data?.id) setEventIdState(Number(data.id));
  };

  const saveDirections = (dirs: DirectionModel[]) => {
    setSavedDirections(dirs);
    setIsDirectionsSaved(dirs.length > 0);
    setHasUnsavedDirections(false);
  };

  const getUnsavedMessage = () => {
    if (activeTab === "directions" && hasUnsavedDirections) return "Вы не сохранили изменения";
    if (activeTab === "projects" && hasUnsavedProjects) return "Вы не сохранили изменения";
    if (hasUnsavedAutomation) return "Вы не сохранили настройки роботов и триггеров";
    return "";
  };

  const requestTabChange = (tab: WizardTab) => {
    if (tab === activeTab) return;
    const unsavedMessage = getUnsavedMessage();
    if (unsavedMessage) {
      showToast("error", unsavedMessage);
      return;
    }
    setActiveTab(tab);
  };

  const requestClose = () => {
    const unsavedMessage = getUnsavedMessage();
    if (unsavedMessage) {
      showToast("error", unsavedMessage);
      return;
    }
    onClose();
  };

  const requestAutomationClose = () => {
    if (hasUnsavedAutomation) {
      showToast("error", "Вы не сохранили настройки роботов и триггеров");
      return;
    }
    setAutomationOpen(false);
  };

  const saveAutomationSettings = async () => {
    const saved = await automationPanelRef.current?.save();
    if (saved) {
      setHasUnsavedAutomation(false);
      setAutomationOpen(false);
    }
  };

  const ctxValue: WizardContextState = {
    mode,
    activeTab,
    page: resolvedPage,
    eventId: eventIdState,
    directionId: initialDirectionId ?? context?.directionId,
    projectId: context?.projectId,
    setActiveTab: requestTabChange,
    isEventSaved,
    saveEvent,
    savedEvent,
    savedDirections,
    isDirectionsSaved,
    saveDirections,
    hasUnsavedDirections,
    setHasUnsavedDirections,
    hasUnsavedProjects,
    setHasUnsavedProjects,
    hasUnsavedAutomation,
    setHasUnsavedAutomation,
  };

  return (
    <WizardContext.Provider value={ctxValue}>
      <div className="wizard-overlay" onClick={requestClose}>
        <div className={`wizard wizard-tab--${activeTab}`} onClick={(event) => event.stopPropagation()}>
          <AppButton className="wizard-close" aria-label="Закрыть" onClick={requestClose}>
            x
          </AppButton>

          <aside className="wizard-nav">
            <NavButton tab="event" label="Настройка мероприятия" />
            <NavButton tab="directions" label="Настройка направлений" />
            <NavButton tab="projects" label="Настройка проектов" />
            <NavButton tab="form" label="Конструктор формы" />
            <AppButton
              type="button"
              className="wizard-nav-btn wizard-nav-btn--automation"
              onClick={() => {
                if (!automationEventId) {
                  showToast("error", "Сначала сохраните настройки мероприятия.");
                  return;
                }
                setAutomationOpen(true);
              }}
            >
              <SettingOutlined />
              <span>Роботы и триггеры</span>
            </AppButton>
          </aside>

          <section className="wizard-content">
            {activeTab === "event" && <EventForm />}
            {activeTab === "directions" && <DirectionForm />}
            {activeTab === "projects" && <ProjectForm />}
            {activeTab === "form" && <FormBuilderForm />}
          </section>
        </div>
      </div>

      <AntModal
        open={automationOpen}
        onCancel={requestAutomationClose}
        footer={
          <div className="automation-settings-modal__footer">
            <AppButton className="close-btn" onClick={requestAutomationClose}>
              Закрыть
            </AppButton>
            <AppButton className="btn-send" onClick={() => void saveAutomationSettings()}>
              Сохранить настройки
            </AppButton>
          </div>
        }
        width="min(1380px, calc(100vw - 32px))"
        centered
        zIndex={1400}
        destroyOnHidden
        className="automation-settings-modal"
        title="Настройка роботов и триггеров CRM"
      >
        {automationEventId && (
          <AutomationPanel
            ref={automationPanelRef}
            scope="crm"
            lockedEventId={automationEventId}
            className="automation-panel--modal"
            hideLocalSave
            hideEventSelector
            onDirtyChange={setHasUnsavedAutomation}
          />
        )}
      </AntModal>
    </WizardContext.Provider>
  );
}

function NavButton({ tab, label }: { tab: WizardTab; label: string }) {
  const {
    activeTab,
    setActiveTab,
    mode,
    isEventSaved,
    isDirectionsSaved,
    eventId,
    directionId,
    hasUnsavedDirections,
    hasUnsavedProjects,
  } = useWizard();
  const { showToast } = useToast();

  const handleClick = () => {
    if (activeTab !== tab && ((activeTab === "directions" && hasUnsavedDirections) || (activeTab === "projects" && hasUnsavedProjects))) {
      showToast("error", "Вы не сохранили изменения");
      return;
    }

    if (mode === "create") {
      if ((tab === "directions" || tab === "projects" || tab === "form") && !isEventSaved && !eventId) {
        showToast("error", "Сначала сохраните настройки мероприятия.");
        return;
      }

      if (tab === "projects" && !isDirectionsSaved && !directionId) {
        showToast("error", "Добавьте и сохраните хотя бы одно направление перед переходом к проектам.");
        return;
      }
    }

    setActiveTab(tab);
  };

  return (
    <AppButton
      type="button"
      className={`wizard-nav-btn ${activeTab === tab ? "active" : ""} wizard-nav-btn--${tab}`}
      onClick={handleClick}
    >
      {label}
    </AppButton>
  );
}


