export interface Specialization {
  id: number;
  title: string;
}

export type ApplicationFormFieldType = "text" | "textarea" | "select";

export interface ApplicationFormField {
  id: string;
  label: string;
  type: ApplicationFormFieldType;
  options?: string[];
  required?: boolean;
  locked?: boolean;
  system?: boolean;
}

export interface Event {
  id: number;
  title?: string;
  description?: string;
  startDate?: string;
  endDate?: string;
  applyDeadline?: string;
  leader?: number | string;
  organizerIds?: Array<number | string>;
  organizer?: string;
  specializations?: Specialization[];
  status?: string;
  archived?: boolean;
  archivedAt?: string;
  orgChatUrl?: string;
  orgChatPeerId?: number | string;
  applicationFormFields?: ApplicationFormField[];
}
