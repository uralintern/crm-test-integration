import client from "../../../api/client";
import { createNotification } from "../../../api/notifications";
import { buildMockRequestTransitionUrl, REQUEST_STATUS } from "../../../constants/requestProgress";
import { pushNotifications } from "../../../storage/notifications";
import { getAllUsers } from "../../../storage/storage";
import type { Event } from "../../../types/event";
import type { CreateNotificationInput } from "../../../types/notification";
import type { Request as ReqType } from "../../../types/request";
import type { User } from "../../../types/user";
import { updateRequestStatus as updateStoredRequestStatus } from "../../requests/storage/requests";
import type { AutomationConfig, AutomationRobot } from "../types";
import { rememberExecution, wasExecuted } from "./executionLog";
import type { RequestAutomationEvent } from "./requestAutomationTypes";
import { getStageStatus } from "./stageResolver";

function renderTemplate(template: string, request: ReqType, event?: Event) {
  const values: Record<string, string> = {
    student: request.studentName || "Проектант",
    event: request.eventTitle || event?.title || "мероприятие",
    status: request.status || "",
    direction: request.directionTitle || "",
    project: request.projectTitle || "",
  };

  return template.replace(/\{(student|event|status|direction|project)\}/g, (_, key: string) => values[key] || "");
}

async function getOrganizerIds(event?: Event) {
  const users = await getAllUsers().catch(() => [] as User[]);
  const explicitIds = new Set<number>();

  event?.organizerIds?.forEach((id) => {
    const numberId = Number(id);
    if (Number.isFinite(numberId)) explicitIds.add(numberId);
  });

  const leaderId = Number(event?.leader);
  if (Number.isFinite(leaderId)) explicitIds.add(leaderId);

  if (event?.organizer) {
    const organizerName = event.organizer.toLowerCase();
    users
      .filter((user) => `${user.name} ${user.surname}`.toLowerCase().includes(organizerName))
      .forEach((user) => explicitIds.add(Number(user.id)));
  }

  if (explicitIds.size > 0) return Array.from(explicitIds);
  return users.filter((user) => String(user.role).toLowerCase() === "organizer").map((user) => Number(user.id));
}

function buildStudentLink(robot: AutomationRobot, request: ReqType) {
  if (robot.action === "testing.link") {
    return buildMockRequestTransitionUrl(request.id, REQUEST_STATUS.CHAT_LINK_SENT, "testing");
  }

  if (isChatLinkAction(robot)) {
    return buildMockRequestTransitionUrl(request.id, REQUEST_STATUS.JOINED_CHAT, "chat");
  }

  return "/requests";
}

function isChatLinkAction(robot: AutomationRobot) {
  return robot.action === "message.vk_or_notification" || robot.action === "chat.link.vk";
}

function isBackendVkAction(robot: AutomationRobot) {
  return robot.action === "message.vk" || isChatLinkAction(robot);
}

function buildNotificationTitle(robot: AutomationRobot, request: ReqType, event?: Event) {
  const title = renderTemplate(robot.subject || robot.title, request, event).trim();
  const isGenericUserNotificationTitle = !title || title === "Уведомление" || title === "Отправить уведомление";

  if (robot.action !== "notification.user" || !isGenericUserNotificationTitle) {
    return title || "Уведомление";
  }

  const eventTitle = request.eventTitle || event?.title;
  return eventTitle ? `Обновление по заявке: ${eventTitle}` : "Обновление по заявке";
}

async function buildRobotNotifications(robot: AutomationRobot, request: ReqType, event?: Event) {
  const title = buildNotificationTitle(robot, request, event);
  let message = renderTemplate(robot.message || robot.description, request, event);

  if (robot.action === "notification.organizer" || robot.action === "notification.curator" || robot.action === "task.review") {
    const organizerIds = await getOrganizerIds(event);
    return organizerIds.map<CreateNotificationInput>((userId) => ({
      userId,
      title,
      message,
      link: "/requests",
    }));
  }

  if (
    robot.action === "testing.link" ||
    isChatLinkAction(robot) ||
    robot.action === "message.vk" ||
    robot.action === "notification.user" ||
    robot.action === "notification.assignee"
  ) {
    if (!request.ownerId) return [];
    message = message.replace(/\{chat_link\}/g, buildStudentLink(robot, request));
    return [
      {
        userId: Number(request.ownerId),
        title,
        message,
        link: buildStudentLink(robot, request),
      },
    ];
  }

  const organizerIds = await getOrganizerIds(event);
  return organizerIds.map<CreateNotificationInput>((userId) => ({
    userId,
    title,
    message,
    link: "/requests",
  }));
}

async function runWithTiming(robot: AutomationRobot, execute: () => Promise<void>) {
  const delayMinutes = Number(robot.settings.delayMinutes || 0);
  if (robot.settings.timing === "delayed" && delayMinutes > 0) {
    window.setTimeout(() => {
      void execute();
    }, delayMinutes * 60 * 1000);
    return;
  }

  await execute();
}

async function sendBackendApplicationVkMessage(robot: AutomationRobot, request: ReqType, event?: Event) {
  if (!request.id || client.USE_MOCK) return false;

  await client.post(`/api/integrations/vk/applications/${request.id}/message/`, {
    subject: "",
    message: renderTemplate(robot.message || robot.description, request, event),
    include_chat_link: isChatLinkAction(robot),
  });

  return true;
}

async function sendNotifications(notifications: CreateNotificationInput[]) {
  if (notifications.length === 0) return;

  if (client.USE_MOCK) {
    pushNotifications(notifications);
    return;
  }

  await Promise.all(notifications.map((notification) => createNotification(notification)));
}

export async function executeRobot(
  config: AutomationConfig,
  robot: AutomationRobot,
  eventItem: RequestAutomationEvent<ReqType>,
  event?: Event
) {
  const key = [
    config.scope,
    config.eventId,
    eventItem.request.id,
    eventItem.previousStatus || "none",
    eventItem.request.status || "none",
    robot.stageId,
    robot.id,
  ].join(":");

  if (wasExecuted(key)) return;
  rememberExecution(key);

  await runWithTiming(robot, async () => {
    if (robot.action === "status.change") {
      const targetStatus = robot.targetStatus || getStageStatus(config, robot.targetStageId || robot.stageId);
      if (targetStatus) {
        const updated = await updateStoredRequestStatus(eventItem.request.id, targetStatus);
        if (updated) eventItem.request = updated;
      }
      return;
    }

    if (isBackendVkAction(robot) && !client.USE_MOCK) {
      try {
        await sendBackendApplicationVkMessage(robot, eventItem.request, event);
      } catch {
      }
      return;
    }

    const notifications = await buildRobotNotifications(robot, eventItem.request, event);
    await sendNotifications(notifications);
  });
}
