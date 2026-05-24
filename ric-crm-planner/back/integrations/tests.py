import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import signing
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from integrations.vk.crm_notifications import (
    CHAT_LINK_SALT,
    notify_application_testing_started,
    scan_chat_membership_for_sent_applications,
)
from integrations.vk.planner_invites import (
    build_welcome_keyboard,
    handle_planner_invite_payload,
    handle_vk_message_new_event,
    handle_vk_start_message,
    send_planner_invites_for_event,
)
from integrations.vk.services import VKAPIError, extract_vk_screen_name, normalize_vk_group_id, send_vk_message
from users.automation_engine import run_crm_automation
from users.models import Application, CRMAutomationConfig, Event, Profile, Status


class VKCallbackTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/integrations/vk/callback/"

    @override_settings(VK_CONFIRMATION_CODE="confirm-code", VK_GROUP_ID="club123")
    def test_callback_confirmation_returns_vk_confirmation_code(self):
        response = self.client.post(self.url, {"type": "confirmation", "group_id": 123}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.content.decode(), "confirm-code")

    @override_settings(VK_CONFIRMATION_CODE="confirm-code", VK_GROUP_ID="club123")
    def test_callback_confirmation_rejects_wrong_group_id(self):
        response = self.client.post(self.url, {"type": "confirmation", "group_id": 456}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(VK_CALLBACK_SECRET="secret")
    def test_callback_rejects_invalid_secret(self):
        response = self.client.post(self.url, {"type": "message_new", "secret": "wrong"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(VK_CALLBACK_SECRET="secret")
    def test_callback_accepts_valid_secret(self):
        response = self.client.post(self.url, {"type": "message_new", "secret": "secret"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.content.decode(), "ok")


class VKServiceTests(TestCase):
    def test_normalize_vk_group_id_accepts_club_prefix(self):
        self.assertEqual(normalize_vk_group_id("club238353336"), "238353336")

    def test_extract_vk_screen_name_accepts_profile_link(self):
        self.assertEqual(extract_vk_screen_name("https://vk.com/projectant"), "projectant")

    @override_settings(
        VK_ENABLED=True,
        VK_ACCESS_TOKEN="token",
        VK_API_VERSION="5.199",
        VK_API_BASE_URL="https://api.vk.com/method",
        VK_REQUEST_TIMEOUT_SECONDS=5,
    )
    @patch("integrations.vk.services.urllib.request.urlopen")
    def test_send_vk_message_returns_message_id(self, urlopen):
        urlopen.return_value.__enter__.return_value.read.return_value = json.dumps({"response": 777}).encode()

        message_id = send_vk_message(user_id=1, message="Тест")

        self.assertEqual(message_id, 777)
        self.assertTrue(urlopen.called)

    @override_settings(
        VK_ENABLED=True,
        VK_ACCESS_TOKEN="token",
        VK_API_VERSION="5.199",
        VK_API_BASE_URL="https://api.vk.com/method",
        VK_REQUEST_TIMEOUT_SECONDS=5,
    )
    @patch("integrations.vk.services.urllib.request.urlopen")
    def test_send_vk_message_raises_vk_api_error(self, urlopen):
        urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(
            {"error": {"error_code": 901, "error_msg": "Can't send messages for users without permission"}}
        ).encode()

        with self.assertRaises(VKAPIError):
            send_vk_message(user_id=1, message="Тест")


class VKCRMNotificationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="student@example.com",
            email="student@example.com",
            password="password",
            first_name="Иван",
            last_name="Иванов",
            is_active=True,
        )
        self.profile, _ = Profile.objects.update_or_create(
            user=self.user,
            defaults={
                "surname": "Иванов",
                "name": "Иван",
                "email": "student@example.com",
                "course": 1,
                "vk": "https://vk.com/id123456",
                "vk_user_id": 123456,
                "vk_confirmed_at": timezone.now(),
            },
        )
        self.event = Event.objects.create(
            name="Практика",
            stage="Набор",
            start_date="2026-05-01",
            end_date="2026-05-10",
            end_app_date=timezone.now(),
        )
        self.default_status = Status.objects.create(name="Прислал заявку")
        self.testing_status = Status.objects.create(name="Прохождение тестирования")
        self.chat_link_sent_status = Status.objects.create(name="Отправлена ссылка на орг. чат")
        self.chat_joined_status = Status.objects.create(name="Добавился в орг. чат")
        self.application = Application.objects.create(
            user=self.user,
            event=self.event,
            date_sub=timezone.now(),
            date_end=timezone.now(),
            status=self.testing_status,
        )

    @override_settings(VK_ENABLED=True)
    @patch("integrations.vk.crm_notifications.send_vk_message")
    def test_notify_application_testing_started_sends_vk_message(self, send_vk_message_mock):
        send_vk_message_mock.return_value = 3

        message_id = notify_application_testing_started(
            self.application,
            previous_status_id=self.default_status.id,
        )

        self.assertEqual(message_id, 3)
        send_vk_message_mock.assert_called_once()
        self.assertEqual(send_vk_message_mock.call_args.kwargs["user_id"], 123456)

    @override_settings(VK_ENABLED=True)
    @patch("integrations.vk.crm_notifications.send_vk_message")
    def test_notify_application_testing_started_skips_same_status(self, send_vk_message_mock):
        notify_application_testing_started(
            self.application,
            previous_status_id=self.testing_status.id,
        )

        send_vk_message_mock.assert_not_called()

    @override_settings(VK_ORG_CHAT_URL="https://vk.com/im?sel=c1", VK_CHAT_LINK_MAX_AGE_SECONDS=3600)
    def test_chat_link_redirect_does_not_update_application_status(self):
        self.application.status = self.chat_link_sent_status
        self.application.save(update_fields=["status"])
        token = signing.dumps({"application_id": self.application.id}, salt=CHAT_LINK_SALT)

        response = self.client.get(f"/api/integrations/vk/chat-links/{token}/")

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(response["Location"], "https://vk.com/im?sel=c1")
        self.application.refresh_from_db()
        self.assertEqual(self.application.status.name, self.chat_link_sent_status.name)

    @override_settings(VK_ENABLED=True)
    def test_vk_chat_join_service_message_updates_application_status(self):
        self.application.status = self.chat_link_sent_status
        self.application.save(update_fields=["status"])

        handled = handle_vk_message_new_event(
            {
                "type": "message_new",
                "object": {
                    "message": {
                        "from_id": 123456,
                        "peer_id": 2000000001,
                        "text": "",
                        "action": {"type": "chat_invite_user_by_link", "member_id": 123456},
                    }
                },
            }
        )

        self.assertTrue(handled)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status.name, self.chat_joined_status.name)

    @override_settings(VK_ENABLED=True)
    @patch("integrations.vk.planner_invites.send_vk_message")
    def test_vk_peer_debug_message_replies_with_chat_peer_id(self, send_vk_message_mock):
        handled = handle_vk_message_new_event(
            {
                "type": "message_new",
                "object": {
                    "message": {
                        "from_id": 123456,
                        "peer_id": 2000000223,
                        "text": "/peer",
                    }
                },
            }
        )

        self.assertTrue(handled)
        send_vk_message_mock.assert_called_once_with(
            peer_id=2000000223,
            message="ID этой беседы для CRM: 2000000223",
        )

    @override_settings(VK_ENABLED=True, VK_ORG_CHAT_URL="https://vk.com/im?sel=c1")
    @patch("integrations.vk.crm_notifications.send_vk_message")
    @patch("integrations.vk.crm_notifications.is_vk_user_in_conversation", return_value=True)
    def test_chat_link_robot_skips_message_when_user_already_in_chat(self, member_check_mock, send_vk_message_mock):
        self.application.status = self.chat_link_sent_status
        self.application.save(update_fields=["status"])
        CRMAutomationConfig.objects.create(
            scope="crm",
            event=self.event,
            stages=[
                {"id": "application-chat-link-sent", "title": self.chat_link_sent_status.name, "description": ""},
                {"id": "application-joined-chat", "title": self.chat_joined_status.name, "description": ""},
            ],
            triggers=[],
            robots=[
                {
                    "id": "chat-link",
                    "stageId": "application-chat-link-sent",
                    "title": "Chat link",
                    "description": "",
                    "action": "chat.link.vk",
                    "enabled": True,
                    "settings": {"runMode": "queue", "timing": "immediate", "delayMinutes": 0, "condition": {"mode": "all", "rules": []}},
                    "subject": "Chat",
                    "message": "Join {chat_link}",
                },
                {
                    "id": "chat-link-copy",
                    "stageId": "application-chat-link-sent",
                    "title": "Chat link copy",
                    "description": "",
                    "action": "chat.link.vk",
                    "enabled": True,
                    "settings": {"runMode": "queue", "timing": "immediate", "delayMinutes": 0, "condition": {"mode": "all", "rules": []}},
                    "subject": "Chat copy",
                    "message": "Join again {chat_link}",
                }
            ],
        )

        run_crm_automation(self.application, "request.status_changed", previous_status=self.testing_status.name)

        self.assertEqual(member_check_mock.call_count, 2)
        member_check_mock.assert_any_call(peer_id=2000000001, user_id=123456)
        send_vk_message_mock.assert_not_called()
        self.application.refresh_from_db()
        self.assertEqual(self.application.status.name, self.chat_joined_status.name)

    @override_settings(VK_ENABLED=True, VK_ORG_CHAT_URL="https://vk.com/im?sel=c1")
    @patch("integrations.vk.crm_notifications.is_vk_user_in_conversation", return_value=True)
    def test_chat_membership_scan_updates_application_when_vk_event_is_missing(self, member_check_mock):
        self.application.status = self.chat_link_sent_status
        self.application.save(update_fields=["status"])

        result = scan_chat_membership_for_sent_applications()

        self.assertEqual(result["scanned"], 1)
        self.assertEqual(result["changed"], 1)
        member_check_mock.assert_called_once_with(peer_id=2000000001, user_id=123456)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status.name, self.chat_joined_status.name)

    @override_settings(VK_ORG_CHAT_URL="", VK_CHAT_LINK_MAX_AGE_SECONDS=3600)
    def test_chat_link_redirect_uses_event_org_chat_url(self):
        self.application.status = self.chat_link_sent_status
        self.application.save(update_fields=["status"])
        self.event.org_chat_url = "https://vk.me/join/event-chat"
        self.event.save(update_fields=["org_chat_url"])
        token = signing.dumps({"application_id": self.application.id}, salt=CHAT_LINK_SALT)

        response = self.client.get(f"/api/integrations/vk/chat-links/{token}/")

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(response["Location"], "https://vk.me/join/event-chat")

    @override_settings(VK_ORG_CHAT_URL="https://vk.com/im?sel=c1", VK_CHAT_LINK_MAX_AGE_SECONDS=3600)
    def test_chat_link_redirect_does_not_update_wrong_current_status(self):
        token = signing.dumps({"application_id": self.application.id}, salt=CHAT_LINK_SALT)

        response = self.client.get(f"/api/integrations/vk/chat-links/{token}/")

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status.name, "Прохождение тестирования")

    @override_settings(VK_ENABLED=True)
    @patch("integrations.vk.planner_invites.send_vk_message")
    def test_send_planner_invites_for_event_sends_joined_chat_applications(self, send_vk_message_mock):
        send_vk_message_mock.return_value = 9
        self.application.status = self.chat_joined_status
        self.application.save(update_fields=["status"])

        result = send_planner_invites_for_event(self.event.id)

        self.assertEqual(result, {"sent": 1, "failed": 0, "skipped": 0})
        send_vk_message_mock.assert_called_once()
        self.assertEqual(send_vk_message_mock.call_args.kwargs["user_id"], 123456)
        keyboard = send_vk_message_mock.call_args.kwargs["keyboard"]
        self.assertEqual(keyboard["buttons"][0][0]["action"]["type"], "callback")

    @override_settings(VK_ENABLED=True, VK_CALLBACK_SECRET="")
    @patch("integrations.vk.views.handle_vk_message_event")
    def test_vk_message_event_callback_routes_to_handler(self, handle_event_mock):
        response = self.client.post(
            "/api/integrations/vk/callback/",
            {
                "type": "message_event",
                "object": {
                    "user_id": 123456,
                    "peer_id": 123456,
                    "event_id": "event-id",
                    "payload": {"type": "planner_invite", "action": "accept", "application_id": self.application.id},
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        handle_event_mock.assert_called_once()

    @override_settings(VK_ENABLED=True)
    @patch("integrations.vk.planner_invites.send_vk_message")
    @patch("integrations.vk.planner_invites.delete_vk_message")
    @patch("integrations.vk.planner_invites.answer_vk_message_event")
    def test_vk_message_event_deletes_source_message(self, answer_event_mock, delete_message_mock, send_vk_message_mock):
        self.application.status = self.chat_joined_status
        self.application.save(update_fields=["status"])

        from integrations.vk.planner_invites import handle_vk_message_event

        handled = handle_vk_message_event(
            {
                "type": "message_event",
                "object": {
                    "user_id": 123456,
                    "peer_id": 123456,
                    "event_id": "event-id",
                    "conversation_message_id": 55,
                    "payload": {"type": "planner_invite", "action": "accept", "application_id": self.application.id},
                },
            }
        )

        self.assertTrue(handled)
        answer_event_mock.assert_called_once()
        delete_message_mock.assert_called_once_with(
            peer_id=123456,
            message_id=None,
            conversation_message_id=55,
        )
        send_vk_message_mock.assert_called_once()

    @override_settings(VK_ENABLED=True, VK_CALLBACK_SECRET="")
    @patch("integrations.vk.views.handle_vk_message_new_event")
    def test_vk_message_new_callback_routes_to_handler(self, handle_new_mock):
        response = self.client.post(
            "/api/integrations/vk/callback/",
            {
                "type": "message_new",
                "object": {"message": {"from_id": 123456, "text": "Начать"}},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        handle_new_mock.assert_called_once()

    @override_settings(VK_ENABLED=True, VK_BOT_FRONTEND_URL="https://crm.example.test")
    @patch("integrations.vk.planner_invites.send_vk_message")
    def test_vk_start_message_sends_welcome_keyboard(self, send_vk_message_mock):
        handled = handle_vk_start_message({"from_id": 123456, "text": "Начать"})

        self.assertTrue(handled)
        send_vk_message_mock.assert_called_once()
        self.assertEqual(send_vk_message_mock.call_args.kwargs["user_id"], 123456)
        keyboard = send_vk_message_mock.call_args.kwargs["keyboard"]
        self.assertEqual(keyboard["buttons"][0][0]["action"]["type"], "open_link")
        self.assertEqual(keyboard["buttons"][0][0]["action"]["link"], "https://crm.example.test")

    @override_settings(VK_ENABLED=True, VK_BOT_FRONTEND_URL="https://crm.example.test")
    @patch("integrations.vk.planner_invites.send_vk_message")
    def test_vk_start_payload_sends_welcome_keyboard(self, send_vk_message_mock):
        handled = handle_vk_start_message({"from_id": 123456, "text": "", "payload": '{"command":"start"}'})

        self.assertTrue(handled)
        send_vk_message_mock.assert_called_once()

    @override_settings(VK_ENABLED=True)
    @patch("integrations.vk.planner_invites.send_vk_message")
    def test_vk_bot_status_requires_start_for_duplicate_vk_profile(self, send_vk_message_mock):
        duplicate_user = get_user_model().objects.create_user(
            username="duplicate@example.com",
            email="duplicate@example.com",
            password="password",
            is_active=True,
        )
        duplicate_profile = duplicate_user.crm_profile
        duplicate_profile.vk = "https://vk.com/id123456"
        duplicate_profile.vk_user_id = 123456
        duplicate_profile.vk_confirmed_at = None
        duplicate_profile.save(update_fields=["vk", "vk_user_id", "vk_confirmed_at"])

        api_client = APIClient()
        api_client.force_authenticate(user=duplicate_user)
        response = api_client.get("/api/integrations/vk/bot-status/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["confirmed"])

        handled = handle_vk_start_message({"from_id": 123456, "text": "Начать"})
        self.assertTrue(handled)

        response = api_client.get("/api/integrations/vk/bot-status/")
        self.assertTrue(response.data["confirmed"])
        duplicate_profile.refresh_from_db()
        self.assertIsNotNone(duplicate_profile.vk_confirmed_at)

    @override_settings(VK_BOT_FRONTEND_URL="http://localhost:5173")
    def test_vk_welcome_keyboard_skips_invalid_public_link(self):
        self.assertIsNone(build_welcome_keyboard())

    @override_settings(VK_ENABLED=True, VK_CALLBACK_SECRET="")
    @patch("integrations.vk.planner_invites.send_vk_message")
    def test_vk_planner_invite_accept_callback_updates_application_status(self, send_vk_message_mock):
        self.application.status = self.chat_joined_status
        self.application.save(update_fields=["status"])
        handle_planner_invite_payload(
            from_id=123456,
            payload={"type": "planner_invite", "action": "accept", "application_id": self.application.id},
        )

        self.application.refresh_from_db()
        self.assertEqual(self.application.status.name, "Приступил к ПШ")
        send_vk_message_mock.assert_called_once()

    @override_settings(VK_ENABLED=True, VK_CALLBACK_SECRET="")
    @patch("integrations.vk.planner_invites.send_vk_message")
    def test_vk_planner_invite_decline_asks_confirmation(self, send_vk_message_mock):
        self.application.status = self.chat_joined_status
        self.application.save(update_fields=["status"])
        handle_planner_invite_payload(
            from_id=123456,
            payload={"type": "planner_invite", "action": "decline", "application_id": self.application.id},
        )

        self.application.refresh_from_db()
        self.assertEqual(self.application.status.name, "Добавился в орг. чат")
        send_vk_message_mock.assert_called_once()
        self.assertIn("Вы уверены", send_vk_message_mock.call_args.kwargs["message"])

    @override_settings(VK_ENABLED=True, VK_CALLBACK_SECRET="")
    @patch("integrations.vk.planner_invites.send_vk_message")
    def test_vk_planner_invite_decline_confirm_updates_application_status(self, send_vk_message_mock):
        self.application.status = self.chat_joined_status
        self.application.save(update_fields=["status"])
        handle_planner_invite_payload(
            from_id=123456,
            payload={"type": "planner_invite", "action": "decline_confirm", "application_id": self.application.id},
        )

        self.application.refresh_from_db()
        self.assertEqual(self.application.status.name, "Отказался от ПШ")
        send_vk_message_mock.assert_called_once()
