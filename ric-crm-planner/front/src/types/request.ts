export interface Request {
  id: number;
  studentName: string;
  telegram?: string;
  university?: string;
  course?: string;
  projectId?: number;
  projectTitle?: string;
  eventId?: number;
  eventTitle?: string;
  directionId?: number;
  directionTitle?: string;
  specializationId?: number;
  specialization?: string;
  about?: string;
  customFields?: Record<string, string>;
  status?: string;
  statusId?: number;
  ownerId?: number;
  createdAt?: string;
}
