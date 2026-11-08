"""Характеризационные тесты VK-интеграции.

Фиксируют текущее поведение перед реорганизацией кода. Реальная сеть не
используется: HTTP к VK подменяется на уровне urlopen или функций-обёрток.
Если VK_ACCESS_TOKEN не задан явно, любой непредусмотренный вызов VK падает
с VKConfigurationError, а не уходит в сеть.
"""

import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.error import URLError
from urllib.parse import parse_qs

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core import signing
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from integrations.vk.crm_notifications import (
    CHAT_LINK_SALT,
    build_application_chat_link,
    build_testing_started_message,
    get_application_organizers,
    inject_application_chat_link,
    mark_application_joined_chat_by_vk_user,
    mark_application_joined_chat_if_member,
    notify_application_testing_started,
    notify_organizers_about_vk_error,
    resolve_application_chat_peer_id,
    resolve_application_vk_user_id,
    resolve_vk_chat_peer_id,
    scan_chat_membership_for_sent_applications,
    send_application_vk_message,
    upload_application_vk_documents,
)
from integrations.vk.planner_invites import (
    build_decline_confirmation_keyboard,
    build_planner_invite_keyboard,
    handle_planner_invite_payload,
    handle_vk_chat_join_message,
    handle_vk_message_event,
    handle_vk_message_new_event,
    handle_vk_peer_debug_message,
    handle_vk_start_message,
    is_vk_start_message,
    parse_vk_button_payload,
    resolve_vk_application_user_id,
    send_planner_invite,
    send_planner_invites_for_event,
    send_start_message,
)
from integrations.vk.serializers import (
    VKApplicationMessageSerializer,
    VKPlannerInviteSerializer,
    VKSendTestSerializer,
)
from integrations.vk.services import (
    VKAPIError,
    VKConfigurationError,
    answer_vk_message_event,
    call_vk_method,
    delete_vk_message,
    ensure_vk_configured,
    extract_saved_doc,
    extract_vk_screen_name,
    extract_vk_user_id,
    is_vk_configured,
    is_vk_user_in_conversation,
    normalize_vk_group_id,
    resolve_vk_user_id,
    send_vk_message,
    upload_multipart_file,
    upload_vk_document,
)
from users.models import ROLE_CURATOR, Application, CRMRole, Event, Profile, Status
from users.vk_profiles import (
    confirm_profile_by_vk_user_id,
    get_vk_bot_url,
    refresh_profile_vk_user_id,
    reset_profile_vk_confirmation_if_changed,
    resolve_profile_vk_user_id,
)

VK_API_SETTINGS = {
    "VK_ENABLED": True,
    "VK_ACCESS_TOKEN": "token-example",
    "VK_API_VERSION": "5.199",
    "VK_API_BASE_URL": "https://api.vk.example.test/method",
    "VK_REQUEST_TIMEOUT_SECONDS": 5,
}
URLOPEN = "integrations.vk.services.urllib.request.urlopen"
RUN_CRM_AUTOMATION = "users.automation_engine.run_crm_automation"

CHAT_LINK_SENT = "Отправлена ссылка на орг. чат"
CHAT_JOINED = "Добавился в орг. чат"
ENROLLMENT_CLOSED = "Набор завершён"
STARTED_PSH = "Приступил к ПШ"
DECLINED_PSH = "Отказался от ПШ"


def vk_response(data):
    """Ответ urlopen, пригодный для `with urlopen(...) as response`."""
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(data).encode("utf-8")
    return response


def sent_request(urlopen_mock, index=-1):
    request = urlopen_mock.call_args_list[index].args[0]
    return request, parse_qs(request.data.decode("utf-8"))


class VKFixturesMixin:
    """Общие данные: проектант с подтверждённым VK, мероприятие и заявка."""

    def create_user(self, email, vk_user_id=None, confirmed=True, vk=None):
        user = get_user_model().objects.create_user(
            username=email,
            email=email,
            password="password",
            first_name="Иван",
            last_name="Иванов",
            is_active=True,
        )
        profile = user.crm_profile
        profile.vk = vk if vk is not None else (f"https://vk.com/id{vk_user_id}" if vk_user_id else "")
        profile.vk_user_id = vk_user_id
        profile.vk_confirmed_at = timezone.now() if confirmed else None
        profile.save(update_fields=["vk", "vk_user_id", "vk_confirmed_at"])
        return user, profile

    def create_event(self, name="Практика", **extra):
        return Event.objects.create(
            name=name,
            stage="Набор",
            start_date="2026-05-01",
            end_date="2026-05-10",
            end_app_date=timezone.now(),
            **extra,
        )

    def create_application(self, user, event, status_obj, date_sub=None):
        return Application.objects.create(
            user=user,
            event=event,
            date_sub=date_sub or timezone.now(),
            date_end=timezone.now(),
            status=status_obj,
        )

    @staticmethod
    def get_status(name):
        # Часть статусов уже засеяна миграциями; дубли ломают поиск по имени.
        return Status.objects.filter(name=name).order_by("id").first() or Status.objects.create(name=name)

    def setup_vk_data(self):
        self.user, self.profile = self.create_user("student@example.test", vk_user_id=123456)
        self.event = self.create_event()
        self.testing_status = self.get_status("Прохождение тестирования")
        self.chat_link_sent_status = self.get_status(CHAT_LINK_SENT)
        self.chat_joined_status = self.get_status(CHAT_JOINED)
        self.enrollment_closed_status = self.get_status(ENROLLMENT_CLOSED)
        self.application = self.create_application(self.user, self.event, self.chat_link_sent_status)

    def make_curator(self, user, profile):
        CRMRole.objects.create(
            user=user,
            role_type=ROLE_CURATOR,
            content_type=ContentType.objects.get_for_model(Profile),
            object_id=profile.pk,
        )


# ---------------------------------------------------------------------------
# services.py
# ---------------------------------------------------------------------------


class VKServiceHelpersTests(TestCase):
    @override_settings(VK_GROUP_ID="club555")
    def test_normalize_vk_group_id_uses_settings_by_default(self):
        self.assertEqual(normalize_vk_group_id(), "555")

    def test_normalize_vk_group_id_accepts_int(self):
        self.assertEqual(normalize_vk_group_id(777), "777")

    def test_extract_vk_user_id_variants(self):
        self.assertIsNone(extract_vk_user_id(None))
        self.assertIsNone(extract_vk_user_id("   "))
        self.assertEqual(extract_vk_user_id("42"), 42)
        self.assertEqual(extract_vk_user_id(42), 42)
        self.assertEqual(extract_vk_user_id("https://vk.com/id123"), 123)
        self.assertEqual(extract_vk_user_id("https://vk.com/id123?w=wall"), 123)
        self.assertEqual(extract_vk_user_id("https://vk.com/im?sel=987"), 987)
        self.assertIsNone(extract_vk_user_id("https://vk.com/some_screen_name"))

    def test_extract_vk_screen_name_variants(self):
        self.assertEqual(extract_vk_screen_name(None), "")
        self.assertEqual(extract_vk_screen_name("  "), "")
        self.assertEqual(extract_vk_screen_name("@student_name"), "student_name")
        self.assertEqual(extract_vk_screen_name("student_name"), "student_name")
        self.assertEqual(extract_vk_screen_name("https://vk.com/student_name/extra"), "student_name")
        self.assertEqual(extract_vk_screen_name("https://vk.com/"), "")

    @override_settings(VK_ENABLED=True, VK_ACCESS_TOKEN="token-example")
    def test_is_vk_configured_requires_flag_and_token(self):
        self.assertTrue(is_vk_configured())
        with override_settings(VK_ACCESS_TOKEN=""):
            self.assertFalse(is_vk_configured())
        with override_settings(VK_ENABLED=False):
            self.assertFalse(is_vk_configured())

    def test_ensure_vk_configured_raises_when_disabled(self):
        with override_settings(VK_ENABLED=False, VK_ACCESS_TOKEN="token-example"):
            with self.assertRaisesMessage(VKConfigurationError, "disabled"):
                ensure_vk_configured()
        with override_settings(VK_ENABLED=True, VK_ACCESS_TOKEN=""):
            with self.assertRaisesMessage(VKConfigurationError, "token"):
                ensure_vk_configured()

    def test_vk_api_error_str(self):
        self.assertEqual(str(VKAPIError(901, "Нет доступа")), "VK API error 901: Нет доступа")
        self.assertEqual(str(VKAPIError(None, "Сеть недоступна")), "Сеть недоступна")

    def test_extract_saved_doc_variants(self):
        doc = {"id": 1, "owner_id": -2}
        self.assertEqual(extract_saved_doc({"type": "doc", "doc": doc}), doc)
        self.assertEqual(extract_saved_doc(doc), doc)
        self.assertEqual(extract_saved_doc([{"doc": doc}]), doc)
        self.assertEqual(extract_saved_doc(["skip", doc]), doc)
        with self.assertRaises(VKAPIError):
            extract_saved_doc({"unexpected": True})
        with self.assertRaises(VKAPIError):
            extract_saved_doc(None)


@override_settings(**VK_API_SETTINGS)
@patch(URLOPEN)
class VKServiceHttpTests(TestCase):
    def test_call_vk_method_posts_token_and_version(self, urlopen):
        urlopen.return_value = vk_response({"response": 1})

        data = call_vk_method("users.get", {"user_ids": "student"})

        self.assertEqual(data, {"response": 1})
        request, params = sent_request(urlopen)
        self.assertEqual(request.full_url, "https://api.vk.example.test/method/users.get")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(params["access_token"], ["token-example"])
        self.assertEqual(params["v"], ["5.199"])
        self.assertEqual(params["user_ids"], ["student"])
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 5)

    def test_call_vk_method_wraps_network_error(self, urlopen):
        urlopen.side_effect = URLError("connection refused")

        with self.assertRaises(VKAPIError) as ctx:
            call_vk_method("users.get", {})

        self.assertIsNone(ctx.exception.code)
        self.assertIn("VK API request failed", ctx.exception.message)

    def test_call_vk_method_error_without_message(self, urlopen):
        urlopen.return_value = vk_response({"error": {"error_code": 5}})

        with self.assertRaises(VKAPIError) as ctx:
            call_vk_method("users.get", {})

        self.assertEqual(ctx.exception.code, 5)
        self.assertEqual(ctx.exception.message, "Unknown VK API error.")

    def test_call_vk_method_does_not_call_network_when_disabled(self, urlopen):
        with override_settings(VK_ENABLED=False):
            with self.assertRaises(VKConfigurationError):
                call_vk_method("users.get", {})
        urlopen.assert_not_called()

    def test_resolve_vk_user_id_from_link_without_network(self, urlopen):
        self.assertEqual(resolve_vk_user_id("https://vk.com/id321"), 321)
        urlopen.assert_not_called()

    def test_resolve_vk_user_id_by_screen_name(self, urlopen):
        urlopen.return_value = vk_response({"response": [{"id": 4242}]})

        self.assertEqual(resolve_vk_user_id("https://vk.com/student_name"), 4242)
        _, params = sent_request(urlopen)
        self.assertEqual(params["user_ids"], ["student_name"])

    def test_resolve_vk_user_id_returns_none_for_unknown_or_empty(self, urlopen):
        urlopen.return_value = vk_response({"response": []})

        self.assertIsNone(resolve_vk_user_id("student_name"))
        self.assertIsNone(resolve_vk_user_id(""))
        self.assertEqual(urlopen.call_count, 1)

    def test_send_vk_message_to_peer_with_attachments_and_keyboard(self, urlopen):
        urlopen.return_value = vk_response({"response": 15})
        keyboard = {"inline": True, "buttons": []}

        message_id = send_vk_message(
            peer_id=2000000001,
            message="  Привет  ",
            keyboard=keyboard,
            attachments=["doc1_2", "  ", "doc3_4"],
        )

        self.assertEqual(message_id, 15)
        request, params = sent_request(urlopen)
        self.assertTrue(request.full_url.endswith("/messages.send"))
        self.assertEqual(params["peer_id"], ["2000000001"])
        self.assertNotIn("user_id", params)
        self.assertEqual(params["message"], ["Привет"])
        self.assertEqual(params["attachment"], ["doc1_2,doc3_4"])
        self.assertEqual(json.loads(params["keyboard"][0]), keyboard)
        self.assertIn("random_id", params)

    def test_send_vk_message_attachment_only(self, urlopen):
        urlopen.return_value = vk_response({"response": 16})

        send_vk_message(user_id=7, message="", attachments=["doc1_2"])

        _, params = sent_request(urlopen)
        self.assertEqual(params["user_id"], ["7"])
        self.assertNotIn("message", params)

    def test_send_vk_message_validates_arguments(self, urlopen):
        with self.assertRaises(ValueError):
            send_vk_message(user_id=1, message="   ")
        with self.assertRaises(ValueError):
            send_vk_message(message="Текст")
        urlopen.assert_not_called()

    def test_is_vk_user_in_conversation_matches_member_id_and_id(self, urlopen):
        urlopen.return_value = vk_response(
            {"response": {"items": ["bad", {"member_id": "oops"}, {"member_id": 10}, {"id": 20}]}}
        )
        self.assertTrue(is_vk_user_in_conversation(peer_id=2000000001, user_id=10))

        urlopen.return_value = vk_response({"response": {"items": [{"id": 20}]}})
        self.assertTrue(is_vk_user_in_conversation(peer_id=2000000001, user_id=20))

        urlopen.return_value = vk_response({"response": {"items": [{"member_id": 10}]}})
        self.assertFalse(is_vk_user_in_conversation(peer_id=2000000001, user_id=99))

        _, params = sent_request(urlopen)
        self.assertEqual(params["peer_id"], ["2000000001"])

    def test_is_vk_user_in_conversation_handles_unexpected_shape(self, urlopen):
        urlopen.return_value = vk_response({"response": {"items": "not-a-list"}})
        self.assertFalse(is_vk_user_in_conversation(peer_id=1, user_id=1))

        urlopen.return_value = vk_response({"response": []})
        self.assertFalse(is_vk_user_in_conversation(peer_id=1, user_id=1))

    def test_answer_vk_message_event_sends_snackbar(self, urlopen):
        urlopen.return_value = vk_response({"response": 1})

        answer_vk_message_event(event_id="evt-1", user_id=5, peer_id=6, text="Принято")

        request, params = sent_request(urlopen)
        self.assertTrue(request.full_url.endswith("/messages.sendMessageEventAnswer"))
        self.assertEqual(params["event_id"], ["evt-1"])
        self.assertEqual(json.loads(params["event_data"][0]), {"type": "show_snackbar", "text": "Принято"})

    def test_answer_vk_message_event_skips_empty_event_id(self, urlopen):
        answer_vk_message_event(event_id="", user_id=5, peer_id=6)
        urlopen.assert_not_called()

    def test_delete_vk_message_by_conversation_message_id(self, urlopen):
        urlopen.return_value = vk_response({"response": 1})

        delete_vk_message(peer_id=6, conversation_message_id=55)

        request, params = sent_request(urlopen)
        self.assertTrue(request.full_url.endswith("/messages.delete"))
        self.assertEqual(params["cmids"], ["55"])
        self.assertEqual(params["peer_id"], ["6"])
        self.assertEqual(params["delete_for_all"], ["1"])

    def test_delete_vk_message_by_message_id(self, urlopen):
        urlopen.return_value = vk_response({"response": 1})

        delete_vk_message(peer_id=6, message_id=77)

        _, params = sent_request(urlopen)
        self.assertEqual(params["message_ids"], ["77"])
        self.assertNotIn("cmids", params)

    def test_delete_vk_message_without_ids_does_nothing(self, urlopen):
        delete_vk_message(peer_id=6)
        urlopen.assert_not_called()

    def test_upload_multipart_file_builds_multipart_request(self, urlopen):
        urlopen.return_value = vk_response({"file": "file-token"})

        data = upload_multipart_file("https://upload.example.test/doc", file_name='plan"\nv1.pdf', content=b"PDF")

        self.assertEqual(data, {"file": "file-token"})
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://upload.example.test/doc")
        self.assertTrue(request.get_header("Content-type").startswith("multipart/form-data; boundary="))
        self.assertIn(b'filename="plan\' v1.pdf"', request.data)
        self.assertIn(b"PDF", request.data)

    def test_upload_multipart_file_errors(self, urlopen):
        urlopen.return_value = vk_response({"error": {"error_code": 3, "error_msg": "bad file"}})
        with self.assertRaises(VKAPIError) as ctx:
            upload_multipart_file("https://upload.example.test", file_name="a.pdf", content=b"x")
        self.assertEqual(ctx.exception.code, 3)

        urlopen.return_value = vk_response({"error": "no_file"})
        with self.assertRaises(VKAPIError) as ctx:
            upload_multipart_file("https://upload.example.test", file_name="a.pdf", content=b"x")
        self.assertEqual(ctx.exception.message, "no_file")

        urlopen.side_effect = URLError("timeout")
        with self.assertRaisesMessage(VKAPIError, "VK document upload failed"):
            upload_multipart_file("https://upload.example.test", file_name="a.pdf", content=b"x")

    def test_upload_vk_document_returns_attachment_with_access_key(self, urlopen):
        urlopen.side_effect = [
            vk_response({"response": {"upload_url": "https://upload.example.test/doc"}}),
            vk_response({"file": "file-token"}),
            vk_response({"response": {"type": "doc", "doc": {"id": 5, "owner_id": -10, "access_key": "key"}}}),
        ]

        attachment = upload_vk_document(file_name="plan.pdf", content=b"PDF", user_id=123)

        self.assertEqual(attachment, "doc-10_5_key")
        _, server_params = sent_request(urlopen, 0)
        self.assertEqual(server_params["type"], ["doc"])
        self.assertEqual(server_params["peer_id"], ["123"])
        _, save_params = sent_request(urlopen, 2)
        self.assertEqual(save_params["file"], ["file-token"])
        self.assertEqual(save_params["title"], ["plan.pdf"])

    def test_upload_vk_document_without_access_key(self, urlopen):
        urlopen.side_effect = [
            vk_response({"response": {"upload_url": "https://upload.example.test/doc"}}),
            vk_response({"file": "file-token"}),
            vk_response({"response": [{"id": 5, "owner_id": 10}]}),
        ]

        self.assertEqual(upload_vk_document(file_name="a.pdf", content=b"x", peer_id=2000000001), "doc10_5")

    def test_upload_vk_document_errors(self, urlopen):
        with self.assertRaises(ValueError):
            upload_vk_document(file_name="a.pdf", content=b"x")

        urlopen.side_effect = [vk_response({"response": {}})]
        with self.assertRaisesMessage(VKAPIError, "upload URL"):
            upload_vk_document(file_name="a.pdf", content=b"x", user_id=1)

        urlopen.side_effect = [
            vk_response({"response": {"upload_url": "https://upload.example.test/doc"}}),
            vk_response({}),
        ]
        with self.assertRaisesMessage(VKAPIError, "file token"):
            upload_vk_document(file_name="a.pdf", content=b"x", user_id=1)


# ---------------------------------------------------------------------------
# serializers.py
# ---------------------------------------------------------------------------


class VKSerializerTests(TestCase):
    def test_send_test_requires_user_or_peer(self):
        serializer = VKSendTestSerializer(data={"message": "Текст"})
        self.assertFalse(serializer.is_valid())

        serializer = VKSendTestSerializer(data={"message": " Текст ", "peer_id": 2000000001})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["message"], "Текст")

    def test_application_message_builds_text_with_and_without_subject(self):
        serializer = VKApplicationMessageSerializer(data={"message": "Тело"})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["text"], "Тело")
        self.assertFalse(serializer.validated_data["include_chat_link"])

        serializer = VKApplicationMessageSerializer(data={"subject": "Тема", "message": "Тело"})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["text"], "Тема\n\nТело")

    def test_planner_invite_recipient_mode_default_and_choices(self):
        serializer = VKPlannerInviteSerializer(data={})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["recipient_mode"], "joined")

        for mode in ("joined", "all", "declined"):
            self.assertTrue(VKPlannerInviteSerializer(data={"recipient_mode": mode}).is_valid())
        self.assertFalse(VKPlannerInviteSerializer(data={"recipient_mode": "everyone"}).is_valid())


# ---------------------------------------------------------------------------
# views.py
# ---------------------------------------------------------------------------


class VKCallbackViewCoverageTests(TestCase):
    URL = "/api/integrations/vk/callback/"

    def setUp(self):
        self.client = APIClient()

    @override_settings(VK_CONFIRMATION_CODE="", VK_GROUP_ID="club123")
    def test_confirmation_without_configured_code_returns_503(self):
        response = self.client.post(self.URL, {"type": "confirmation", "group_id": 123}, format="json")

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    @override_settings(VK_CONFIRMATION_CODE="confirm-code", VK_GROUP_ID="club123")
    def test_confirmation_without_group_id_in_payload_returns_code(self):
        response = self.client.post(self.URL, {"type": "confirmation"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.content.decode(), "confirm-code")
        self.assertTrue(response["Content-Type"].startswith("text/plain"))

    @override_settings(VK_CONFIRMATION_CODE="confirm-code", VK_CALLBACK_SECRET="secret")
    def test_confirmation_does_not_require_secret(self):
        response = self.client.post(self.URL, {"type": "confirmation"}, format="json")

        self.assertEqual(response.content.decode(), "confirm-code")

    @override_settings(VK_CALLBACK_SECRET="secret")
    @patch("integrations.vk.views.handle_vk_message_new_event")
    def test_message_new_with_valid_secret_is_handled(self, handler):
        payload = {"type": "message_new", "secret": "secret", "object": {"message": {"from_id": 1, "text": "Начать"}}}

        response = self.client.post(self.URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.content.decode(), "ok")
        handler.assert_called_once()
        self.assertEqual(handler.call_args.args[0]["object"]["message"]["text"], "Начать")

    @override_settings(VK_CALLBACK_SECRET="secret")
    @patch("integrations.vk.views.handle_vk_message_event")
    @patch("integrations.vk.views.handle_vk_message_new_event")
    def test_wrong_secret_rejects_without_handling(self, new_handler, event_handler):
        for event_type in ("message_new", "message_event"):
            response = self.client.post(self.URL, {"type": event_type, "secret": "wrong"}, format="json")
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.client.post(self.URL, {"type": "message_new"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        new_handler.assert_not_called()
        event_handler.assert_not_called()

    @override_settings(VK_CALLBACK_SECRET="secret")
    @patch("integrations.vk.views.handle_vk_message_event")
    def test_message_event_with_valid_secret_is_handled(self, handler):
        response = self.client.post(self.URL, {"type": "message_event", "secret": "secret", "object": {}}, format="json")

        self.assertEqual(response.content.decode(), "ok")
        handler.assert_called_once()

    @override_settings(VK_CALLBACK_SECRET="secret")
    @patch("integrations.vk.views.handle_vk_message_event", side_effect=VKAPIError(901, "fail"))
    @patch("integrations.vk.views.handle_vk_message_new_event", side_effect=VKConfigurationError("off"))
    def test_handler_errors_still_answer_ok(self, new_handler, event_handler):
        for event_type in ("message_new", "message_event"):
            response = self.client.post(self.URL, {"type": event_type, "secret": "secret"}, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.content.decode(), "ok")

    @override_settings(VK_CALLBACK_SECRET="secret")
    @patch("integrations.vk.views.handle_vk_message_new_event", side_effect=ValueError("bad"))
    def test_value_error_in_handler_answers_ok(self, handler):
        response = self.client.post(self.URL, {"type": "message_new", "secret": "secret"}, format="json")

        self.assertEqual(response.content.decode(), "ok")

    @override_settings(VK_CALLBACK_SECRET="secret")
    def test_unknown_event_type_answers_ok(self):
        response = self.client.post(self.URL, {"type": "group_join", "secret": "secret"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.content.decode(), "ok")


class VKCuratorViewsTests(VKFixturesMixin, TestCase):
    def setUp(self):
        self.setup_vk_data()
        self.curator, curator_profile = self.create_user("curator@example.test")
        self.make_curator(self.curator, curator_profile)
        self.client = APIClient()
        self.client.force_authenticate(user=self.curator)
        self.student_client = APIClient()
        self.student_client.force_authenticate(user=self.user)

    def test_curator_endpoints_forbidden_for_projectant(self):
        urls = [
            "/api/integrations/vk/send-test/",
            f"/api/integrations/vk/applications/{self.application.id}/message/",
            f"/api/integrations/vk/events/{self.event.id}/planner-invite/",
        ]
        for url in urls:
            response = self.student_client.post(url, {"message": "Текст", "user_id": 1}, format="json")
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, url)

    def test_curator_endpoints_require_authentication(self):
        response = APIClient().post("/api/integrations/vk/send-test/", {"message": "x", "user_id": 1}, format="json")

        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    @patch("integrations.vk.views.send_vk_message", return_value=31)
    def test_send_test_returns_message_id(self, send_mock):
        response = self.client.post(
            "/api/integrations/vk/send-test/", {"message": "Проверка", "user_id": 123456}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"message_id": 31})
        self.assertEqual(send_mock.call_args.kwargs["message"], "Проверка")
        self.assertEqual(send_mock.call_args.kwargs["user_id"], 123456)

    def test_send_test_validation_error(self):
        response = self.client.post("/api/integrations/vk/send-test/", {"message": "Проверка"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("integrations.vk.views.send_vk_message", side_effect=VKConfigurationError("VK integration is disabled."))
    def test_send_test_vk_not_configured_returns_503(self, send_mock):
        response = self.client.post("/api/integrations/vk/send-test/", {"message": "x", "user_id": 1}, format="json")

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["detail"], "VK integration is disabled.")

    @patch("integrations.vk.views.send_vk_message", side_effect=VKAPIError(901, "Нет доступа"))
    def test_send_test_vk_error_returns_400_with_code(self, send_mock):
        response = self.client.post("/api/integrations/vk/send-test/", {"message": "x", "user_id": 1}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"detail": "Нет доступа", "code": 901})

    @patch("integrations.vk.views.send_application_vk_message", return_value=11)
    def test_application_message_sends_subject_and_message(self, send_mock):
        response = self.client.post(
            f"/api/integrations/vk/applications/{self.application.id}/message/",
            {"subject": "Тема", "message": "Тело"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"message_id": 11})
        sent_application, sent_text = send_mock.call_args.args
        self.assertEqual(sent_application.id, self.application.id)
        self.assertEqual(sent_text, "Тема\n\nТело")

    @override_settings(VK_CHAT_LINK_BASE_URL="https://crm.example.test")
    @patch("integrations.vk.views.send_application_vk_message", return_value=12)
    def test_application_message_injects_chat_link(self, send_mock):
        response = self.client.post(
            f"/api/integrations/vk/applications/{self.application.id}/message/",
            {"message": "Вступайте: {chat_link}", "chat_url": "https://vk.me/join/example"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sent_text = send_mock.call_args.args[1]
        self.assertTrue(sent_text.startswith("Вступайте: https://crm.example.test/api/integrations/vk/chat-links/"))
        token = sent_text.rsplit("/chat-links/", 1)[1].rstrip("/")
        payload = signing.loads(token, salt=CHAT_LINK_SALT)
        self.assertEqual(payload, {"application_id": self.application.id, "chat_url": "https://vk.me/join/example"})

    @patch("integrations.vk.views.notify_organizers_about_vk_error")
    @patch("integrations.vk.views.send_application_vk_message", side_effect=ValueError("у проектанта не указан корректный VK"))
    def test_application_message_error_returns_400_and_notifies(self, send_mock, notify_mock):
        response = self.client.post(
            f"/api/integrations/vk/applications/{self.application.id}/message/", {"message": "Тело"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "у проектанта не указан корректный VK")
        notify_mock.assert_called_once()

    def test_application_message_unknown_application_returns_404(self):
        response = self.client.post("/api/integrations/vk/applications/999999/message/", {"message": "x"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("integrations.vk.views.send_planner_invites_for_event", return_value={"sent": 2, "failed": 1, "skipped": 0})
    def test_planner_invite_returns_result(self, send_mock):
        response = self.client.post(f"/api/integrations/vk/events/{self.event.id}/planner-invite/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"sent": 2, "failed": 1, "skipped": 0})
        send_mock.assert_called_once_with(self.event.id, recipient_mode="joined", message="")

    @patch("integrations.vk.views.send_planner_invites_for_event", return_value={"sent": 0, "failed": 0, "skipped": 0})
    def test_planner_invite_passes_mode_and_message(self, send_mock):
        self.client.post(
            f"/api/integrations/vk/events/{self.event.id}/planner-invite/",
            {"recipient_mode": "declined", "message": "Возвращайтесь"},
            format="json",
        )

        send_mock.assert_called_once_with(self.event.id, recipient_mode="declined", message="Возвращайтесь")

    def test_planner_invite_invalid_mode_returns_400(self):
        response = self.client.post(
            f"/api/integrations/vk/events/{self.event.id}/planner-invite/", {"recipient_mode": "everyone"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("integrations.vk.views.send_planner_invites_for_event", side_effect=VKConfigurationError("disabled"))
    def test_planner_invite_vk_not_configured_returns_503(self, send_mock):
        response = self.client.post(f"/api/integrations/vk/events/{self.event.id}/planner-invite/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)


class VKBotStatusAndPromptTests(VKFixturesMixin, TestCase):
    def setUp(self):
        self.setup_vk_data()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @override_settings(VK_GROUP_ID="club77")
    def test_bot_status_response_shape(self):
        response = self.client.get("/api/integrations/vk/bot-status/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data), {"confirmed", "vk", "vk_user_id", "bot_url"})
        self.assertTrue(response.data["confirmed"])
        self.assertEqual(response.data["vk"], "https://vk.com/id123456")
        self.assertEqual(response.data["vk_user_id"], 123456)
        self.assertEqual(response.data["bot_url"], "https://vk.com/im?sel=-77")

    def test_bot_status_requires_authentication(self):
        response = APIClient().get("/api/integrations/vk/bot-status/")

        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    @patch("integrations.vk.planner_invites.send_vk_message", side_effect=VKAPIError(7, "Permission denied"))
    def test_confirm_prompt_other_vk_error_returns_400_with_code(self, send_mock):
        self.profile.vk_confirmed_at = None
        self.profile.save(update_fields=["vk_confirmed_at"])

        response = self.client.post("/api/integrations/vk/confirm-prompt/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"detail": "Permission denied", "code": 7})


class VKChatLinkRedirectCoverageTests(VKFixturesMixin, TestCase):
    def setUp(self):
        self.setup_vk_data()
        self.client = APIClient()

    def url(self, token):
        return f"/api/integrations/vk/chat-links/{token}/"

    @override_settings(VK_ORG_CHAT_URL="https://vk.com/im?sel=c1", VK_CHAT_LINK_MAX_AGE_SECONDS=3600)
    def test_chat_url_from_token_has_priority(self):
        token = signing.dumps(
            {"application_id": self.application.id, "chat_url": "https://vk.me/join/from-token"}, salt=CHAT_LINK_SALT
        )

        response = self.client.get(self.url(token))

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(response["Location"], "https://vk.me/join/from-token")

    @override_settings(VK_ORG_CHAT_URL="https://vk.com/im?sel=c1", VK_CHAT_LINK_MAX_AGE_SECONDS=-1)
    def test_expired_token_returns_400(self):
        token = signing.dumps({"application_id": self.application.id}, salt=CHAT_LINK_SALT)

        response = self.client.get(self.url(token))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "VK chat link has expired.")

    @override_settings(VK_ORG_CHAT_URL="https://vk.com/im?sel=c1", VK_CHAT_LINK_MAX_AGE_SECONDS=3600)
    def test_invalid_tokens_return_400(self):
        tokens = [
            "not-a-signed-token",
            signing.dumps({"application_id": self.application.id}, salt="other-salt"),
            signing.dumps({"other": 1}, salt=CHAT_LINK_SALT),
            signing.dumps({"application_id": 999999}, salt=CHAT_LINK_SALT),
        ]
        for token in tokens:
            response = self.client.get(self.url(token))
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, token)
            self.assertEqual(response.data["detail"], "Invalid VK chat link.")

    @override_settings(VK_ORG_CHAT_URL="", VK_CHAT_LINK_MAX_AGE_SECONDS=3600)
    def test_without_any_chat_url_returns_503(self):
        token = signing.dumps({"application_id": self.application.id}, salt=CHAT_LINK_SALT)

        response = self.client.get(self.url(token))

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)


# ---------------------------------------------------------------------------
# crm_notifications.py
# ---------------------------------------------------------------------------


class VKChatPeerAndLinkTests(VKFixturesMixin, TestCase):
    def setUp(self):
        self.setup_vk_data()

    def test_resolve_vk_chat_peer_id_variants(self):
        cases = {
            "": None,
            "5": 2000000005,
            "2000000007": 2000000007,
            "https://vk.com/im?sel=c3": 2000000003,
            "https://vk.com/im?sel=12": 2000000012,
            "https://vk.com/im?peer_id=2000000010": 2000000010,
            "https://vk.com/im?peer=4": 2000000004,
            "https://vk.com/im/convo/2000000011": 2000000011,
            "https://vk.com/im?sel=cX": None,
            "https://vk.com/im?sel=abc": None,
            "https://vk.me/join/abcdef": None,
        }
        for value, expected in cases.items():
            self.assertEqual(resolve_vk_chat_peer_id(value), expected, value)

    @override_settings(VK_ORG_CHAT_URL="https://vk.com/im?sel=c9", VK_ORG_CHAT_PEER_ID=2000000077)
    def test_resolve_application_chat_peer_id_priority(self):
        self.assertEqual(resolve_application_chat_peer_id(self.application), 2000000009)

        self.event.org_chat_url = "https://vk.com/im?sel=c2"
        self.event.save(update_fields=["org_chat_url"])
        self.application.refresh_from_db()
        self.assertEqual(resolve_application_chat_peer_id(self.application), 2000000002)

        self.event.org_chat_peer_id = 2000000005
        self.event.save(update_fields=["org_chat_peer_id"])
        self.application.refresh_from_db()
        self.assertEqual(resolve_application_chat_peer_id(self.application), 2000000005)

        with override_settings(VK_ORG_CHAT_URL=""):
            self.event.org_chat_peer_id = 0
            self.event.org_chat_url = ""
            self.event.save(update_fields=["org_chat_peer_id", "org_chat_url"])
            self.application.refresh_from_db()
            self.assertEqual(resolve_application_chat_peer_id(self.application), 2000000077)

    @override_settings(
        VK_CHAT_LINK_BASE_URL="", VK_ORG_CHAT_URL="https://vk.com/im?sel=c1", ALLOWED_HOSTS=["crm.example.test"]
    )
    def test_build_application_chat_link_relative_and_absolute(self):
        relative = build_application_chat_link(self.application)
        self.assertTrue(relative.startswith("/api/integrations/vk/chat-links/"))
        token = relative.rsplit("/chat-links/", 1)[1].rstrip("/")
        self.assertEqual(
            signing.loads(token, salt="vk-application-chat-link"),
            {"application_id": self.application.id, "chat_url": "https://vk.com/im?sel=c1"},
        )

        request = RequestFactory().get("/", HTTP_HOST="crm.example.test")
        absolute = build_application_chat_link(self.application, request)
        self.assertTrue(absolute.startswith("http://crm.example.test/api/integrations/vk/chat-links/"))

    @override_settings(VK_CHAT_LINK_BASE_URL="", VK_ORG_CHAT_URL="")
    def test_build_application_chat_link_without_chat_url(self):
        link = build_application_chat_link(self.application)
        token = link.rsplit("/chat-links/", 1)[1].rstrip("/")

        self.assertEqual(signing.loads(token, salt=CHAT_LINK_SALT), {"application_id": self.application.id})

    @override_settings(VK_CHAT_LINK_BASE_URL="https://crm.example.test/")
    def test_inject_application_chat_link(self):
        replaced = inject_application_chat_link("Ссылка: {chat_link}!", self.application)
        self.assertTrue(replaced.startswith("Ссылка: https://crm.example.test/api/integrations/vk/chat-links/"))
        self.assertTrue(replaced.endswith("/!"))

        appended = inject_application_chat_link("Привет", self.application)
        self.assertTrue(appended.startswith("Привет\n\nСсылка на орг.чат: https://crm.example.test/api/"))

    def test_build_testing_started_message_mentions_event(self):
        self.assertIn('"Практика"', build_testing_started_message(self.application))

    def test_get_application_organizers_includes_leader_once(self):
        organizer, _ = self.create_user("organizer@example.test")
        leader, _ = self.create_user("leader@example.test")
        self.event.organizers.add(organizer, leader)
        self.event.leader = leader
        self.event.save(update_fields=["leader"])
        self.application.refresh_from_db()

        recipients = get_application_organizers(self.application)

        self.assertCountEqual([user.id for user in recipients], [organizer.id, leader.id])

    def test_get_application_organizers_adds_leader_not_in_organizers(self):
        leader, _ = self.create_user("leader@example.test")
        self.event.leader = leader
        self.event.save(update_fields=["leader"])
        self.application.refresh_from_db()

        self.assertEqual([user.id for user in get_application_organizers(self.application)], [leader.id])

    def test_notify_organizers_about_vk_error_logs_warning(self):
        with self.assertLogs("integrations.vk.crm_notifications", level="WARNING") as logs:
            notify_organizers_about_vk_error(self.application, "нет доступа")

        self.assertIn(f"application_id={self.application.id}", logs.output[0])
        self.assertIn("нет доступа", logs.output[0])


class VKChatMembershipTests(VKFixturesMixin, TestCase):
    def setUp(self):
        self.setup_vk_data()
        self.event.org_chat_peer_id = 2000000001
        self.event.save(update_fields=["org_chat_peer_id"])
        self.application.refresh_from_db()

    def test_resolve_application_vk_user_id(self):
        self.assertEqual(resolve_application_vk_user_id(self.application), 123456)

        self.profile.vk_confirmed_at = None
        self.profile.save(update_fields=["vk_confirmed_at"])
        with self.assertRaisesMessage(ValueError, "не подтвердил"):
            resolve_application_vk_user_id(self.application)

        self.profile.vk = ""
        self.profile.vk_user_id = None
        self.profile.save(update_fields=["vk", "vk_user_id"])
        with self.assertRaisesMessage(ValueError, "не указан корректный VK"):
            resolve_application_vk_user_id(self.application)

    def test_mark_joined_by_vk_user_returns_none_without_profile_or_application(self):
        self.assertIsNone(mark_application_joined_chat_by_vk_user(vk_user_id=999999))

        self.application.status = self.testing_status
        self.application.save(update_fields=["status"])
        self.assertIsNone(mark_application_joined_chat_by_vk_user(vk_user_id=123456))

    @patch(RUN_CRM_AUTOMATION)
    def test_mark_joined_by_vk_user_prefers_application_of_matching_chat(self, run_automation):
        other_event = self.create_event(name="Вторая практика", org_chat_peer_id=2000000002)
        older = self.create_application(
            self.user, other_event, self.chat_link_sent_status, date_sub=timezone.now() - timedelta(days=1)
        )

        application = mark_application_joined_chat_by_vk_user(vk_user_id=123456, peer_id=2000000002)

        self.assertEqual(application.id, older.id)
        older.refresh_from_db()
        self.application.refresh_from_db()
        self.assertEqual(older.status.name, CHAT_JOINED)
        self.assertEqual(self.application.status.name, CHAT_LINK_SENT)
        run_automation.assert_called_once()
        self.assertEqual(run_automation.call_args.args[1], "notification.chat_link_opened")
        self.assertEqual(run_automation.call_args.kwargs["previous_status"], CHAT_LINK_SENT)

    @patch(RUN_CRM_AUTOMATION)
    def test_mark_joined_by_vk_user_without_peer_takes_latest(self, run_automation):
        application = mark_application_joined_chat_by_vk_user(vk_user_id=123456)

        self.assertEqual(application.id, self.application.id)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status.name, CHAT_JOINED)

    @patch(RUN_CRM_AUTOMATION)
    @patch("integrations.vk.crm_notifications.is_vk_user_in_conversation", return_value=True)
    def test_mark_joined_if_member_changes_status(self, member_check, run_automation):
        self.assertTrue(mark_application_joined_chat_if_member(self.application))

        member_check.assert_called_once_with(peer_id=2000000001, user_id=123456)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status.name, CHAT_JOINED)
        run_automation.assert_called_once()
        self.assertEqual(run_automation.call_args.args[1], "notification.chat_link_opened")

    @patch(RUN_CRM_AUTOMATION)
    @patch("integrations.vk.crm_notifications.is_vk_user_in_conversation", return_value=True)
    def test_mark_joined_if_member_already_joined_returns_true_without_automation(self, member_check, run_automation):
        self.application.status = self.chat_joined_status
        self.application.save(update_fields=["status"])

        self.assertTrue(mark_application_joined_chat_if_member(self.application))
        run_automation.assert_not_called()

    @patch("integrations.vk.crm_notifications.is_vk_user_in_conversation", return_value=False)
    def test_mark_joined_if_member_not_in_chat(self, member_check):
        self.assertFalse(mark_application_joined_chat_if_member(self.application))

        self.application.refresh_from_db()
        self.assertEqual(self.application.status.name, CHAT_LINK_SENT)

    @patch("integrations.vk.crm_notifications.is_vk_user_in_conversation", side_effect=VKAPIError(917, "no access"))
    def test_mark_joined_if_member_vk_error_returns_false(self, member_check):
        self.assertFalse(mark_application_joined_chat_if_member(self.application))

        self.application.refresh_from_db()
        self.assertEqual(self.application.status.name, CHAT_LINK_SENT)

    @override_settings(VK_ORG_CHAT_URL="", VK_ORG_CHAT_PEER_ID=0)
    @patch("integrations.vk.crm_notifications.is_vk_user_in_conversation")
    def test_mark_joined_if_member_without_peer_skips_check(self, member_check):
        self.event.org_chat_peer_id = 0
        self.event.save(update_fields=["org_chat_peer_id"])
        self.application.refresh_from_db()

        with self.assertLogs("integrations.vk.crm_notifications", level="WARNING"):
            self.assertFalse(mark_application_joined_chat_if_member(self.application))
        self.assertFalse(mark_application_joined_chat_if_member(self.application, log_missing_peer=False))
        member_check.assert_not_called()

    @patch("integrations.vk.crm_notifications.is_vk_user_in_conversation")
    def test_scan_skips_unconfirmed_profiles(self, member_check):
        self.profile.vk_confirmed_at = None
        self.profile.save(update_fields=["vk_confirmed_at"])

        result = scan_chat_membership_for_sent_applications()

        self.assertEqual(result, {"scanned": 1, "changed": 0})
        member_check.assert_not_called()


class VKApplicationMessagingTests(VKFixturesMixin, TestCase):
    def setUp(self):
        self.setup_vk_data()

    @patch("integrations.vk.crm_notifications.send_vk_message", return_value=5)
    def test_send_application_vk_message_uses_user_id(self, send_mock):
        self.assertEqual(send_application_vk_message(self.application, "Текст"), 5)

        send_mock.assert_called_once_with(user_id=123456, message="Текст", keyboard=None, attachments=None)

    @patch("integrations.vk.crm_notifications.send_vk_message", return_value=6)
    def test_send_application_vk_message_with_attachments_uses_peer_id(self, send_mock):
        send_application_vk_message(self.application, "Текст", attachments=["doc1_2"])

        send_mock.assert_called_once_with(peer_id=123456, message="Текст", keyboard=None, attachments=["doc1_2"])

    @patch("integrations.vk.crm_notifications.upload_vk_document", side_effect=["doc1_1", "doc1_2"])
    def test_upload_application_vk_documents(self, upload_mock):
        documents = [
            SimpleNamespace(file_name="a.pdf", content=b"A"),
            SimpleNamespace(file_name="b.pdf", content=memoryview(b"B")),
        ]

        attachments = upload_application_vk_documents(self.application, documents)

        self.assertEqual(attachments, ["doc1_1", "doc1_2"])
        self.assertEqual(upload_mock.call_args_list[0].kwargs, {"peer_id": 123456, "file_name": "a.pdf", "content": b"A"})
        self.assertEqual(upload_mock.call_args_list[1].kwargs["content"], b"B")

    @patch("integrations.vk.crm_notifications.send_vk_message")
    def test_notify_testing_started_does_nothing_when_vk_disabled(self, send_mock):
        self.application.status = self.testing_status
        self.application.save(update_fields=["status"])

        self.assertIsNone(notify_application_testing_started(self.application, previous_status_id=None))
        send_mock.assert_not_called()

    @override_settings(VK_ENABLED=True)
    @patch("integrations.vk.crm_notifications.send_vk_message")
    def test_notify_testing_started_skips_other_status(self, send_mock):
        self.assertIsNone(notify_application_testing_started(self.application, previous_status_id=None))
        send_mock.assert_not_called()

    @override_settings(VK_ENABLED=True)
    @patch("integrations.vk.crm_notifications.send_vk_message", side_effect=VKAPIError(901, "no permission"))
    def test_notify_testing_started_swallows_vk_error(self, send_mock):
        self.application.status = self.testing_status
        self.application.save(update_fields=["status"])

        with self.assertLogs("integrations.vk.crm_notifications", level="WARNING"):
            self.assertIsNone(notify_application_testing_started(self.application, previous_status_id=None))
        send_mock.assert_called_once()


# ---------------------------------------------------------------------------
# planner_invites.py
# ---------------------------------------------------------------------------


class VKPlannerInviteKeyboardContractTests(TestCase):
    """Payload кнопок уже отправлен пользователям — формат менять нельзя."""

    def test_planner_invite_keyboard_payloads(self):
        keyboard = build_planner_invite_keyboard(42)

        self.assertTrue(keyboard["inline"])
        accept, decline = keyboard["buttons"][0]
        self.assertEqual(accept["action"]["type"], "callback")
        self.assertEqual(accept["action"]["label"], "Принять")
        self.assertEqual(accept["action"]["payload"], {"type": "planner_invite", "action": "accept", "application_id": 42})
        self.assertEqual(decline["action"]["label"], "Отказаться")
        self.assertEqual(decline["action"]["payload"], {"type": "planner_invite", "action": "decline", "application_id": 42})

    def test_decline_confirmation_keyboard_payloads(self):
        yes, no = build_decline_confirmation_keyboard(42)["buttons"][0]

        self.assertEqual(
            yes["action"]["payload"], {"type": "planner_invite", "action": "decline_confirm", "application_id": 42}
        )
        self.assertEqual(
            no["action"]["payload"], {"type": "planner_invite", "action": "decline_cancel", "application_id": 42}
        )

    def test_parse_vk_button_payload(self):
        self.assertEqual(parse_vk_button_payload({"a": 1}), {"a": 1})
        self.assertEqual(parse_vk_button_payload('{"a": 1}'), {"a": 1})
        self.assertIsNone(parse_vk_button_payload(""))
        self.assertIsNone(parse_vk_button_payload(None))
        self.assertIsNone(parse_vk_button_payload("{broken"))
        self.assertIsNone(parse_vk_button_payload("[1, 2]"))

    def test_start_commands(self):
        for text in ("Начать", "НАЧАТЬ", " начать ", "start", "/start", "старт"):
            self.assertTrue(is_vk_start_message({"text": text}), text)
        for payload in ('{"command": "start"}', '{"type": "start"}', '{"action": "Начать"}', {"command": "/start"}):
            self.assertTrue(is_vk_start_message({"text": "", "payload": payload}), payload)
        self.assertFalse(is_vk_start_message({"text": "привет"}))
        self.assertFalse(is_vk_start_message({"text": "привет", "payload": '{"command": "other"}'}))


@override_settings(VK_ENABLED=True)
class VKPlannerInviteFlowTests(VKFixturesMixin, TestCase):
    def setUp(self):
        self.setup_vk_data()
        self.application.status = self.enrollment_closed_status
        self.application.save(update_fields=["status"])

    def payload(self, action, application_id=None):
        return {"type": "planner_invite", "action": action, "application_id": application_id or self.application.id}

    def test_resolve_vk_application_user_id(self):
        self.assertEqual(resolve_vk_application_user_id(self.application), 123456)

        self.profile.vk_confirmed_at = None
        self.profile.save(update_fields=["vk_confirmed_at"])
        self.assertIsNone(resolve_vk_application_user_id(self.application))
        self.assertEqual(resolve_vk_application_user_id(self.application, require_confirmed=False), 123456)

        Profile.objects.filter(pk=self.profile.pk).delete()
        self.assertIsNone(resolve_vk_application_user_id(self.application))

    @patch("integrations.vk.planner_invites.send_vk_message", return_value=8)
    def test_send_planner_invite_defaults(self, send_mock):
        self.assertEqual(send_planner_invite(self.application), 8)

        kwargs = send_mock.call_args.kwargs
        self.assertEqual(kwargs["user_id"], 123456)
        self.assertIn('"Практика"', kwargs["message"])
        self.assertEqual(kwargs["keyboard"], build_planner_invite_keyboard(self.application.id))

    @patch("integrations.vk.planner_invites.send_vk_message", return_value=9)
    def test_send_start_message_uses_custom_message(self, send_mock):
        send_start_message(self.application, message="Свой текст")

        self.assertEqual(send_mock.call_args.kwargs["message"], "Свой текст")
        self.assertEqual(send_mock.call_args.kwargs["keyboard"], build_planner_invite_keyboard(self.application.id))

    @patch("integrations.vk.planner_invites.send_vk_message")
    def test_send_planner_invite_requires_confirmed_vk(self, send_mock):
        self.profile.vk_confirmed_at = None
        self.profile.save(update_fields=["vk_confirmed_at"])

        with self.assertRaises(ValueError):
            send_planner_invite(self.application)
        with self.assertRaises(ValueError):
            send_start_message(self.application)
        send_mock.assert_not_called()

    @patch("integrations.vk.planner_invites.send_planner_invite")
    def test_send_planner_invites_recipient_modes(self, send_invite):
        declined = self.create_application(self.user, self.event, self.get_status(DECLINED_PSH))
        testing = self.create_application(self.user, self.event, self.testing_status)

        result = send_planner_invites_for_event(self.event.id, recipient_mode="declined", message="Текст")
        self.assertEqual(result, {"sent": 1, "failed": 0, "skipped": 0})
        self.assertEqual(send_invite.call_args.args[0].id, declined.id)
        self.assertEqual(send_invite.call_args.kwargs, {"message": "Текст"})

        send_invite.reset_mock()
        result = send_planner_invites_for_event(self.event.id, recipient_mode="all")
        self.assertEqual(result["sent"], 3)
        self.assertCountEqual(
            [call.args[0].id for call in send_invite.call_args_list], [self.application.id, declined.id, testing.id]
        )

    @patch("integrations.vk.planner_invites.send_planner_invite", side_effect=ValueError("нет VK"))
    def test_send_planner_invites_counts_failures(self, send_invite):
        with self.assertLogs("integrations.vk.crm_notifications", level="WARNING"):
            result = send_planner_invites_for_event(self.event.id)

        self.assertEqual(result, {"sent": 0, "failed": 1, "skipped": 0})

    @override_settings(VK_ENABLED=False)
    @patch("integrations.vk.planner_invites.send_planner_invite")
    def test_send_planner_invites_disabled_vk(self, send_invite):
        self.assertEqual(send_planner_invites_for_event(self.event.id), {"sent": 0, "failed": 0, "skipped": 0})
        send_invite.assert_not_called()

    @patch("integrations.vk.planner_invites.send_vk_message")
    def test_payload_without_valid_application_id(self, send_mock):
        result = handle_planner_invite_payload(from_id=123456, payload={"type": "planner_invite", "action": "accept"})

        self.assertEqual(result, "Заявка не определена")
        self.assertEqual(send_mock.call_args.kwargs["message"], "Не удалось определить заявку для этого действия.")

    @patch("integrations.vk.planner_invites.send_vk_message")
    def test_payload_for_missing_application(self, send_mock):
        result = handle_planner_invite_payload(from_id=123456, payload=self.payload("accept", application_id=999999))

        self.assertEqual(result, "Заявка не найдена")
        self.assertEqual(send_mock.call_args.kwargs["message"], "Заявка для этого действия не найдена.")

    @patch(RUN_CRM_AUTOMATION)
    @patch("integrations.vk.planner_invites.send_vk_message")
    def test_payload_from_other_vk_user_is_rejected(self, send_mock, run_automation):
        result = handle_planner_invite_payload(from_id=654321, payload=self.payload("accept"))

        self.assertEqual(result, "Кнопка относится к другой заявке")
        send_mock.assert_called_once_with(user_id=654321, message="Эта кнопка относится к другой заявке.")
        self.application.refresh_from_db()
        self.assertEqual(self.application.status.name, ENROLLMENT_CLOSED)
        run_automation.assert_not_called()

    @patch(RUN_CRM_AUTOMATION)
    @patch("integrations.vk.planner_invites.send_vk_message")
    def test_accept_sets_started_status_and_runs_automation(self, send_mock, run_automation):
        result = handle_planner_invite_payload(from_id=123456, payload=self.payload("accept"))

        self.assertEqual(result, "Готовность подтверждена")
        self.application.refresh_from_db()
        self.assertEqual(self.application.status.name, STARTED_PSH)
        run_automation.assert_called_once()
        self.assertEqual(run_automation.call_args.args[1], "request.status_changed")
        self.assertEqual(run_automation.call_args.kwargs["previous_status"], ENROLLMENT_CLOSED)

    @patch(RUN_CRM_AUTOMATION)
    @patch("integrations.vk.planner_invites.send_vk_message")
    def test_accept_when_already_started(self, send_mock, run_automation):
        self.application.status = self.get_status(STARTED_PSH)
        self.application.save(update_fields=["status"])

        result = handle_planner_invite_payload(from_id=123456, payload=self.payload("accept"))

        self.assertEqual(result, "Готовность уже подтверждена")
        run_automation.assert_not_called()

    @patch(RUN_CRM_AUTOMATION)
    @patch("integrations.vk.planner_invites.send_vk_message")
    def test_accept_from_disallowed_status(self, send_mock, run_automation):
        self.application.status = self.testing_status
        self.application.save(update_fields=["status"])

        result = handle_planner_invite_payload(from_id=123456, payload=self.payload("accept"))

        self.assertEqual(result, "Статус заявки не позволяет подтвердить участие")
        self.assertIn("«Прохождение тестирования»", send_mock.call_args.kwargs["message"])
        self.application.refresh_from_db()
        self.assertEqual(self.application.status.name, "Прохождение тестирования")
        run_automation.assert_not_called()

    @patch(RUN_CRM_AUTOMATION)
    @patch("integrations.vk.planner_invites.send_vk_message")
    def test_decline_confirm_when_already_declined(self, send_mock, run_automation):
        self.application.status = self.get_status(DECLINED_PSH)
        self.application.save(update_fields=["status"])

        result = handle_planner_invite_payload(from_id=123456, payload=self.payload("decline_confirm"))

        self.assertEqual(result, "Отказ уже зафиксирован")
        run_automation.assert_not_called()

    @patch(RUN_CRM_AUTOMATION)
    @patch("integrations.vk.planner_invites.send_vk_message")
    def test_decline_confirm_from_disallowed_status(self, send_mock, run_automation):
        self.application.status = self.testing_status
        self.application.save(update_fields=["status"])

        result = handle_planner_invite_payload(from_id=123456, payload=self.payload("decline_confirm"))

        self.assertEqual(result, "Статус заявки не позволяет отказаться")
        self.application.refresh_from_db()
        self.assertEqual(self.application.status.name, "Прохождение тестирования")
        run_automation.assert_not_called()

    @patch(RUN_CRM_AUTOMATION)
    @patch("integrations.vk.planner_invites.send_vk_message")
    def test_decline_confirm_runs_automation(self, send_mock, run_automation):
        result = handle_planner_invite_payload(from_id=123456, payload=self.payload("decline_confirm"))

        self.assertEqual(result, "Отказ зафиксирован")
        self.application.refresh_from_db()
        self.assertEqual(self.application.status.name, DECLINED_PSH)
        self.assertEqual(run_automation.call_args.kwargs["previous_status"], ENROLLMENT_CLOSED)

    @patch("integrations.vk.planner_invites.send_vk_message")
    def test_decline_cancel_resends_invite_keyboard(self, send_mock):
        result = handle_planner_invite_payload(from_id=123456, payload=self.payload("decline_cancel"))

        self.assertEqual(result, "Отказ отменён")
        self.assertEqual(send_mock.call_args.kwargs["keyboard"], build_planner_invite_keyboard(self.application.id))
        self.application.refresh_from_db()
        self.assertEqual(self.application.status.name, ENROLLMENT_CLOSED)

    @patch("integrations.vk.planner_invites.send_vk_message")
    def test_unknown_action(self, send_mock):
        result = handle_planner_invite_payload(from_id=123456, payload=self.payload("something"))

        self.assertEqual(result, "Неизвестное действие")
        send_mock.assert_not_called()


@override_settings(VK_ENABLED=True)
class VKIncomingMessageRoutingTests(VKFixturesMixin, TestCase):
    def setUp(self):
        self.setup_vk_data()

    def test_message_new_with_unexpected_shape(self):
        self.assertFalse(handle_vk_message_new_event({"object": "bad"}))
        self.assertFalse(handle_vk_message_new_event({"object": {"message": "bad"}}))

    @patch("integrations.vk.planner_invites.send_vk_message")
    def test_message_new_with_regular_text_is_not_handled(self, send_mock):
        self.assertFalse(handle_vk_message_new_event({"object": {"message": {"from_id": 123456, "text": "привет"}}}))
        send_mock.assert_not_called()

    @patch("integrations.vk.planner_invites.handle_planner_invite_payload")
    def test_message_new_with_planner_payload_routes_to_handler(self, handler):
        payload = {"type": "planner_invite", "action": "accept", "application_id": self.application.id}

        handled = handle_vk_message_new_event(
            {"object": {"message": {"from_id": 123456, "text": "Принять", "payload": json.dumps(payload)}}}
        )

        self.assertTrue(handled)
        handler.assert_called_once_with(from_id=123456, payload=payload)

    @patch("integrations.vk.planner_invites.handle_planner_invite_payload")
    def test_message_new_with_planner_payload_and_bad_from_id(self, handler):
        payload = {"type": "planner_invite", "action": "accept", "application_id": 1}

        self.assertTrue(handle_vk_message_new_event({"object": {"message": {"from_id": "x", "payload": payload}}}))
        handler.assert_not_called()

    @patch("integrations.vk.planner_invites.send_vk_message")
    def test_peer_debug_ignores_private_dialog_and_bad_peer(self, send_mock):
        self.assertFalse(handle_vk_peer_debug_message({"text": "peer", "peer_id": 123456}))
        self.assertTrue(handle_vk_peer_debug_message({"text": "/peer", "peer_id": "bad"}))
        self.assertFalse(handle_vk_peer_debug_message({"text": "привет", "peer_id": 2000000001}))
        send_mock.assert_not_called()

    @patch("integrations.vk.planner_invites.send_vk_message")
    def test_peer_debug_commands_in_chat(self, send_mock):
        for command in ("peer", "/peer", "peer_id", "/peer_id", "PEER"):
            send_mock.reset_mock()
            self.assertTrue(handle_vk_peer_debug_message({"text": command, "peer_id": 2000000005}), command)
            send_mock.assert_called_once_with(peer_id=2000000005, message="ID этой беседы для CRM: 2000000005")

    def test_chat_join_message_variants(self):
        self.assertFalse(handle_vk_chat_join_message({"text": "привет"}))
        self.assertFalse(handle_vk_chat_join_message({"action": {"type": "chat_kick_user"}}))
        self.assertTrue(handle_vk_chat_join_message({"action": {"type": "chat_invite_user", "member_id": "bad"}}))

    @patch(RUN_CRM_AUTOMATION)
    def test_chat_join_via_invite_uses_from_id_when_member_missing(self, run_automation):
        handled = handle_vk_chat_join_message(
            {"from_id": 123456, "peer_id": "bad", "action": {"type": "chat_invite_user"}}
        )

        self.assertTrue(handled)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status.name, CHAT_JOINED)

    def test_chat_join_without_matching_application_is_logged(self):
        with self.assertLogs("integrations.vk.planner_invites", level="WARNING") as logs:
            handled = handle_vk_chat_join_message(
                {"peer_id": 2000000001, "action": {"type": "chat_invite_user_by_link", "member_id": 999999}}
            )

        self.assertTrue(handled)
        self.assertIn("no matching application", logs.output[0])

    @patch("integrations.vk.planner_invites.send_vk_message")
    def test_start_message_for_unknown_vk_user(self, send_mock):
        self.assertTrue(handle_vk_start_message({"from_id": 555000, "text": "start"}))

        self.assertEqual(send_mock.call_args.kwargs["user_id"], 555000)
        self.assertIn("Не удалось связать ваш VK", send_mock.call_args.kwargs["message"])

    @patch("integrations.vk.planner_invites.send_vk_message")
    def test_start_message_for_known_vk_user(self, send_mock):
        self.assertTrue(handle_vk_start_message({"from_id": 123456, "text": "старт"}))

        self.assertIn("VK подтвержден", send_mock.call_args.kwargs["message"])

    @patch("integrations.vk.planner_invites.send_vk_message")
    def test_start_message_with_bad_from_id(self, send_mock):
        self.assertTrue(handle_vk_start_message({"from_id": "bad", "text": "/start"}))
        self.assertFalse(handle_vk_start_message({"from_id": 1, "text": "привет"}))
        send_mock.assert_not_called()

    def test_message_event_with_unexpected_payload(self):
        self.assertFalse(handle_vk_message_event({"object": "bad"}))
        self.assertFalse(handle_vk_message_event({"object": {"payload": {"type": "other"}}}))
        self.assertTrue(
            handle_vk_message_event({"object": {"user_id": "bad", "payload": {"type": "planner_invite"}}})
        )

    @patch("integrations.vk.planner_invites.handle_planner_invite_payload")
    @patch("integrations.vk.planner_invites.delete_vk_message", side_effect=VKConfigurationError("off"))
    @patch("integrations.vk.planner_invites.answer_vk_message_event", side_effect=VKAPIError(1, "fail"))
    def test_message_event_tolerates_vk_errors(self, answer_mock, delete_mock, handler):
        payload = {"type": "planner_invite", "action": "decline", "application_id": self.application.id}

        handled = handle_vk_message_event(
            {
                "object": {
                    "user_id": 123456,
                    "peer_id": "bad",
                    "event_id": "evt",
                    "conversation_message_id": "bad",
                    "message_id": 77,
                    "payload": json.dumps(payload),
                }
            }
        )

        self.assertTrue(handled)
        answer_mock.assert_called_once_with(event_id="evt", user_id=123456, peer_id=123456, text="Действие принято")
        delete_mock.assert_called_once_with(peer_id=123456, message_id=77, conversation_message_id=None)
        handler.assert_called_once_with(from_id=123456, payload=payload)


# ---------------------------------------------------------------------------
# users/vk_profiles.py
# ---------------------------------------------------------------------------


class VKProfileHelpersTests(VKFixturesMixin, TestCase):
    def setUp(self):
        self.user, self.profile = self.create_user("student@example.test", vk_user_id=123456)

    @override_settings(VK_GROUP_ID="")
    def test_get_vk_bot_url_without_group(self):
        self.assertEqual(get_vk_bot_url(), "")

    @override_settings(VK_GROUP_ID="club42")
    def test_get_vk_bot_url_with_group(self):
        self.assertEqual(get_vk_bot_url(), "https://vk.com/im?sel=-42")

    def test_resolve_profile_vk_user_id_offline(self):
        self.assertEqual(resolve_profile_vk_user_id("https://vk.com/id77"), 77)
        self.assertIsNone(resolve_profile_vk_user_id("https://vk.com/screen_name"))

    @override_settings(VK_ENABLED=True, VK_ACCESS_TOKEN="token-example")
    @patch("users.vk_profiles.resolve_vk_user_id", return_value=88)
    def test_resolve_profile_vk_user_id_uses_vk_api(self, resolve_mock):
        self.assertEqual(resolve_profile_vk_user_id("https://vk.com/screen_name"), 88)
        resolve_mock.assert_called_once_with("https://vk.com/screen_name")

    @override_settings(VK_ENABLED=True, VK_ACCESS_TOKEN="token-example")
    @patch("users.vk_profiles.resolve_vk_user_id", side_effect=VKAPIError(5, "fail"))
    def test_resolve_profile_vk_user_id_swallows_vk_errors(self, resolve_mock):
        self.assertIsNone(resolve_profile_vk_user_id("https://vk.com/screen_name"))

    def test_refresh_profile_vk_user_id(self):
        self.assertEqual(refresh_profile_vk_user_id(self.profile), 123456)

        self.profile.vk = "https://vk.com/id999"
        self.profile.save(update_fields=["vk"])
        self.assertEqual(refresh_profile_vk_user_id(self.profile), 123456)
        self.assertEqual(refresh_profile_vk_user_id(self.profile, force=True), 999)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.vk_user_id, 999)

    def test_reset_confirmation_only_when_vk_changed(self):
        reset_profile_vk_confirmation_if_changed(self.profile, " https://vk.com/id123456 ")
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.vk_confirmed_at)

        self.profile.vk = "https://vk.com/id42"
        reset_profile_vk_confirmation_if_changed(self.profile, "https://vk.com/id123456")
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.vk_user_id, 42)
        self.assertIsNone(self.profile.vk_confirmed_at)

    def test_confirm_profile_by_stored_vk_user_id(self):
        self.profile.vk_confirmed_at = None
        self.profile.save(update_fields=["vk_confirmed_at"])

        confirmed = confirm_profile_by_vk_user_id(123456)

        self.assertEqual(confirmed.pk, self.profile.pk)
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.vk_confirmed_at)

    def test_confirm_profile_by_vk_user_id_without_match(self):
        self.assertIsNone(confirm_profile_by_vk_user_id(555000))
