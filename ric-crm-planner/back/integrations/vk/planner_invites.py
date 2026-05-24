import json
import logging
from typing import Any
from urllib.parse import urlparse

from django.conf import settings
from django.db import transaction

from users.models import Application, Profile, Status
from users.vk_profiles import confirm_profile_by_vk_user_id, refresh_profile_vk_user_id

from .crm_notifications import mark_application_joined_chat_by_vk_user, notify_organizers_about_vk_error
from .services import (
    VKAPIError,
    VKConfigurationError,
    answer_vk_message_event,
    delete_vk_message,
    send_vk_message,
)


logger = logging.getLogger(__name__)

PLANNER_INVITE_PAYLOAD_TYPE = "planner_invite"
CHAT_JOIN_ACTION_TYPES = {"chat_invite_user", "chat_invite_user_by_link"}
JOINED_CHAT_STATUS_NAME = "Добавился в орг. чат"
STARTED_PSH_STATUS_NAME = "Приступил к ПШ"
DECLINED_PSH_STATUS_NAME = "Отказался от ПШ"
REMOVED_FROM_PSH_STATUS_NAME = "Удален с ПШ"
PLANNER_INVITE_ACCEPT_ALLOWED_STATUSES = {JOINED_CHAT_STATUS_NAME, DECLINED_PSH_STATUS_NAME, REMOVED_FROM_PSH_STATUS_NAME}
START_COMMANDS = {"начать", "start", "/start", "старт"}
PEER_COMMANDS = {"peer", "/peer", "peer_id", "/peer_id"}


def resolve_application_status(name: str, *, description: str = "", is_positive: bool = True) -> Status:
    status_obj = Status.objects.filter(name=name).order_by("id").first()
    if status_obj:
        return status_obj

    return Status.objects.create(
        name=name,
        description=description,
        is_positive=is_positive,
    )


def resolve_vk_application_user_id(application: Application, *, require_confirmed: bool = True) -> int | None:
    profile = Profile.objects.filter(user=application.user).only("vk", "vk_user_id", "vk_confirmed_at").first()
    if not profile:
        return None
    if require_confirmed and not profile.vk_confirmed_at:
        return None
    return refresh_profile_vk_user_id(profile)


def vk_button(label: str, color: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": {
            "type": "callback",
            "label": label,
            "payload": payload,
        },
        "color": color,
    }


def build_inline_keyboard(rows: list[list[dict[str, Any]]]) -> dict[str, Any]:
    return {
        "inline": True,
        "buttons": rows,
    }


def build_welcome_keyboard() -> dict[str, Any] | None:
    frontend_url = settings.VK_BOT_FRONTEND_URL.rstrip("/")
    parsed_frontend_url = urlparse(frontend_url)
    if parsed_frontend_url.scheme != "https" or not parsed_frontend_url.netloc:
        return None

    return build_inline_keyboard(
        [
            [
                {
                    "action": {
                        "type": "open_link",
                        "label": "Открыть CRM",
                        "link": frontend_url,
                    },
                }
            ]
        ]
    )


def planner_invite_payload(application_id: int, action: str) -> dict[str, Any]:
    return {
        "type": PLANNER_INVITE_PAYLOAD_TYPE,
        "action": action,
        "application_id": application_id,
    }


def build_planner_invite_keyboard(application_id: int) -> dict[str, Any]:
    return build_inline_keyboard(
        [
            [
                vk_button("Принять", "positive", planner_invite_payload(application_id, "accept")),
                vk_button("Отказаться", "negative", planner_invite_payload(application_id, "decline")),
            ]
        ]
    )


def build_decline_confirmation_keyboard(application_id: int) -> dict[str, Any]:
    return build_inline_keyboard(
        [
            [
                vk_button("Да", "negative", planner_invite_payload(application_id, "decline_confirm")),
                vk_button("Нет", "secondary", planner_invite_payload(application_id, "decline_cancel")),
            ]
        ]
    )


def build_planner_invite_message(application: Application) -> str:
    event_name = application.event.name if application.event_id and application.event else "мероприятие"
    return (
        f'Набор по мероприятию "{event_name}" завершён. '
        "Подтвердите готовность перейти к работе в планировщике."
    )


def send_planner_invite(application: Application, *, message: str = "", keyboard: dict[str, Any] | None = None) -> int:
    vk_user_id = resolve_vk_application_user_id(application)
    if not vk_user_id:
        raise ValueError("проектант не подтвердил VK-бота или указал некорректный VK")

    return send_vk_message(
        user_id=vk_user_id,
        message=message or build_planner_invite_message(application),
        keyboard=keyboard or build_planner_invite_keyboard(application.id),
    )


def send_planner_invites_for_event(
    event_id: int,
    *,
    recipient_mode: str = "joined",
    message: str = "",
) -> dict[str, int]:
    if not settings.VK_ENABLED:
        return {"sent": 0, "failed": 0, "skipped": 0}

    applications = (
        Application.objects.select_related("user", "event", "event__leader", "status")
        .prefetch_related("event__organizers")
        .filter(event_id=event_id)
    )
    if recipient_mode == "declined":
        applications = applications.filter(status__name__in=[DECLINED_PSH_STATUS_NAME, REMOVED_FROM_PSH_STATUS_NAME])
    elif recipient_mode == "joined":
        applications = applications.filter(status__name=JOINED_CHAT_STATUS_NAME)

    result = {"sent": 0, "failed": 0, "skipped": 0}
    for application in applications:
        try:
            send_planner_invite(application, message=message)
            result["sent"] += 1
        except (VKConfigurationError, VKAPIError, ValueError) as exc:
            result["failed"] += 1
            notify_organizers_about_vk_error(application, str(exc))

    return result


def parse_vk_button_payload(raw_payload: Any) -> dict[str, Any] | None:
    if isinstance(raw_payload, dict):
        return raw_payload
    if not isinstance(raw_payload, str) or not raw_payload.strip():
        return None

    try:
        parsed = json.loads(raw_payload)
    except json.JSONDecodeError:
        return None

    return parsed if isinstance(parsed, dict) else None


def is_vk_start_message(message: dict[str, Any]) -> bool:
    raw_text = str(message.get("text") or "").strip().lower()
    if raw_text in START_COMMANDS:
        return True

    payload = parse_vk_button_payload(message.get("payload"))
    if not payload:
        return False

    payload_values = {
        str(payload.get("command") or "").strip().lower(),
        str(payload.get("type") or "").strip().lower(),
        str(payload.get("action") or "").strip().lower(),
    }
    return bool(payload_values & START_COMMANDS)


def handle_vk_peer_debug_message(message: dict[str, Any]) -> bool:
    raw_text = str(message.get("text") or "").strip().lower()
    if raw_text not in PEER_COMMANDS:
        return False

    try:
        peer_id = int(message.get("peer_id"))
    except (TypeError, ValueError):
        return True

    if peer_id < 2_000_000_000:
        return False

    send_vk_message(
        peer_id=peer_id,
        message=f"ID этой беседы для CRM: {peer_id}",
    )
    logger.warning("VK peer debug command handled: peer_id=%s", peer_id)
    return True


def handle_vk_chat_join_message(message: dict[str, Any]) -> bool:
    action = message.get("action")
    if not isinstance(action, dict):
        return False

    action_type = str(action.get("type") or "").strip()
    if action_type not in CHAT_JOIN_ACTION_TYPES:
        return False

    member_id = action.get("member_id") or message.get("from_id")
    try:
        vk_user_id = int(member_id)
    except (TypeError, ValueError):
        return True

    try:
        peer_id = int(message.get("peer_id") or 0) or None
    except (TypeError, ValueError):
        peer_id = None

    application = mark_application_joined_chat_by_vk_user(vk_user_id=vk_user_id, peer_id=peer_id)
    if application:
        logger.warning(
            "VK chat join detected: vk_user_id=%s peer_id=%s application_id=%s",
            vk_user_id,
            peer_id,
            application.id,
        )
    else:
        logger.warning(
            "VK chat join ignored: vk_user_id=%s peer_id=%s no matching application",
            vk_user_id,
            peer_id,
        )
    return True


def handle_vk_message_new_event(callback_payload: dict[str, Any]) -> bool:
    vk_object = callback_payload.get("object")
    if not isinstance(vk_object, dict):
        return False

    message = vk_object.get("message")
    if not isinstance(message, dict):
        return False

    if handle_vk_chat_join_message(message):
        return True

    if handle_vk_peer_debug_message(message):
        return True

    button_payload = parse_vk_button_payload(message.get("payload"))
    if not button_payload or button_payload.get("type") != PLANNER_INVITE_PAYLOAD_TYPE:
        return handle_vk_start_message(message)

    try:
        from_id = int(message.get("from_id"))
    except (TypeError, ValueError):
        return True

    handle_planner_invite_payload(from_id=from_id, payload=button_payload)
    return True


def handle_vk_start_message(message: dict[str, Any]) -> bool:
    if not is_vk_start_message(message):
        return False

    try:
        from_id = int(message.get("from_id"))
    except (TypeError, ValueError):
        return True

    profile = confirm_profile_by_vk_user_id(from_id)
    if profile:
        message = (
            "VK подтвержден. Теперь бот сможет отправлять вам сообщения по заявкам, "
            "организационному чату и планировщику."
        )
    else:
        message = (
            "Привет! Это бот CRM проектной школы.\n\n"
            "Не удалось связать ваш VK с профилем CRM. Проверьте, что в профиле указан именно этот аккаунт VK, "
            "затем нажмите «Начать» еще раз."
        )

    send_vk_message(user_id=from_id, message=message, keyboard=build_welcome_keyboard())
    return True


def handle_vk_message_event(callback_payload: dict[str, Any]) -> bool:
    vk_object = callback_payload.get("object")
    if not isinstance(vk_object, dict):
        return False

    button_payload = parse_vk_button_payload(vk_object.get("payload"))
    if not button_payload or button_payload.get("type") != PLANNER_INVITE_PAYLOAD_TYPE:
        return False

    try:
        from_id = int(vk_object.get("user_id"))
    except (TypeError, ValueError):
        return True

    event_id = str(vk_object.get("event_id") or "")
    try:
        peer_id = int(vk_object.get("peer_id") or from_id)
    except (TypeError, ValueError):
        peer_id = from_id
    try:
        conversation_message_id = int(vk_object.get("conversation_message_id") or 0) or None
    except (TypeError, ValueError):
        conversation_message_id = None
    try:
        message_id = int(vk_object.get("message_id") or 0) or None
    except (TypeError, ValueError):
        message_id = None

    # VK keeps the button in loading state until it receives this answer.
    # Send it before any business logic or follow-up messages.
    try:
        answer_vk_message_event(
            event_id=event_id,
            user_id=from_id,
            peer_id=peer_id,
            text="Действие принято",
        )
    except (VKConfigurationError, VKAPIError):
        pass

    try:
        delete_vk_message(
            peer_id=peer_id,
            message_id=message_id,
            conversation_message_id=conversation_message_id,
        )
    except (VKConfigurationError, VKAPIError):
        pass

    handle_planner_invite_payload(from_id=from_id, payload=button_payload)
    return True


def handle_planner_invite_payload(*, from_id: int, payload: dict[str, Any]) -> str:
    action = str(payload.get("action", "")).strip()
    try:
        application_id = int(payload.get("application_id"))
    except (TypeError, ValueError):
        send_vk_message(user_id=from_id, message="Не удалось определить заявку для этого действия.")
        return "Заявка не определена"

    application = (
        Application.objects.select_related("user", "event", "event__leader", "status")
        .prefetch_related("event__organizers")
        .filter(pk=application_id)
        .first()
    )
    if not application:
        send_vk_message(user_id=from_id, message="Заявка для этого действия не найдена.")
        return "Заявка не найдена"

    expected_user_id = resolve_vk_application_user_id(application)
    if expected_user_id != from_id:
        send_vk_message(user_id=from_id, message="Эта кнопка относится к другой заявке.")
        return "Кнопка относится к другой заявке"

    if action == "accept":
        return accept_planner_invite(application, from_id)

    if action == "decline":
        send_vk_message(
            user_id=from_id,
            message="Вы уверены, что хотите отказаться от участия в проектной школе?",
            keyboard=build_decline_confirmation_keyboard(application.id),
        )
        return "Подтвердите отказ"

    if action == "decline_confirm":
        return decline_planner_invite(application, from_id)

    if action == "decline_cancel":
        send_vk_message(
            user_id=from_id,
            message="Отказ отменён. Если готовы начать работу, нажмите «Принять».",
            keyboard=build_planner_invite_keyboard(application.id),
        )
        return "Отказ отменён"

    return "Неизвестное действие"


@transaction.atomic
def accept_planner_invite(application: Application, vk_user_id: int) -> str:
    locked_application = Application.objects.select_for_update().get(pk=application.pk)
    if locked_application.status_id and locked_application.status.name == STARTED_PSH_STATUS_NAME:
        send_vk_message(user_id=vk_user_id, message="Вы уже подтвердили готовность. Статус заявки: «Приступил к ПШ».")
        return "Готовность уже подтверждена"

    current_status = locked_application.status.name if locked_application.status_id else "без статуса"
    if current_status not in PLANNER_INVITE_ACCEPT_ALLOWED_STATUSES:
        send_vk_message(
            user_id=vk_user_id,
            message=(
                f"Не удалось подтвердить участие: текущий статус заявки «{current_status}». "
                f"Подтверждение доступно только после статуса «{JOINED_CHAT_STATUS_NAME}» "
                f"или для повторного приглашения после статуса «{DECLINED_PSH_STATUS_NAME}»."
            ),
        )
        return "Статус заявки не позволяет подтвердить участие"

    started_status = resolve_application_status(
        STARTED_PSH_STATUS_NAME,
        description="Проектант подтвердил готовность приступить к проектной школе.",
        is_positive=True,
    )
    locked_application.status = started_status
    locked_application.save(update_fields=["status"])
    send_vk_message(
        user_id=vk_user_id,
        message="Готовность подтверждена. Статус заявки изменён на «Приступил к ПШ».",
    )
    return "Готовность подтверждена"


@transaction.atomic
def decline_planner_invite(application: Application, vk_user_id: int) -> str:
    locked_application = Application.objects.select_for_update().get(pk=application.pk)
    if locked_application.status_id and locked_application.status.name == DECLINED_PSH_STATUS_NAME:
        send_vk_message(user_id=vk_user_id, message="Отказ уже зафиксирован. Статус заявки: «Отказался от ПШ».")
        return "Отказ уже зафиксирован"

    current_status = locked_application.status.name if locked_application.status_id else "без статуса"
    if current_status != JOINED_CHAT_STATUS_NAME:
        send_vk_message(
            user_id=vk_user_id,
            message=(
                f"Не удалось отказаться от участия: текущий статус заявки «{current_status}». "
                f"Отказ доступен только после статуса «{JOINED_CHAT_STATUS_NAME}»."
            ),
        )
        return "Статус заявки не позволяет отказаться"

    declined_status = resolve_application_status(
        DECLINED_PSH_STATUS_NAME,
        description="Проектант отказался от участия после приглашения в планировщик.",
        is_positive=False,
    )
    locked_application.status = declined_status
    locked_application.save(update_fields=["status"])
    send_vk_message(
        user_id=vk_user_id,
        message="Отказ зафиксирован. Статус заявки изменён на «Отказался от ПШ».",
    )
    return "Отказ зафиксирован"
