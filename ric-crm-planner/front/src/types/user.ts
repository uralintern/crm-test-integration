export interface User {
  id: number;
  email: string;
  name: string;
  surname: string;
  role: "student" | "organizer" | string;
  vk?: string;
  vkConfirmed?: boolean;
  vkBotUrl?: string;
  isSuperuser?: boolean;
  isStaff?: boolean;
  password?: string;
}
