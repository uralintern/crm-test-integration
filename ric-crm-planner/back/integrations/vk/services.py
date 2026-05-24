import json
import random
import re
import urllib.parse
import urllib.request
import uuid
from typing import Any
from dataclasses import dataclass

from django.conf import settings


class VKConfigurationError(Exception):
    pass


@dataclass
class VKAPIError(Exception):
    code: int | None
    message: str

    def __str__(self) -> str:
        if self.code is None:
            return self.message
        return f"VK API error {self.code}: {self.message}"


def normalize_vk_group_id(group_id: str | int | None = None) -> str:
    raw_group_id = str(group_id if group_id is not None else settings.VK_GROUP_ID).strip()
    return "".join(ch for ch in raw_group_id if ch.isdigit())


def extract_vk_user_id(value: str | int | None) -> int | None:
    if value is None:
        return None

    raw_value = str(value).strip()
    if not raw_value:
        return None

    if raw_value.isdigit():
        return int(raw_value)

    id_match = re.search(r"(?:^|[/=])id(\d+)(?:$|[/?&#])", raw_value, flags=re.IGNORECASE)
    if id_match:
        return int(id_match.group(1))

    selector_match = re.search(r"[?&]sel=(\d+)", raw_value, flags=re.IGNORECASE)
    if selector_match:
        return int(selector_match.group(1))

    return None


def is_vk_configured() -> bool:
    return bool(settings.VK_ENABLED and settings.VK_ACCESS_TOKEN)


def ensure_vk_configured() -> None:
    if not settings.VK_ENABLED:
        raise VKConfigurationError("VK integration is disabled.")
    if not settings.VK_ACCESS_TOKEN:
        raise VKConfigurationError("VK access token is not configured.")


def call_vk_method(method_name: str, payload: dict[str, str | int]) -> dict:
    ensure_vk_configured()

    request_payload: dict[str, str | int] = {
        "access_token": settings.VK_ACCESS_TOKEN,
        "v": settings.VK_API_VERSION,
        **payload,
    }
    encoded_payload = urllib.parse.urlencode(request_payload).encode("utf-8")
    request = urllib.request.Request(
        f"{settings.VK_API_BASE_URL.rstrip('/')}/{method_name}",
        data=encoded_payload,
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=settings.VK_REQUEST_TIMEOUT_SECONDS) as response:
        response_body = response.read().decode("utf-8")

    data = json.loads(response_body)
    if "error" in data:
        error = data["error"]
        raise VKAPIError(error.get("error_code"), error.get("error_msg", "Unknown VK API error."))

    return data


def extract_vk_screen_name(value: str | int | None) -> str:
    if value is None:
        return ""

    raw_value = str(value).strip()
    if not raw_value:
        return ""

    if raw_value.startswith("@"):
        return raw_value[1:].strip()

    parsed = urllib.parse.urlparse(raw_value if "://" in raw_value else f"https://vk.com/{raw_value}")
    path = parsed.path.strip("/")
    if not path:
        return ""

    return path.split("/", 1)[0].strip()


def resolve_vk_user_id(value: str | int | None) -> int | None:
    extracted_user_id = extract_vk_user_id(value)
    if extracted_user_id:
        return extracted_user_id

    screen_name = extract_vk_screen_name(value)
    if not screen_name:
        return None

    data = call_vk_method("users.get", {"user_ids": screen_name})
    users = data.get("response", [])
    if not users:
        return None

    return int(users[0]["id"])


def send_vk_message(
    *,
    message: str,
    user_id: int | None = None,
    peer_id: int | None = None,
    keyboard: dict[str, Any] | None = None,
    attachments: list[str] | None = None,
) -> int:
    normalized_message = message.strip()
    normalized_attachments = [attachment.strip() for attachment in (attachments or []) if str(attachment).strip()]
    if not normalized_message and not normalized_attachments:
        raise ValueError("Message or attachment must not be empty.")
    if user_id is None and peer_id is None:
        raise ValueError("Either user_id or peer_id is required.")

    payload: dict[str, str | int] = {
        **({"peer_id": peer_id} if peer_id is not None else {"user_id": user_id or 0}),
        "random_id": random.randint(1, 2_147_483_647),
    }
    if normalized_message:
        payload["message"] = normalized_message
    if normalized_attachments:
        payload["attachment"] = ",".join(normalized_attachments)
    if keyboard:
        payload["keyboard"] = json.dumps(keyboard, ensure_ascii=False)

    data = call_vk_method("messages.send", payload)

    return int(data.get("response", 0))


def is_vk_user_in_conversation(*, peer_id: int, user_id: int) -> bool:
    data = call_vk_method("messages.getConversationMembers", {"peer_id": peer_id})
    response = data.get("response", {})
    items = response.get("items") if isinstance(response, dict) else []
    if not isinstance(items, list):
        return False

    for item in items:
        if not isinstance(item, dict):
            continue
        member_id = item.get("member_id", item.get("id"))
        try:
            if int(member_id) == int(user_id):
                return True
        except (TypeError, ValueError):
            continue
    return False


def answer_vk_message_event(*, event_id: str, user_id: int, peer_id: int, text: str = "Готово") -> None:
    if not event_id:
        return

    call_vk_method(
        "messages.sendMessageEventAnswer",
        {
            "event_id": event_id,
            "user_id": user_id,
            "peer_id": peer_id,
            "event_data": json.dumps(
                {
                    "type": "show_snackbar",
                    "text": text,
                },
                ensure_ascii=False,
            ),
        },
    )


def delete_vk_message(
    *,
    peer_id: int,
    message_id: int | None = None,
    conversation_message_id: int | None = None,
) -> None:
    payload: dict[str, str | int] = {
        "delete_for_all": 1,
    }
    if conversation_message_id:
        payload["peer_id"] = peer_id
        payload["cmids"] = conversation_message_id
    elif message_id:
        payload["message_ids"] = message_id
    else:
        return

    call_vk_method("messages.delete", payload)


def upload_multipart_file(upload_url: str, *, file_name: str, content: bytes) -> dict:
    boundary = f"----crm-vk-upload-{uuid.uuid4().hex}"
    safe_file_name = file_name.replace('"', "'").replace("\r", " ").replace("\n", " ")
    body = b"\r\n".join(
        [
            f"--{boundary}".encode("utf-8"),
            f'Content-Disposition: form-data; name="file"; filename="{safe_file_name}"'.encode("utf-8"),
            b"Content-Type: application/octet-stream",
            b"",
            content,
            f"--{boundary}--".encode("utf-8"),
            b"",
        ]
    )
    request = urllib.request.Request(
        upload_url,
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request, timeout=settings.VK_REQUEST_TIMEOUT_SECONDS) as response:
        response_body = response.read().decode("utf-8")
    data = json.loads(response_body)
    if "error" in data:
        error = data["error"]
        if isinstance(error, dict):
            raise VKAPIError(error.get("error_code"), error.get("error_msg", "Unknown VK upload error."))
        raise VKAPIError(None, str(error))
    return data


def extract_saved_doc(response: Any) -> dict:
    if isinstance(response, dict):
        if isinstance(response.get("doc"), dict):
            return response["doc"]
        if "id" in response and "owner_id" in response:
            return response
    if isinstance(response, list):
        for item in response:
            if isinstance(item, dict):
                if isinstance(item.get("doc"), dict):
                    return item["doc"]
                if "id" in item and "owner_id" in item:
                    return item
    raise VKAPIError(None, "VK docs.save did not return saved document data.")


def upload_vk_document(*, file_name: str, content: bytes, user_id: int | None = None, peer_id: int | None = None) -> str:
    if user_id is None and peer_id is None:
        raise ValueError("Either user_id or peer_id is required.")
    target_peer_id = peer_id if peer_id is not None else user_id
    server_data = call_vk_method("docs.getMessagesUploadServer", {"type": "doc", "peer_id": int(target_peer_id or 0)})
    upload_url = str((server_data.get("response") or {}).get("upload_url") or "")
    if not upload_url:
        raise VKAPIError(None, "VK did not return document upload URL.")
    uploaded = upload_multipart_file(upload_url, file_name=file_name, content=content)
    file_token = str(uploaded.get("file") or "")
    if not file_token:
        raise VKAPIError(None, "VK document upload did not return file token.")
    saved = call_vk_method("docs.save", {"file": file_token, "title": file_name})
    doc = extract_saved_doc(saved.get("response"))
    return f"doc{int(doc['owner_id'])}_{int(doc['id'])}"
