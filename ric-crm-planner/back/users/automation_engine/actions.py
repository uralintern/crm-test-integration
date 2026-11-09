"""Действия роботов: уведомления, смена статуса, VK, вложения."""

from typing import Any
from integrations.vk.crm_notifications import (
    CHAT_LINK_PLACEHOLDER,
    inject_application_chat_link,
    mark_application_joined_chat_if_member,
    notify_organizers_about_vk_error,
    send_application_vk_message,
    upload_application_vk_documents,
)
from integrations.vk.planner_invites import send_planner_invite, send_start_message
from integrations.vk.services import VKAPIError, VKConfigurationError
from users.models import (
    Application,
    CRMAutomationAttachment,
    CRMAutomationConfig,
    CRMAutomationExecutionLog,
    Notification,
    Status,
)
from .utils import normalized_text, to_int
from .events import CRMAutomationEvent
from .config import config_model_to_dict, target_status_for_stage
from .conditions import application_status, render_template
from .logs import create_log, log_exists, should_delay


def get_application_organizers(application: Application):
    if not application.event_id:
        return []
    recipients = list(application.event.organizers.all())
    if application.event.leader_id and all(recipient.id != application.event.leader_id for recipient in recipients):
        recipients.append(application.event.leader)
    return [recipient for recipient in recipients if recipient]


def create_notification(user_id: int | None, title: str, message: str, link: str = "/requests") -> bool:
    if not user_id:
        return False
    Notification.objects.create(user_id=user_id, title=title[:255], message=message, link=link)
    return True


def create_organizer_notifications(application: Application, title: str, message: str) -> int:
    created = 0
    for organizer in get_application_organizers(application):
        Notification.objects.create(user=organizer, title=title[:255], message=message, link="/requests")
        created += 1
    return created


def update_application_status(application: Application, status_name: str) -> bool:
    if not status_name or application_status(application) == status_name:
        return False
    status_obj, _ = Status.objects.get_or_create(name=status_name, defaults={"description": "", "is_positive": True})
    application.status = status_obj
    application.save(update_fields=["status"])
    return True


def robot_attachment_ids(robot: dict[str, Any]) -> list[int]:
    raw_attachments = robot.get("attachments") if isinstance(robot.get("attachments"), list) else []
    ids: list[int] = []
    for attachment in raw_attachments:
        if isinstance(attachment, dict):
            attachment_id = to_int(attachment.get("id"))
        else:
            attachment_id = to_int(attachment)
        if attachment_id and attachment_id not in ids:
            ids.append(attachment_id)
    return ids


def get_robot_attachments(robot: dict[str, Any], event_id: int):
    ids = robot_attachment_ids(robot)
    if not ids:
        return []
    attachments_by_id = {
        attachment.id: attachment
        for attachment in CRMAutomationAttachment.objects.filter(event_id=event_id, id__in=ids)
    }
    return [attachments_by_id[attachment_id] for attachment_id in ids if attachment_id in attachments_by_id]


def run_robot_action(
    config_model: CRMAutomationConfig,
    robot: dict[str, Any],
    event: CRMAutomationEvent,
    *,
    force_immediate: bool = False,
) -> bool:
    if log_exists(config_model, event, robot, "robot") and not force_immediate:
        return False

    if not force_immediate:
        delayed, scheduled_for = should_delay(robot)
        if delayed:
            create_log(
                config_model=config_model,
                event=event,
                rule=robot,
                rule_kind="robot",
                status=CRMAutomationExecutionLog.STATUS_PENDING,
                message="Запланировано отложенное выполнение робота.",
                scheduled_for=scheduled_for,
            )
            return False

    action = normalized_text(robot.get("action"))
    if action == "message.vk_interactive":
        action = "message.vk"
    title = render_template(robot.get("subject") or robot.get("title", ""), event) or "Уведомление"
    message = render_template(robot.get("message") or robot.get("description", ""), event)
    success = False
    log_message = ""

    if action in {"notification.organizer", "notification.curator"}:
        success = create_organizer_notifications(event.application, title, message) > 0
        log_message = "Уведомления отправлены организаторам." if success else "Организаторы не найдены."
    elif action in {"notification.user", "notification.assignee", "testing.link"}:
        notification_link = f"/testing?applicationId={event.application.id}" if action == "testing.link" else "/requests"
        success = create_notification(event.application.user_id, title, message, link=notification_link)
        log_message = "Уведомление отправлено проектанту." if success else "Проектант не найден."
    elif action == "file.vk":
        try:
            documents = get_robot_attachments(robot, event.event_id)
            if not documents:
                log_message = "Файлы для VK-робота не выбраны."
            else:
                vk_attachments = upload_application_vk_documents(event.application, documents)
                print(f"VK file robot attachments: application_id={event.application.id} attachments={vk_attachments}")
                send_application_vk_message(
                    event.application,
                    message or "Вам отправлены файлы по заявке.",
                    attachments=vk_attachments,
                )
                success = True
                log_message = "VK-файлы отправлены проектанту."
        except (VKConfigurationError, VKAPIError, ValueError) as exc:
            notify_organizers_about_vk_error(event.application, str(exc))
            log_message = str(exc)
    elif action == "planner.invite.vk":
        try:
            send_planner_invite(event.application, message=message)
            success = True
            log_message = "VK-приглашение в планировщик отправлено проектанту."
        except (VKConfigurationError, VKAPIError, ValueError) as exc:
            notify_organizers_about_vk_error(event.application, str(exc))
            log_message = str(exc)
    elif action == "planner.start.vk":
        try:
            send_start_message(event.application, message=message)
            success = True
            log_message = "VK-Сообщение Старта"
        except (VKConfigurationError, VKAPIError, ValueError) as exc:
            log_message = str(exc)
    elif action == "status.change":
        target_stage_id = normalized_text(robot.get("targetStageId"))
        target_status = normalized_text(robot.get("targetStatus")) or target_status_for_stage(
            config_model_to_dict(config_model),
            target_stage_id,
        )
        success = update_application_status(event.application, target_status)
        if success:
            event.application.refresh_from_db()
        log_message = (
            f"Заявка переведена в статус «{target_status}»."
            if success
            else "Статус заявки не изменился."
        )
    elif action in {"message.vk", "chat.link.vk", "message.vk_or_notification"}:
        try:
            if action == "chat.link.vk" and mark_application_joined_chat_if_member(event.application):
                event.application.refresh_from_db()
                success = True
                log_message = "Проектант уже состоит в орг. чате, отправка ссылки пропущена."
            else:
                vk_message = message
                if action in {"chat.link.vk", "message.vk_or_notification"} or CHAT_LINK_PLACEHOLDER in vk_message:
                    vk_message = inject_application_chat_link(vk_message, event.application, event.request)
                send_application_vk_message(event.application, vk_message)
                success = True
                log_message = "VK-сообщение отправлено проектанту."
        except (VKConfigurationError, VKAPIError, ValueError) as exc:
            notify_organizers_about_vk_error(event.application, str(exc))
            log_message = str(exc)
    else:
        log_message = f"Действие робота {action} пока не поддерживается."

    if not force_immediate:
        create_log(
            config_model=config_model,
            event=event,
            rule=robot,
            rule_kind="robot",
            status=CRMAutomationExecutionLog.STATUS_SUCCESS if success else CRMAutomationExecutionLog.STATUS_SKIPPED,
            message=log_message,
        )
    return success
