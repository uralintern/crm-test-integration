import logging

from django.conf import settings
from django.core import signing
from django.urls import reverse
from urllib.parse import parse_qs, urlparse

from users.models import Application, Notification, Profile, Status

from .services import VKAPIError, VKConfigurationError, is_vk_user_in_conversation, send_vk_message
from users.vk_profiles import refresh_profile_vk_user_id


TESTING_STATUS_NAME = "Прохождение тестирования"
CHAT_LINK_SENT_STATUS_NAME = "Отправлена ссылка на орг. чат"
CHAT_JOINED_STATUS_NAME = "Добавился в орг. чат"
CHAT_LINK_SALT = "vk-application-chat-link"
CHAT_LINK_PLACEHOLDER = "{chat_link}"
VK_CHAT_PEER_OFFSET = 2_000_000_000
logger = logging.getLogger(__name__)


def build_testing_started_message(application: Application) -> str:
    event_name = application.event.name if application.event_id else "мероприятие"
    return (
        f'Ваша заявка на мероприятие "{event_name}" переведена на этап тестирования. '
        "Ожидайте инструкции по прохождению теста."
    )


def get_application_organizers(application: Application):
    if not application.event_id:
        return []

    recipients = list(application.event.organizers.all())
    if application.event.leader_id and all(recipient.id != application.event.leader_id for recipient in recipients):
        recipients.append(application.event.leader)
    return [recipient for recipient in recipients if recipient]


def notify_organizers_about_vk_error(application: Application, reason: str) -> None:
    student_name = application.user.get_full_name() or application.user.email or str(application.user)
    event_name = application.event.name if application.event_id else "мероприятие"

    for organizer in get_application_organizers(application):
        Notification.objects.create(
            user=organizer,
            title="Ошибка отправки VK",
            message=(
                f"Не удалось отправить VK-сообщение проектанту {student_name} "
                f'по заявке на мероприятие "{event_name}". Причина: {reason}'
            ),
            link="/requests",
        )


def notify_organizers_about_chat_join(application: Application) -> None:
    student_name = application.user.get_full_name() or application.user.email or str(application.user)
    event_name = application.event.name if application.event_id else "мероприятие"

    for organizer in get_application_organizers(application):
        Notification.objects.create(
            user=organizer,
            title="Проектант перешел в орг.чат",
            message=f'Проектант {student_name} перешел по ссылке на орг.чат мероприятия "{event_name}".',
            link="/requests",
        )


def resolve_vk_chat_peer_id(chat_url: str) -> int | None:
    if not chat_url:
        return None

    raw_value = str(chat_url).strip()
    if raw_value.isdigit():
        peer_id = int(raw_value)
        return peer_id if peer_id > VK_CHAT_PEER_OFFSET else VK_CHAT_PEER_OFFSET + peer_id

    try:
        parsed = urlparse(raw_value)
    except ValueError:
        return None

    query = parse_qs(parsed.query)
    raw_peer = None
    for key in ("peer_id", "peer", "sel"):
        values = query.get(key)
        if values:
            raw_peer = values[0]
            break

    if not raw_peer:
        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) >= 3 and path_parts[0] == "im" and path_parts[1] == "convo":
            raw_peer = path_parts[2]

    if not raw_peer:
        return None

    raw_peer = str(raw_peer).strip()
    if raw_peer.startswith("c"):
        raw_peer = raw_peer[1:]
        try:
            return VK_CHAT_PEER_OFFSET + int(raw_peer)
        except ValueError:
            return None

    try:
        peer_id = int(raw_peer)
    except ValueError:
        return None

    if peer_id > VK_CHAT_PEER_OFFSET:
        return peer_id
    return VK_CHAT_PEER_OFFSET + peer_id


def resolve_application_chat_peer_id(application: Application) -> int | None:
    event_peer_id = application.event.org_chat_peer_id if application.event_id and application.event else 0
    if event_peer_id:
        return int(event_peer_id)

    event_chat_url = application.event.org_chat_url if application.event_id and application.event else ""
    configured_peer_id = getattr(settings, "VK_ORG_CHAT_PEER_ID", 0) or None
    return (
        resolve_vk_chat_peer_id(event_chat_url)
        or resolve_vk_chat_peer_id(settings.VK_ORG_CHAT_URL)
        or configured_peer_id
    )


def build_application_chat_link(application: Application, request=None, chat_url: str = "") -> str:
    payload = {"application_id": application.id}
    event_chat_url = application.event.org_chat_url if application.event_id and application.event else ""
    target_url = chat_url or event_chat_url or settings.VK_ORG_CHAT_URL
    if target_url:
        payload["chat_url"] = target_url

    token = signing.dumps(payload, salt=CHAT_LINK_SALT)
    url = reverse("vk-chat-link-redirect", kwargs={"token": token})
    if settings.VK_CHAT_LINK_BASE_URL:
        return f"{settings.VK_CHAT_LINK_BASE_URL.rstrip('/')}{url}"
    if request is None:
        return url
    return request.build_absolute_uri(url)


def inject_application_chat_link(message: str, application: Application, request=None, chat_url: str = "") -> str:
    chat_link = build_application_chat_link(application, request, chat_url=chat_url)
    if CHAT_LINK_PLACEHOLDER in message:
        return message.replace(CHAT_LINK_PLACEHOLDER, chat_link)
    return f"{message}\n\nСсылка на орг.чат: {chat_link}"


def resolve_chat_joined_status() -> Status:
    status_obj = Status.objects.filter(name=CHAT_JOINED_STATUS_NAME).order_by("id").first()
    if status_obj:
        return status_obj

    return Status.objects.create(
        name=CHAT_JOINED_STATUS_NAME,
        description="Проектант перешел по индивидуальной ссылке на организационный чат.",
        is_positive=True,
    )


def mark_application_chat_link_opened(token: str) -> tuple[Application, str]:
    payload = signing.loads(
        token,
        salt=CHAT_LINK_SALT,
        max_age=settings.VK_CHAT_LINK_MAX_AGE_SECONDS,
    )
    application = Application.objects.select_related("user", "event", "event__leader").prefetch_related(
        "event__organizers"
    ).get(pk=payload["application_id"])
    event_chat_url = application.event.org_chat_url if application.event_id and application.event else ""
    redirect_url = payload.get("chat_url") or event_chat_url or settings.VK_ORG_CHAT_URL
    if not redirect_url:
        return application, ""

    return application, redirect_url


def mark_application_joined_chat_by_vk_user(vk_user_id: int, peer_id: int | None = None) -> Application | None:
    profile = Profile.objects.filter(vk_user_id=vk_user_id).select_related("user").first()
    if not profile:
        return None

    applications = list(
        Application.objects.select_related("user", "event", "event__leader", "status")
        .prefetch_related("event__organizers")
        .filter(user=profile.user, status__name=CHAT_LINK_SENT_STATUS_NAME)
        .order_by("-date_sub", "-id")
    )
    if not applications:
        return None

    matched_applications = applications
    if peer_id:
        exact_matches = [
            application
            for application in applications
            if resolve_application_chat_peer_id(application) == peer_id
        ]
        if exact_matches:
            matched_applications = exact_matches

    application = matched_applications[0]
    joined_status = resolve_chat_joined_status()
    if application.status_id == joined_status.id:
        return application

    previous_status = application.status.name if application.status_id else ""
    application.status = joined_status
    application.save(update_fields=["status"])
    notify_organizers_about_chat_join(application)

    from users.automation_engine import run_crm_automation

    run_crm_automation(
        application,
        "notification.chat_link_opened",
        previous_status=previous_status,
    )
    return application


def resolve_application_vk_user_id(application: Application) -> int:
    profile = Profile.objects.filter(user=application.user).only("vk", "vk_user_id", "vk_confirmed_at").first()
    vk_user_id = refresh_profile_vk_user_id(profile) if profile else None
    if not vk_user_id:
        raise ValueError("у проектанта не указан корректный VK")
    if profile and not profile.vk_confirmed_at:
        raise ValueError("проектант не подтвердил VK-бота")
    return int(vk_user_id)


def mark_application_joined_chat_if_member(application: Application, *, log_missing_peer: bool = True) -> bool:
    peer_id = resolve_application_chat_peer_id(application)
    if not peer_id:
        if log_missing_peer:
            logger.warning("VK chat membership check skipped: peer_id is not configured for application_id=%s", application.id)
        return False

    vk_user_id = resolve_application_vk_user_id(application)
    try:
        if not is_vk_user_in_conversation(peer_id=peer_id, user_id=vk_user_id):
            logger.warning(
                "VK chat membership check: user is not in chat application_id=%s vk_user_id=%s peer_id=%s",
                application.id,
                vk_user_id,
                peer_id,
            )
            return False
    except VKAPIError:
        logger.warning(
            "VK chat membership check failed: application_id=%s vk_user_id=%s peer_id=%s",
            application.id,
            vk_user_id,
            peer_id,
            exc_info=True,
        )
        return False

    logger.warning(
        "VK chat membership check: user already in chat application_id=%s vk_user_id=%s peer_id=%s",
        application.id,
        vk_user_id,
        peer_id,
    )

    joined_status = resolve_chat_joined_status()
    if application.status_id == joined_status.id:
        return True

    previous_status = application.status.name if application.status_id else ""
    application.status = joined_status
    application.save(update_fields=["status"])
    notify_organizers_about_chat_join(application)

    from users.automation_engine import run_crm_automation

    run_crm_automation(
        application,
        "notification.chat_link_opened",
        previous_status=previous_status,
    )
    return True


def scan_chat_membership_for_sent_applications(limit: int = 50) -> dict[str, int]:
    applications = list(
        Application.objects.select_related("user", "event", "event__leader", "status")
        .prefetch_related("event__organizers")
        .filter(status__name=CHAT_LINK_SENT_STATUS_NAME)
        .order_by("-date_sub", "-id")[:limit]
    )

    result = {"scanned": 0, "changed": 0}
    for application in applications:
        result["scanned"] += 1
        try:
            if mark_application_joined_chat_if_member(application, log_missing_peer=False):
                result["changed"] += 1
        except (ValueError, VKConfigurationError) as exc:
            logger.warning(
                "VK chat membership scan skipped: application_id=%s error=%s",
                application.id,
                exc,
            )

    return result


def send_application_vk_message(application: Application, message: str, keyboard: dict | None = None) -> int:
    vk_user_id = resolve_application_vk_user_id(application)

    return send_vk_message(user_id=vk_user_id, message=message, keyboard=keyboard)


def notify_application_testing_started(application: Application, previous_status_id: int | None = None) -> int | None:
    if not settings.VK_ENABLED:
        return None

    if application.status_id == previous_status_id:
        return None

    if not application.status_id or application.status.name != TESTING_STATUS_NAME:
        return None

    try:
        return send_application_vk_message(application, build_testing_started_message(application))
    except (VKConfigurationError, VKAPIError, ValueError) as exc:
        notify_organizers_about_vk_error(application, str(exc))
        return None
