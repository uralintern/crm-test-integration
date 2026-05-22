import type { Project } from "./project";

export interface Direction {
  id: number;
  title: string;
  description?: string;
  organizer?: string;
  leader?: number | string;
  eventId?: number;
  projects?: Project[];
}
