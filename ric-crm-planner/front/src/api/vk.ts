import client from "./client";

export type VKBotStatus = {
  confirmed: boolean;
  vk?: string;
  vkUserId?: number | null;
  botUrl?: string;
};

type BackendVKBotStatus = {
  confirmed?: boolean;
  vk?: string;
  vk_user_id?: number | null;
  vkUserId?: number | null;
  bot_url?: string;
  botUrl?: string;
};

export async function getVKBotStatus(): Promise<VKBotStatus> {
  const raw = await client.get<BackendVKBotStatus>("/api/integrations/vk/bot-status/");
  return {
    confirmed: Boolean(raw.confirmed),
    vk: raw.vk || "",
    vkUserId: raw.vkUserId ?? raw.vk_user_id ?? null,
    botUrl: raw.botUrl || raw.bot_url || "",
  };
}
