import type { Event } from "../../../../types/event";

export type WizardMode = "create" | "edit";
export type WizardTab = "event" | "directions" | "projects" | "form";

export type WizardPage = "events" | "directions" | "projects";

export interface ProjectModel {
  id: number;
  title?: string;
  description?: string;
  curator?: string;
  curatorId?: number;
  teams?: number;
  directionId?: number | string;
}

export interface DirectionModel {
  id: number;
  title: string;
  description?: string;
  organizer?: string;
  projects?: ProjectModel[];
}

export interface WizardContextState {
  mode: WizardMode;
  activeTab: WizardTab;
  page: WizardPage;

  eventId?: number;
  directionId?: number;
  projectId?: number;

  setActiveTab: (tab: WizardTab) => void;

  isEventSaved?: boolean;
  saveEvent?: (data: Event) => void;

  savedDirections?: DirectionModel[];
  savedEvent?: Event | null;
  isDirectionsSaved?: boolean;
  saveDirections?: (dirs: DirectionModel[]) => void;

  hasUnsavedDirections?: boolean;
  setHasUnsavedDirections?: (value: boolean) => void;
  hasUnsavedProjects?: boolean;
  setHasUnsavedProjects?: (value: boolean) => void;
  hasUnsavedAutomation?: boolean;
  setHasUnsavedAutomation?: (value: boolean) => void;
}

