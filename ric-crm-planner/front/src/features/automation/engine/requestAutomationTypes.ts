export type RequestAutomationEventCode =
  | "application.created"
  | "request.status_changed"
  | "testing.started"
  | "testing.completed"
  | "notification.chat_link_opened"
  | "notification.link_opened"
  | "field.changed";

export type RequestAutomationEvent<RequestType> = {
  code: RequestAutomationEventCode;
  request: RequestType;
  previousStatus?: string;
};
