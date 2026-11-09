"""Характеризационные тесты API приложения users.

Фиксируют текущее поведение эндпоинтов перед реорганизацией кода
(разбиение users/views.py и users/serializers.py на пакеты).
Поведение, помеченное в doc/REFACTOR_SPEC.md (раздел 4) как дефект,
здесь намеренно не проверяется.
"""

import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.tokens import default_token_generator
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import (
    Answer,
    Application,
    Contact,
    CRMAutomationAttachment,
    CRMAutomationConfig,
    CRMAutomationExecutionLog,
    CRMRole,
    Direction,
    Event,
    EventSpecialization,
    Notification,
    Profile,
    Project,
    Question,
    ROLE_ADMIN,
    ROLE_CURATOR,
    ROLE_PROJECTANT,
    Specialization,
    Status,
    Test,
    TestResult,
    TestSession,
    TrueAnswer,
)
from users.permissions import (
    AdminOnlyPermission,
    CuratorOnlyPermission,
    CuratorOrAdminPermission,
    RolePermission,
    TestingServicePermission,
    has_curator_or_admin_role,
    is_event_organizer,
    resolve_event_id_from_request,
)
from users.serializers import (
    FlexibleStatusField,
    UserSerializer,
    build_user_display_name,
    resolve_status_by_name,
    serialize_default_crm_automation_config,
)

PASSWORD = "StrongPass123"
SERVICE_TOKEN = "service-token-example"
TESTING_URL = "https://testing.example.test"

APPLICATION_CONTRACT_KEYS = {
    "id",
    "message",
    "is_link",
    "is_approved",
    "comment",
    "date_sub",
    "dateSub",
    "createdAt",
    "date_end",
    "user",
    "ownerId",
    "studentName",
    "userName",
    "userEmail",
    "user_email",
    "university",
    "course",
    "vk",
    "direction",
    "directionId",
    "direction_name",
    "event",
    "eventId",
    "eventTitle",
    "eventName",
    "event_name",
    "project",
    "specialization",
    "specializationId",
    "status",
    "statusId",
    "team_id",
    "tests_assigned",
    "tests_assigned_at",
    "test_session_id",
    "hasAvailableTests",
    "custom_fields",
}

# Ключи projectId/projectTitle появляются в ответе только если у заявки есть проект.
APPLICATION_PROJECT_KEYS = {"projectId", "projectTitle"}

USER_CONTRACT_KEYS = {
    "id",
    "email",
    "username",
    "first_name",
    "last_name",
    "role",
    "vk",
    "vkConfirmed",
    "vkBotUrl",
    "managedEventIds",
    "isGlobalOrganizer",
    "isSuperuser",
    "isStaff",
}

EVENT_CONTRACT_KEYS = {
    "id",
    "title",
    "specialization",
    "specializations",
    "leader",
    "organizer",
    "organizerIds",
    "organizerName",
    "name",
    "description",
    "stage",
    "startDate",
    "start_date",
    "endDate",
    "end_date",
    "applyDeadline",
    "end_app_date",
    "is_archived",
    "archived",
    "archived_at",
    "archivedAt",
    "org_chat_url",
    "orgChatUrl",
    "org_chat_peer_id",
    "orgChatPeerId",
    "application_form_fields",
    "applicationFormFields",
}


def get_status(name):
    """Статусы частично засеяны миграциями — берём существующий или создаём."""
    status_obj = Status.objects.filter(name=name).order_by("id").first()
    if status_obj:
        return status_obj
    return Status.objects.create(name=name, description="", is_positive=True)


class APIFixtureMixin:
    """Общие данные: проектант, куратор, организатор мероприятия, мероприятие."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user_model = get_user_model()
        self.event_content_type = ContentType.objects.get_for_model(Event)

        self.projectant = self.create_user("student-api@example.test", "Ivan", "Student")
        self.other_projectant = self.create_user("student-other@example.test", "Petr", "Other")
        self.curator = self.create_user("curator-api@example.test", "Cura", "Tor")
        CRMRole.objects.create(
            user=self.curator,
            role_type=ROLE_CURATOR,
            content_type=self.event_content_type,
            object_id=0,
        )
        # Организатор мероприятия: без роли куратора, только лидер своего мероприятия.
        self.event_organizer = self.create_user("organizer-api@example.test", "Olga", "Organizer")

        self.specialization, _ = Specialization.objects.get_or_create(
            name="Backend разработчик",
            defaults={"description": ""},
        )
        self.event = Event.objects.create(
            name="API Event",
            description="Event for API coverage tests",
            stage="open",
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=30),
            end_app_date=timezone.now() + timedelta(days=7),
            leader=self.event_organizer,
        )
        self.direction = Direction.objects.create(
            name="Backend",
            description="Direction",
            event=self.event,
            leader=self.event_organizer,
        )
        self.project = Project.objects.create(
            name="CRM API",
            description="Project",
            direction=self.direction,
            curator=self.curator,
        )
        self.submitted_status = get_status("Прислал заявку")
        self.testing_status = get_status("Прохождение тестирования")

    def create_user(self, email, first_name="", last_name="", **extra):
        return self.user_model.objects.create_user(
            email=email,
            username=email,
            password=PASSWORD,
            first_name=first_name,
            last_name=last_name,
            is_active=extra.pop("is_active", True),
            **extra,
        )

    def create_application(self, user=None, **kwargs):
        defaults = {
            "user": user or self.projectant,
            "event": self.event,
            "direction": self.direction,
            "specialization": self.specialization,
            "status": self.submitted_status,
            "message": "Хочу участвовать",
            "date_sub": timezone.now(),
            "date_end": self.event.end_app_date,
        }
        defaults.update(kwargs)
        return Application.objects.create(**defaults)

    def create_event(self, **kwargs):
        defaults = {
            "name": "Second Event",
            "description": "",
            "stage": "open",
            "start_date": timezone.now().date(),
            "end_date": timezone.now().date() + timedelta(days=30),
            "end_app_date": timezone.now() + timedelta(days=7),
        }
        defaults.update(kwargs)
        return Event.objects.create(**defaults)

    def create_test(self, **kwargs):
        defaults = {
            "name": "Backend Basics",
            "description": "",
            "entry": 1,
            "event": self.event,
            "specialization": self.specialization,
            "passing_score": 60,
            "time_limit": 30,
            "is_active": True,
            "question_count": 3,
            "test_type": "online",
        }
        defaults.update(kwargs)
        return Test.objects.create(**defaults)

    def auth(self, user):
        self.client.force_authenticate(user=user)


# --------------------------------------------------------------------------
# Auth: вход, выход, обновление токена, сброс пароля, подтверждение email
# --------------------------------------------------------------------------


class AuthAPITests(APIFixtureMixin, TestCase):
    def test_login_returns_user_payload_and_sets_all_auth_cookies(self):
        client = APIClient()
        response = client.post(
            reverse("user-login"),
            {"email": "STUDENT-API@example.test", "password": PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data.keys()), {"user"})
        self.assertEqual(set(response.data["user"].keys()), USER_CONTRACT_KEYS)
        for cookie_name in ("access_token", "refresh_token", "csrftoken"):
            self.assertIn(cookie_name, response.cookies)
        self.assertTrue(response.cookies["access_token"]["httponly"])
        self.assertFalse(response.cookies["csrftoken"]["httponly"])

    def test_login_with_wrong_password_returns_400(self):
        response = APIClient().post(
            reverse("user-login"),
            {"email": self.projectant.email, "password": "wrong-password"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn("access_token", response.cookies)

    def test_login_of_inactive_user_returns_400(self):
        self.projectant.is_active = False
        self.projectant.save(update_fields=["is_active"])

        response = APIClient().post(
            reverse("user-login"),
            {"email": self.projectant.email, "password": PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_refresh_without_cookie_returns_401(self):
        response = self.client.post(reverse("token-refresh"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data, {"error": "Refresh token not provided"})

    def test_refresh_rotates_refresh_cookie_and_sets_csrf(self):
        self.client.cookies["refresh_token"] = str(RefreshToken.for_user(self.projectant))

        response = self.client.post(reverse("token-refresh"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        for cookie_name in ("access_token", "refresh_token", "csrftoken"):
            self.assertIn(cookie_name, response.cookies)

    def test_logout_without_refresh_cookie_clears_cookies(self):
        self.auth(self.projectant)

        response = self.client.post(reverse("user-logout"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)
        self.assertEqual(response.cookies["access_token"].value, "")

    def test_logout_with_broken_refresh_cookie_returns_400(self):
        # Проверяем только код ответа: текст ошибки — дефект S9.
        self.client.cookies["refresh_token"] = "broken"
        self.auth(self.projectant)

        response = self.client.post(reverse("user-logout"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_requires_authentication(self):
        response = self.client.post(reverse("user-logout"))

        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_request_for_active_user_sends_email(self):
        response = self.client.post(
            reverse("password-reset-request"),
            {"email": self.projectant.email},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.projectant.email])

    def test_password_reset_request_with_malformed_email_returns_400(self):
        response = self.client.post(
            reverse("password-reset-request"),
            {"email": "not-an-email"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_password_reset_token_check_requires_email_and_token(self):
        response = self.client.get(reverse("password-reset-confirm"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_reset_token_check_rejects_unknown_email_and_bad_token(self):
        unknown = self.client.get(
            reverse("password-reset-confirm"),
            {"email": "nobody@example.test", "token": "x"},
        )
        bad_token = self.client.get(
            reverse("password-reset-confirm"),
            {"email": self.projectant.email, "token": "bad-token"},
        )

        self.assertEqual(unknown.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(bad_token.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("token", bad_token.data)

    def test_password_reset_token_check_accepts_valid_token(self):
        token = default_token_generator.make_token(self.projectant)

        response = self.client.get(
            reverse("password-reset-confirm"),
            {"email": self.projectant.email, "token": token},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)

    def test_password_reset_confirm_sets_new_password(self):
        token = default_token_generator.make_token(self.projectant)

        response = self.client.post(
            reverse("password-reset-confirm"),
            {
                "email": self.projectant.email,
                "token": token,
                "new_password": "AnotherStrong456",
                "new_password_confirmation": "AnotherStrong456",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.projectant.refresh_from_db()
        self.assertTrue(self.projectant.check_password("AnotherStrong456"))

    def test_password_reset_confirm_validation_errors(self):
        token = default_token_generator.make_token(self.projectant)
        base = {
            "email": self.projectant.email,
            "token": token,
            "new_password": "AnotherStrong456",
            "new_password_confirmation": "AnotherStrong456",
        }
        cases = {
            "email": {**base, "email": "nobody@example.test"},
            "token": {**base, "token": "bad-token"},
            "new_password_confirmation": {**base, "new_password_confirmation": "Mismatch456789"},
        }

        for field, payload in cases.items():
            with self.subTest(field=field):
                response = self.client.post(reverse("password-reset-confirm"), payload, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)

    def test_email_confirmation_activates_inactive_user_via_get_and_post(self):
        for method in ("get", "post"):
            with self.subTest(method=method):
                user = self.create_user(f"inactive-{method}@example.test", is_active=False)
                token = default_token_generator.make_token(user)
                payload = {"email": user.email, "token": token}

                if method == "get":
                    response = self.client.get(reverse("email-confirmation"), payload)
                else:
                    response = self.client.post(reverse("email-confirmation"), payload, format="json")

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                user.refresh_from_db()
                self.assertTrue(user.is_active)

    def test_email_confirmation_validation_errors(self):
        inactive = self.create_user("inactive-errors@example.test", is_active=False)
        cases = {
            "unknown email": ({"email": "nobody@example.test", "token": "x"}, "email"),
            "already active": ({"email": self.projectant.email, "token": "x"}, "email"),
            "bad token": ({"email": inactive.email, "token": "bad-token"}, "token"),
        }

        for name, (payload, field) in cases.items():
            with self.subTest(case=name):
                get_response = self.client.get(reverse("email-confirmation"), payload)
                post_response = self.client.post(reverse("email-confirmation"), payload, format="json")
                self.assertEqual(get_response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(post_response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, post_response.data)


# --------------------------------------------------------------------------
# Users: регистрация, user-info, список пользователей, профиль
# --------------------------------------------------------------------------


class UsersAPITests(APIFixtureMixin, TestCase):
    def test_registration_creates_active_user_with_profile_vk(self):
        response = self.client.post(
            reverse("registration"),
            {
                "email": "New.User@Example.test",
                "vk": "https://vk.com/id12345",
                "first_name": "New",
                "last_name": "User",
                "password": PASSWORD,
                "password_confirmation": PASSWORD,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["email"], "new.user@example.test")
        self.assertNotIn("password", response.data)
        user = self.user_model.objects.get(email="new.user@example.test")
        self.assertTrue(user.is_active)
        self.assertEqual(user.username, user.email)
        self.assertEqual(user.crm_profile.vk, "https://vk.com/id12345")

    def test_registration_rejects_blank_vk(self):
        response = self.client.post(
            reverse("registration"),
            {
                "email": "blank-vk@example.test",
                "vk": "   ",
                "first_name": "New",
                "last_name": "User",
                "password": PASSWORD,
                "password_confirmation": PASSWORD,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("vk", response.data)

    def test_registration_rejects_email_taken_as_username(self):
        self.user_model.objects.create_user(
            username="taken@example.test",
            email="",
            password=PASSWORD,
        )

        response = self.client.post(
            reverse("registration"),
            {
                "email": "taken@example.test",
                "vk": "id1",
                "first_name": "New",
                "last_name": "User",
                "password": PASSWORD,
                "password_confirmation": PASSWORD,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_user_info_requires_authentication(self):
        response = self.client.get(reverse("user-info"))

        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_user_info_role_values_for_each_kind_of_user(self):
        staff = self.create_user("staff-api@example.test", is_staff=True)
        cases = (
            (self.projectant, "student", False, []),
            (self.curator, "organizer", True, []),
            (self.event_organizer, "organizer", False, [self.event.id]),
            (staff, "organizer", True, []),
        )

        for user, role, is_global, managed in cases:
            with self.subTest(user=user.email):
                self.auth(user)
                response = self.client.get(reverse("user-info"))
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(set(response.data.keys()), USER_CONTRACT_KEYS)
                self.assertEqual(response.data["role"], role)
                self.assertEqual(response.data["isGlobalOrganizer"], is_global)
                self.assertEqual(response.data["managedEventIds"], managed)

    def test_user_info_falls_back_to_profile_names(self):
        user = self.create_user("noname@example.test")
        Profile.objects.filter(user=user).update(name="Имя", surname="Фамилия", vk="id77")
        self.auth(self.user_model.objects.get(pk=user.pk))

        response = self.client.get(reverse("user-info"))

        self.assertEqual(response.data["first_name"], "Имя")
        self.assertEqual(response.data["last_name"], "Фамилия")
        self.assertEqual(response.data["vk"], "id77")
        self.assertFalse(response.data["vkConfirmed"])

    def test_curator_gets_user_list_as_array(self):
        self.auth(self.curator)

        response = self.client.get(reverse("user-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(set(response.data[0].keys()), USER_CONTRACT_KEYS)

    def test_profile_get_returns_contract_keys(self):
        self.auth(self.projectant)

        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data.keys()),
            {
                "surname",
                "name",
                "patronymic",
                "telegram",
                "email",
                "course",
                "university",
                "vk",
                "vkConfirmed",
                "vkBotUrl",
                "job",
                "workplace",
                "specialty",
                "about",
            },
        )

    def test_profile_patch_syncs_user_names_and_email(self):
        self.auth(self.projectant)

        response = self.client.patch(
            reverse("profile"),
            {"name": "Новое", "surname": "Имя", "email": "renamed@example.test"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.projectant.refresh_from_db()
        self.assertEqual(self.projectant.first_name, "Новое")
        self.assertEqual(self.projectant.last_name, "Имя")
        self.assertEqual(self.projectant.email, "renamed@example.test")
        self.assertEqual(self.projectant.username, "renamed@example.test")

    def test_profile_vk_change_resets_vk_confirmation(self):
        Profile.objects.filter(user=self.projectant).update(
            vk="id100", vk_user_id=100, vk_confirmed_at=timezone.now()
        )
        self.auth(self.projectant)

        response = self.client.patch(reverse("profile"), {"vk": "https://vk.com/id200"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertFalse(response.data["vkConfirmed"])
        profile = Profile.objects.get(user=self.projectant)
        self.assertIsNone(profile.vk_confirmed_at)
        self.assertEqual(profile.vk_user_id, 200)

    def test_profile_patch_with_same_vk_keeps_confirmation(self):
        Profile.objects.filter(user=self.projectant).update(vk="id100", vk_confirmed_at=timezone.now())
        self.auth(self.projectant)

        response = self.client.patch(reverse("profile"), {"vk": "id100", "about": "Обо мне"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["vkConfirmed"])


# --------------------------------------------------------------------------
# Events: мероприятия, экспорт, справочники
# --------------------------------------------------------------------------


class EventsAPITests(APIFixtureMixin, TestCase):
    def test_event_list_is_array_with_contract_keys(self):
        response = self.client.get(reverse("event-list-create"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(set(response.data[0].keys()), EVENT_CONTRACT_KEYS)

    def test_event_list_separates_archived_events(self):
        archived = self.create_event(name="Old Event", is_archived=True, archived_at=timezone.now())

        active_ids = [item["id"] for item in self.client.get(reverse("event-list-create")).data]
        archived_ids = [
            item["id"] for item in self.client.get(reverse("event-list-create"), {"archived": "true"}).data
        ]

        self.assertIn(self.event.id, active_ids)
        self.assertNotIn(archived.id, active_ids)
        self.assertEqual(archived_ids, [archived.id])

    def test_event_detail_shows_organizer_name_and_legacy_specialization(self):
        event = self.create_event(specialization=self.specialization, leader=self.curator)

        response = self.client.get(reverse("event-detail", kwargs={"event_id": event.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["organizerName"], "Tor Cura")
        self.assertEqual(response.data["organizer"], self.curator.id)
        self.assertEqual([item["id"] for item in response.data["specializations"]], [self.specialization.id])

    def test_event_organizer_names_are_joined(self):
        event = self.create_event(leader=self.curator)
        event.organizers.set([self.event_organizer, self.curator])

        response = self.client.get(reverse("event-detail", kwargs={"event_id": event.id}))

        self.assertEqual(
            sorted(response.data["organizerName"].split(", ")),
            ["Organizer Olga", "Tor Cura"],
        )

    def test_curator_creates_event_with_organizers_leader_defaults_to_first(self):
        self.auth(self.curator)

        response = self.client.post(
            reverse("event-list-create"),
            {
                "name": "Новое мероприятие",
                "description": "",
                "stage": "open",
                "start_date": str(timezone.now().date()),
                "end_date": str(timezone.now().date() + timedelta(days=10)),
                "end_app_date": (timezone.now() + timedelta(days=5)).isoformat(),
                "organizerIds": [self.event_organizer.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        event = Event.objects.get(pk=response.data["id"])
        self.assertEqual(event.leader_id, self.event_organizer.id)
        self.assertEqual(list(event.organizers.values_list("id", flat=True)), [self.event_organizer.id])
        self.assertEqual(response.data["organizerIds"], [self.event_organizer.id])

    def test_curator_updates_event_specializations(self):
        second, _ = Specialization.objects.get_or_create(name="QA инженер", defaults={"description": ""})
        self.auth(self.curator)
        url = reverse("event-detail", kwargs={"event_id": self.event.id})

        set_response = self.client.patch(
            url, {"specializations": [self.specialization.id, second.id]}, format="json"
        )
        self.event.refresh_from_db()
        linked = set(EventSpecialization.objects.filter(event=self.event).values_list("specialization_id", flat=True))
        clear_response = self.client.patch(url, {"specialization": None}, format="json")

        self.assertEqual(set_response.status_code, status.HTTP_200_OK, set_response.data)
        self.assertEqual(linked, {self.specialization.id, second.id})
        self.assertEqual(self.event.specialization_id, self.specialization.id)
        self.assertEqual(clear_response.status_code, status.HTTP_200_OK, clear_response.data)
        self.event.refresh_from_db()
        self.assertIsNone(self.event.specialization_id)
        self.assertFalse(EventSpecialization.objects.filter(event=self.event).exists())

    def test_curator_updates_organizers(self):
        self.auth(self.curator)

        response = self.client.patch(
            reverse("event-detail", kwargs={"event_id": self.event.id}),
            {"organizerIds": [self.curator.id]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(list(self.event.organizers.values_list("id", flat=True)), [self.curator.id])

    def test_event_organizer_can_edit_description_of_own_event(self):
        self.auth(self.event_organizer)

        response = self.client.patch(
            reverse("event-detail", kwargs={"event_id": self.event.id}),
            {"description": "Обновлено организатором"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.event.refresh_from_db()
        self.assertEqual(self.event.description, "Обновлено организатором")

    def test_event_organizer_cannot_change_organizers_or_archive(self):
        self.auth(self.event_organizer)
        url = reverse("event-detail", kwargs={"event_id": self.event.id})

        organizers_response = self.client.patch(url, {"organizerIds": [self.curator.id]}, format="json")
        archive_response = self.client.patch(url, {"archived": True}, format="json")

        self.assertEqual(organizers_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("organizerIds", organizers_response.data)
        self.assertEqual(archive_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("archived", archive_response.data)

    def test_projectant_cannot_edit_foreign_event(self):
        self.auth(self.projectant)

        response = self.client.patch(
            reverse("event-detail", kwargs={"event_id": self.event.id}),
            {"description": "hack"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_curator_delete_archives_event(self):
        self.auth(self.curator)

        response = self.client.delete(reverse("event-detail", kwargs={"event_id": self.event.id}))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.event.refresh_from_db()
        self.assertTrue(self.event.is_archived)
        self.assertIsNotNone(self.event.archived_at)

    def test_event_organizer_cannot_delete_event(self):
        self.auth(self.event_organizer)

        response = self.client.delete(reverse("event-detail", kwargs={"event_id": self.event.id}))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.event.refresh_from_db()
        self.assertFalse(self.event.is_archived)

    def test_exports_are_forbidden_for_projectant(self):
        self.auth(self.projectant)

        for name in ("event-export-details-docx", "event-export-applications-xlsx"):
            with self.subTest(export=name):
                response = self.client.get(reverse(name, kwargs={"event_id": self.event.id}))
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_exports_return_404_for_missing_event(self):
        self.auth(self.curator)

        for name in ("event-export-details-docx", "event-export-applications-xlsx"):
            with self.subTest(export=name):
                response = self.client.get(reverse(name, kwargs={"event_id": 999999}))
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_statuses_and_specializations_are_public_arrays(self):
        statuses = self.client.get(reverse("status-list"))
        specializations = self.client.get(reverse("specialization-list"))

        self.assertEqual(statuses.status_code, status.HTTP_200_OK)
        self.assertIsInstance(statuses.data, list)
        self.assertEqual(set(statuses.data[0].keys()), {"id", "name", "description", "is_positive"})
        self.assertEqual(specializations.status_code, status.HTTP_200_OK)
        self.assertEqual(set(specializations.data[0].keys()), {"id", "name", "title", "description"})


# --------------------------------------------------------------------------
# Directions и Projects
# --------------------------------------------------------------------------


class DirectionsProjectsAPITests(APIFixtureMixin, TestCase):
    def test_direction_detail_crud_for_curator(self):
        self.auth(self.curator)
        url = reverse("direction-detail", kwargs={"event_id": self.event.id, "direction_id": self.direction.id})

        get_response = self.client.get(url)
        patch_response = self.client.patch(url, {"description": "Новое описание"}, format="json")
        delete_response = self.client.delete(url)

        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(get_response.data.keys()),
            {"id", "title", "name", "description", "event", "eventId", "leader", "organizer", "organizerName"},
        )
        self.assertEqual(get_response.data["organizerName"], "Organizer Olga")
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data["description"], "Новое описание")
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Direction.objects.filter(pk=self.direction.id).exists())

    def test_directions_of_archived_event_return_404(self):
        self.event.is_archived = True
        self.event.save(update_fields=["is_archived"])

        list_response = self.client.get(reverse("direction-list-create", kwargs={"event_id": self.event.id}))
        detail_response = self.client.get(
            reverse("direction-detail", kwargs={"event_id": self.event.id, "direction_id": self.direction.id})
        )

        self.assertEqual(list_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_event_organizer_creates_direction_in_own_event(self):
        self.auth(self.event_organizer)

        response = self.client.post(
            reverse("direction-list-create", kwargs={"event_id": self.event.id}),
            {"name": "Frontend", "description": ""},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["eventId"], self.event.id)

    def test_all_directions_list_is_public_array(self):
        response = self.client.get(reverse("user-direction-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data], [self.direction.id])

    def test_projects_in_direction_list_and_create(self):
        url = reverse("project-list-create", kwargs={"event_id": self.event.id, "direction_id": self.direction.id})

        list_response = self.client.get(url)
        self.auth(self.curator)
        create_response = self.client.post(url, {"name": "Новый проект", "description": ""}, format="json")

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(list_response.data[0].keys()),
            {
                "id",
                "title",
                "name",
                "description",
                "direction",
                "directionId",
                "curator",
                "curatorId",
                "curatorName",
                "teams",
                "created_at",
                "updated_at",
            },
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED, create_response.data)
        self.assertEqual(create_response.data["directionId"], self.direction.id)

    def test_projects_of_foreign_direction_return_404(self):
        other_event = self.create_event()

        response = self.client.get(
            reverse("project-list-create", kwargs={"event_id": other_event.id, "direction_id": self.direction.id})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_project_detail_and_update_by_event_organizer(self):
        url = reverse("project-detail", kwargs={"project_id": self.project.id})

        get_response = self.client.get(url)
        self.auth(self.event_organizer)
        patch_response = self.client.patch(url, {"teams": 3}, format="json")

        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        self.assertEqual(get_response.data["curatorName"], "Tor Cura")
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK, patch_response.data)
        self.assertEqual(patch_response.data["teams"], 3)

    def test_project_create_via_flat_endpoint(self):
        self.auth(self.event_organizer)

        response = self.client.post(
            reverse("user-project-list-create"),
            {"name": "Проект через общий список", "direction_id": self.direction.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["directionId"], self.direction.id)

    def test_project_create_without_direction_returns_400(self):
        self.auth(self.curator)

        response = self.client.post(reverse("user-project-list-create"), {"name": "Без направления"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("direction", response.data)

    def test_projectant_cannot_create_project(self):
        self.auth(self.projectant)

        response = self.client.post(
            reverse("user-project-list-create"),
            {"name": "Запрещено", "direction_id": self.direction.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# --------------------------------------------------------------------------
# Applications: заявки
# --------------------------------------------------------------------------


class ApplicationsAPITests(APIFixtureMixin, TestCase):
    def post_application(self, payload):
        self.auth(self.projectant)
        return self.client.post(reverse("application-list"), payload, format="json")

    def test_create_application_returns_contract_and_has_available_tests(self):
        self.create_test()

        response = self.post_application(
            {"event_id": self.event.id, "direction_id": self.direction.id, "message": "Привет"}
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(set(response.data.keys()), APPLICATION_CONTRACT_KEYS)
        self.assertTrue(response.data["hasAvailableTests"])
        self.assertEqual(response.data["status"], "Прислал заявку")
        self.assertEqual(response.data["eventTitle"], self.event.name)
        self.assertEqual(response.data["eventName"], self.event.name)
        self.assertEqual(response.data["event_name"], self.event.name)
        self.assertEqual(response.data["createdAt"], response.data["dateSub"])

    def test_create_application_without_tests_reports_no_available_tests(self):
        response = self.post_application({"event_id": self.event.id})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertFalse(response.data["hasAvailableTests"])

    def test_create_application_with_project_derives_direction(self):
        response = self.post_application({"event_id": self.event.id, "project": self.project.id})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(set(response.data.keys()), APPLICATION_CONTRACT_KEYS | APPLICATION_PROJECT_KEYS)
        self.assertEqual(response.data["directionId"], self.direction.id)
        self.assertEqual(response.data["projectId"], self.project.id)
        self.assertEqual(response.data["projectTitle"], self.project.name)

    def test_create_application_accepts_specialization_by_name(self):
        response = self.post_application(
            {"event_id": self.event.id, "specialization": "backend РАЗРАБОТЧИК"}
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["specializationId"], self.specialization.id)
        self.assertEqual(response.data["specialization"]["id"], self.specialization.id)

    def test_create_application_validation_errors(self):
        other_event = self.create_event()
        other_direction = Direction.objects.create(name="Other", event=other_event)
        other_project = Project.objects.create(name="Other", direction=other_direction)
        second_direction = Direction.objects.create(name="Second", event=self.event)
        expired_event = self.create_event(end_app_date=timezone.now() - timedelta(days=1))
        cases = {
            "direction of other event": (
                {"event_id": self.event.id, "direction_id": other_direction.id},
                "direction",
            ),
            "project without direction from other event": (
                {"event_id": self.event.id, "project": other_project.id},
                "direction",
            ),
            "project of other event": (
                {"event_id": self.event.id, "direction_id": self.direction.id, "project": other_project.id},
                "project",
            ),
            "project of other direction": (
                {"event_id": self.event.id, "direction_id": second_direction.id, "project": self.project.id},
                "project",
            ),
            "project and project_ref mismatch": (
                {"event_id": self.event.id, "project": self.project.id, "project_ref": other_project.id},
                "project",
            ),
            "deadline expired": ({"event_id": expired_event.id}, "event"),
            "unknown specialization": (
                {"event_id": self.event.id, "specialization": "Неизвестная специализация"},
                "specialization",
            ),
        }

        for name, (payload, field) in cases.items():
            with self.subTest(case=name):
                response = self.post_application(payload)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
                self.assertIn(field, response.data)
        self.assertFalse(Application.objects.exists())

    def test_create_application_without_event_returns_400(self):
        response = self.post_application({"message": "Без мероприятия"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("event", response.data)

    def test_second_application_for_same_event_is_rejected(self):
        self.create_application()

        response = self.post_application({"event_id": self.event.id})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("event", response.data)

    def test_curator_cannot_create_application(self):
        CRMRole.objects.filter(user=self.curator, role_type=ROLE_PROJECTANT).delete()
        self.auth(self.curator)

        response = self.client.post(reverse("application-list"), {"event_id": self.event.id}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_application_list_visibility_by_role(self):
        own = self.create_application()
        foreign_event = self.create_event()
        foreign = self.create_application(user=self.other_projectant, event=foreign_event, direction=None)

        def visible_ids(user):
            self.auth(user)
            response = self.client.get(reverse("application-list"))
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIsInstance(response.data, list)
            return {item["id"] for item in response.data}

        self.assertEqual(visible_ids(self.projectant), {own.id})
        self.assertEqual(visible_ids(self.other_projectant), {foreign.id})
        self.assertEqual(visible_ids(self.event_organizer), {own.id})
        self.assertEqual(visible_ids(self.curator), {own.id, foreign.id})

    def test_application_list_filters(self):
        approved = self.create_application(is_approved=True, tests_assigned=True)
        other = self.create_application(
            user=self.other_projectant, direction=None, status=self.testing_status
        )
        self.auth(self.curator)
        url = reverse("application-list")

        def ids(params):
            return {item["id"] for item in self.client.get(url, params).data}

        self.assertEqual(ids({"event": self.event.id}), {approved.id, other.id})
        self.assertEqual(ids({"direction": self.direction.id}), {approved.id})
        self.assertEqual(ids({"status": self.testing_status.id}), {other.id})
        self.assertEqual(ids({"user": self.other_projectant.id}), {other.id})
        self.assertEqual(ids({"specialization": self.specialization.id}), {approved.id, other.id})
        self.assertEqual(ids({"is_approved": "true"}), {approved.id})
        self.assertEqual(ids({"is_approved": "0"}), {other.id})
        self.assertEqual(ids({"tests_assigned": "yes"}), {approved.id})

    def test_application_list_hides_archived_events(self):
        application = self.create_application()
        self.event.is_archived = True
        self.event.save(update_fields=["is_archived"])
        self.auth(self.curator)

        response = self.client.get(reverse("application-list"))

        self.assertNotIn(application.id, [item["id"] for item in response.data])

    def test_application_detail_get_returns_contract_for_owner(self):
        Profile.objects.filter(user=self.projectant).update(university="МГУ", course=3, vk="id5")
        application = self.create_application()
        self.auth(self.projectant)

        response = self.client.get(reverse("application-detail", kwargs={"application_id": application.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data.keys()), APPLICATION_CONTRACT_KEYS)
        self.assertEqual(response.data["ownerId"], self.projectant.id)
        self.assertEqual(response.data["studentName"], "Student Ivan")
        self.assertEqual(response.data["userName"], "Student Ivan")
        self.assertEqual(response.data["userEmail"], self.projectant.email)
        self.assertEqual(response.data["user_email"], self.projectant.email)
        self.assertEqual(response.data["university"], "МГУ")
        self.assertEqual(response.data["course"], 3)
        self.assertEqual(response.data["vk"], "id5")
        self.assertEqual(response.data["direction_name"], self.direction.name)
        self.assertEqual(response.data["status"], "Прислал заявку")
        self.assertEqual(response.data["statusId"], self.submitted_status.id)

    def test_application_detail_of_other_user_is_not_found(self):
        application = self.create_application()
        self.auth(self.other_projectant)

        get_response = self.client.get(reverse("application-detail", kwargs={"application_id": application.id}))
        delete_response = self.client.delete(
            reverse("application-detail", kwargs={"application_id": application.id})
        )

        self.assertEqual(get_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(delete_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Application.objects.filter(pk=application.id).exists())

    def test_owner_moves_application_to_testing_by_name_and_by_id(self):
        # Легитимный сценарий фронта startTestingScenario (см. S1).
        for value in ("Прохождение тестирования", "testing-id"):
            with self.subTest(value=value):
                Application.objects.all().delete()
                application = self.create_application()
                payload_status = self.testing_status.id if value == "testing-id" else value
                self.auth(self.projectant)

                response = self.client.patch(
                    reverse("application-detail", kwargs={"application_id": application.id}),
                    {"status": payload_status},
                    format="json",
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
                self.assertEqual(response.data["status"], "Прохождение тестирования")
                application.refresh_from_db()
                self.assertEqual(application.status_id, self.testing_status.id)

    def test_owner_patch_with_save_request_fields(self):
        application = self.create_application()
        self.auth(self.projectant)

        response = self.client.patch(
            reverse("application-detail", kwargs={"application_id": application.id}),
            {
                "message": "Обновлённое сообщение",
                "is_link": True,
                "comment": "Комментарий",
                "project_ref": self.project.id,
                "specialization": self.specialization.id,
                "custom_fields": {"portfolio": "https://example.test/portfolio"},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        application.refresh_from_db()
        self.assertEqual(application.message, "Обновлённое сообщение")
        self.assertTrue(application.is_link)
        self.assertEqual(application.comment, "Комментарий")
        self.assertEqual(application.project_id, self.project.id)
        self.assertEqual(application.custom_fields, {"portfolio": "https://example.test/portfolio"})

    def test_update_rejects_unknown_status_and_project_mismatch(self):
        application = self.create_application()
        other_project = Project.objects.create(name="Other", direction=self.direction)
        self.auth(self.event_organizer)
        url = reverse("application-detail", kwargs={"application_id": application.id})

        unknown_status = self.client.patch(url, {"status": "Несуществующий статус"}, format="json")
        mismatch = self.client.patch(
            url, {"project": self.project.id, "project_ref": other_project.id}, format="json"
        )

        self.assertEqual(unknown_status.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", unknown_status.data)
        self.assertEqual(mismatch.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("project", mismatch.data)

    def test_status_change_runs_matching_automation_events(self):
        chat_joined = get_status("Добавился в орг. чат")
        enrollment_closed = get_status("Набор завершён")
        cases = (
            (self.testing_status, ["request.status_changed", "testing.started"]),
            (chat_joined, ["request.status_changed", "notification.chat_link_opened"]),
            (enrollment_closed, ["request.status_changed", "enrollment.closed"]),
        )

        for target_status, expected_codes in cases:
            with self.subTest(status=target_status.name):
                Application.objects.all().delete()
                application = self.create_application()
                self.auth(self.event_organizer)
                with patch("users.views.applications.run_crm_automation") as automation_mock:
                    response = self.client.patch(
                        reverse("application-detail", kwargs={"application_id": application.id}),
                        {"status": target_status.id},
                        format="json",
                    )

                self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
                self.assertEqual([call.args[1] for call in automation_mock.call_args_list], expected_codes)
                for call in automation_mock.call_args_list:
                    self.assertEqual(call.kwargs["previous_status"], "Прислал заявку")

    def test_update_without_status_change_does_not_run_automation(self):
        application = self.create_application()
        self.auth(self.event_organizer)

        with patch("users.views.applications.run_crm_automation") as automation_mock:
            response = self.client.patch(
                reverse("application-detail", kwargs={"application_id": application.id}),
                {"comment": "Без смены статуса"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        automation_mock.assert_not_called()

    def test_event_organizer_and_curator_can_delete_application(self):
        for user in (self.event_organizer, self.curator):
            with self.subTest(user=user.email):
                application = self.create_application(user=self.create_user(f"del-{user.id}@example.test"))
                self.auth(user)

                response = self.client.delete(
                    reverse("application-detail", kwargs={"application_id": application.id})
                )

                self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
                self.assertFalse(Application.objects.filter(pk=application.id).exists())

    def test_direction_application_create_returns_application_contract(self):
        self.auth(self.projectant)

        response = self.client.post(
            reverse(
                "direction-application-create",
                kwargs={"event_id": self.event.id, "direction_id": self.direction.id},
            ),
            {"message": "Через направление"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(set(response.data.keys()), APPLICATION_CONTRACT_KEYS)
        self.assertEqual(response.data["directionId"], self.direction.id)


# --------------------------------------------------------------------------
# Notifications: уведомления
# --------------------------------------------------------------------------


class NotificationsAPITests(APIFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.own = Notification.objects.create(user=self.projectant, title="Своё", message="Текст")
        self.foreign = Notification.objects.create(user=self.other_projectant, title="Чужое")
        self.auth(self.projectant)

    def test_list_contains_only_own_notifications_with_contract_keys(self):
        response = self.client.get(reverse("notification-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data], [self.own.id])
        self.assertEqual(
            set(response.data[0].keys()),
            {"id", "userId", "title", "message", "link", "read", "createdAt"},
        )

    def test_create_notification_for_self(self):
        response = self.client.post(
            reverse("notification-list"),
            {"title": "Напоминание", "message": "Сделать задачу", "link": "/planner"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["userId"], self.projectant.id)
        self.assertEqual(response.data["link"], "/planner")

    def test_patch_and_delete_own_notification(self):
        url = reverse("notification-detail", kwargs={"notification_id": self.own.id})

        patch_response = self.client.patch(url, {"read": True}, format="json")
        delete_response = self.client.delete(url)

        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertTrue(patch_response.data["read"])
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Notification.objects.filter(pk=self.own.id).exists())

    def test_foreign_notification_is_not_found(self):
        response = self.client.patch(
            reverse("notification-detail", kwargs={"notification_id": self.foreign.id}),
            {"read": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_mark_all_read_touches_only_own(self):
        response = self.client.post(reverse("notification-mark-all-read"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)
        self.own.refresh_from_db()
        self.foreign.refresh_from_db()
        self.assertTrue(self.own.read)
        self.assertFalse(self.foreign.read)

    def test_clear_deletes_only_own(self):
        response = self.client.delete(reverse("notification-clear"))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Notification.objects.filter(user=self.projectant).exists())
        self.assertTrue(Notification.objects.filter(pk=self.foreign.id).exists())

    def test_notifications_require_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(reverse("notification-list"))

        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))


# --------------------------------------------------------------------------
# Automation: настройки CRM-автоматизации, вложения, логи
# --------------------------------------------------------------------------


class AutomationAPITests(APIFixtureMixin, TestCase):
    CONFIG_KEYS = {"id", "scope", "eventId", "updatedAt", "stages", "triggers", "robots"}

    def test_config_get_creates_default_config(self):
        self.auth(self.curator)

        response = self.client.get(reverse("crm-automation-config", kwargs={"event_id": self.event.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(self.CONFIG_KEYS.issubset(response.data.keys()))
        self.assertEqual(response.data["eventId"], self.event.id)
        self.assertEqual(response.data["scope"], "crm")
        self.assertTrue(response.data["stages"])
        self.assertTrue(CRMAutomationConfig.objects.filter(event=self.event).exists())

    def test_config_get_for_missing_event_returns_404(self):
        self.auth(self.curator)

        response = self.client.get(reverse("crm-automation-config", kwargs={"event_id": 999999}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_config_put_and_patch_save_custom_items_and_keep_defaults(self):
        self.auth(self.event_organizer)
        url = reverse("crm-automation-config", kwargs={"event_id": self.event.id})
        custom_stage = {"id": "custom-stage", "title": "Своя стадия"}

        put_response = self.client.put(
            url, {"stages": [custom_stage], "triggers": [], "robots": []}, format="json"
        )
        patch_response = self.client.patch(
            url, {"robots": [{"id": "custom-robot", "action": "notification.crm"}]}, format="json"
        )

        self.assertEqual(put_response.status_code, status.HTTP_200_OK, put_response.data)
        stage_ids = [stage["id"] for stage in put_response.data["stages"]]
        self.assertEqual(stage_ids[0], "custom-stage")
        self.assertGreater(len(stage_ids), 1)
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK, patch_response.data)
        self.assertIn("custom-robot", [robot["id"] for robot in patch_response.data["robots"]])
        self.assertIn("custom-stage", [stage["id"] for stage in patch_response.data["stages"]])
        self.assertEqual(CRMAutomationConfig.objects.filter(event=self.event).count(), 1)

    def test_config_rejects_foreign_scope(self):
        self.auth(self.curator)

        response = self.client.patch(
            reverse("crm-automation-config", kwargs={"event_id": self.event.id}),
            {"scope": "planner"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("scope", response.data)

    def test_projectant_has_no_access_to_automation(self):
        self.auth(self.projectant)

        responses = [
            self.client.get(reverse("crm-automation-config", kwargs={"event_id": self.event.id})),
            self.client.get(reverse("crm-automation-log-list", kwargs={"event_id": self.event.id})),
            self.client.get(reverse("crm-automation-attachment-list", kwargs={"event_id": self.event.id})),
            self.client.post(reverse("crm-automation-run-pending")),
        ]

        for response in responses:
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_attachment_upload_and_list(self):
        self.auth(self.curator)
        url = reverse("crm-automation-attachment-list", kwargs={"event_id": self.event.id})

        upload = self.client.post(
            url,
            {"file": SimpleUploadedFile("Памятка.PDF", b"%PDF-1.4 test", content_type="application/pdf")},
            format="multipart",
        )
        listing = self.client.get(url)

        self.assertEqual(upload.status_code, status.HTTP_201_CREATED, upload.data)
        self.assertEqual(set(upload.data.keys()), {"id", "name", "size", "contentType", "createdAt"})
        self.assertEqual(upload.data["name"], "Памятка.PDF")
        self.assertEqual(upload.data["contentType"], "application/pdf")
        attachment = CRMAutomationAttachment.objects.get()
        self.assertEqual(attachment.uploaded_by_id, self.curator.id)
        self.assertEqual(bytes(attachment.content), b"%PDF-1.4 test")
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in listing.data], [attachment.id])

    def test_attachment_upload_validation(self):
        self.auth(self.curator)
        url = reverse("crm-automation-attachment-list", kwargs={"event_id": self.event.id})

        no_file = self.client.post(url, {}, format="multipart")
        bad_extension = self.client.post(
            url, {"file": SimpleUploadedFile("script.exe", b"MZ")}, format="multipart"
        )
        no_extension = self.client.post(url, {"file": SimpleUploadedFile("README", b"x")}, format="multipart")
        with patch("users.views.automation.CRM_AUTOMATION_ATTACHMENT_MAX_SIZE", 3):
            too_big = self.client.post(
                url, {"file": SimpleUploadedFile("big.txt", b"12345")}, format="multipart"
            )

        for response in (no_file, bad_extension, no_extension, too_big):
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("file", response.data)
        self.assertFalse(CRMAutomationAttachment.objects.exists())

    def test_attachment_list_for_archived_event_returns_404(self):
        self.event.is_archived = True
        self.event.save(update_fields=["is_archived"])
        self.auth(self.curator)

        response = self.client.get(reverse("crm-automation-attachment-list", kwargs={"event_id": self.event.id}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_execution_log_list_returns_logs_of_event(self):
        config = CRMAutomationConfig.objects.create(event=self.event, stages=[], triggers=[], robots=[])
        application = self.create_application()
        log = CRMAutomationExecutionLog.objects.create(
            config=config,
            application=application,
            event_id=self.event.id,
            entity_id=str(application.id),
            event_code="application.created",
            rule_kind="robot",
            rule_id="robot-1",
            run_key="run-key-api-coverage",
            status=CRMAutomationExecutionLog.STATUS_SUCCESS,
        )
        self.auth(self.curator)

        response = self.client.get(reverse("crm-automation-log-list", kwargs={"event_id": self.event.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data], [log.id])
        self.assertEqual(
            set(response.data[0].keys()),
            {
                "id",
                "eventId",
                "applicationId",
                "entityType",
                "entityId",
                "eventCode",
                "ruleKind",
                "ruleId",
                "runKey",
                "status",
                "message",
                "context",
                "scheduledFor",
                "executedAt",
                "createdAt",
            },
        )
        self.assertEqual(response.data[0]["applicationId"], application.id)

    def test_run_pending_returns_engine_summary(self):
        self.auth(self.curator)

        with patch("users.views.automation.run_due_crm_automation", return_value={"processed": 0}) as run_mock:
            response = self.client.post(reverse("crm-automation-run-pending"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"processed": 0})
        run_mock.assert_called_once_with()

    def test_default_config_helper_matches_engine_defaults(self):
        config = serialize_default_crm_automation_config(self.event.id)

        self.assertTrue({"stages", "triggers", "robots"}.issubset(config.keys()))


# --------------------------------------------------------------------------
# Integration: эндпоинты для Go-сервиса тестирования (контракт раздела 2.2)
# --------------------------------------------------------------------------


@override_settings(TESTING_SERVICE_TOKEN=SERVICE_TOKEN, TESTING_SERVICE_URL=TESTING_URL)
class IntegrationAPITests(APIFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.headers = {"HTTP_X_SERVICE_TOKEN": SERVICE_TOKEN}
        self.application = self.create_application(status=self.testing_status)
        self.test = self.create_test()

    def status_url(self, application=None):
        return reverse(
            "integration-application-status",
            kwargs={"application_id": (application or self.application).id},
        )

    def session_url(self):
        return reverse("integration-application-test-session", kwargs={"application_id": self.application.id})

    def result_url(self):
        return reverse("integration-application-test-result", kwargs={"application_id": self.application.id})

    def context_url(self):
        return reverse(
            "integration-application-testing-context", kwargs={"application_id": self.application.id}
        )

    def create_session(self, session_id="session-int", application=None, test=None):
        return TestSession.objects.create(
            session_id=session_id,
            application=application or self.application,
            test=test or self.test,
            user=(application or self.application).user,
            expires_at=timezone.now() + timedelta(hours=1),
            status="assigned",
        )

    def result_payload(self, session, **overrides):
        started = timezone.now()
        payload = {
            "session_id": session.session_id,
            "score": 30,
            "max_score": 100,
            "started_at": started.isoformat(),
            "completed_at": (started + timedelta(minutes=10)).isoformat(),
        }
        payload.update(overrides)
        return payload

    # --- авторизация сервисным токеном ---

    def test_bearer_token_is_accepted(self):
        response = self.client.get(self.context_url(), HTTP_AUTHORIZATION=f"Bearer {SERVICE_TOKEN}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_wrong_token_is_rejected(self):
        response = self.client.get(self.context_url(), HTTP_X_SERVICE_TOKEN="wrong-token")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(TESTING_SERVICE_TOKEN="")
    def test_empty_server_token_rejects_everyone(self):
        response = self.client.get(self.context_url(), **self.headers)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_application_returns_404(self):
        response = self.client.post(
            reverse("integration-application-status", kwargs={"application_id": 999999}),
            {"application_status": "Не прошел тестирование"},
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- смена статуса (строки захардкожены в Go-сервисе) ---

    def test_status_endpoint_accepts_go_service_russian_names(self):
        for name in ("Не прошел тестирование", "Отправлена ссылка на орг. чат"):
            with self.subTest(status=name):
                get_status(name)
                self.application.status = self.testing_status
                self.application.save(update_fields=["status"])

                with patch("users.views.testing_integration.run_crm_automation") as automation_mock:
                    response = self.client.post(
                        self.status_url(),
                        {"application_status": name, "reason": "test"},
                        format="json",
                        **self.headers,
                    )

                self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
                self.assertEqual(response.data["status"], name)
                self.assertEqual(set(response.data.keys()), APPLICATION_CONTRACT_KEYS)
                self.application.refresh_from_db()
                self.assertEqual(self.application.status.name, name)
                self.assertEqual(
                    [call.args[1] for call in automation_mock.call_args_list], ["request.status_changed"]
                )

    def test_status_endpoint_is_case_insensitive(self):
        get_status("Не прошел тестирование")

        response = self.client.post(
            self.status_url(), {"application_status": "не прошел ТЕСТИРОВАНИЕ"}, format="json", **self.headers
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "Не прошел тестирование")

    def test_status_endpoint_enrollment_closed_runs_extra_trigger(self):
        get_status("Набор завершён")

        with patch("users.views.testing_integration.run_crm_automation") as automation_mock:
            response = self.client.post(
                self.status_url(), {"application_status": "Набор завершён"}, format="json", **self.headers
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [call.args[1] for call in automation_mock.call_args_list],
            ["request.status_changed", "enrollment.closed"],
        )

    def test_status_endpoint_same_status_does_not_run_automation(self):
        with patch("users.views.testing_integration.run_crm_automation") as automation_mock:
            response = self.client.post(
                self.status_url(),
                {"application_status": self.testing_status.name},
                format="json",
                **self.headers,
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        automation_mock.assert_not_called()

    def test_status_endpoint_validation(self):
        empty = self.client.post(self.status_url(), {}, format="json", **self.headers)
        unknown = self.client.post(
            self.status_url(), {"application_status": "Неизвестный статус"}, format="json", **self.headers
        )

        for response in (empty, unknown):
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("application_status", response.data)

    # --- контекст тестирования ---

    def test_testing_context_contract(self):
        session = self.create_session()
        self.application.test_session_id = session.session_id
        self.application.save(update_fields=["test_session_id"])
        result = TestResult.objects.create(
            score=10,
            max_score=100,
            is_passed=False,
            completed_at=timezone.now(),
            started_at=timezone.now(),
            application=self.application,
            session=session,
            test=self.test,
            user=self.projectant,
            correct_answers=1,
            total_questions=3,
            percentage="10.00",
            time_spent_seconds=60,
            result_status="failed",
            detailed_results="не json",
        )

        response = self.client.get(self.context_url(), **self.headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data.keys()),
            {
                "application",
                "applicant",
                "event",
                "direction",
                "specialization",
                "availableTests",
                "currentSession",
                "latestResult",
            },
        )
        self.assertEqual(response.data["applicant"]["display_name"], "Student Ivan")
        self.assertEqual(response.data["event"]["id"], self.event.id)
        self.assertEqual(response.data["direction"]["leader_id"], self.event_organizer.id)
        self.assertEqual(response.data["specialization"]["id"], self.specialization.id)
        self.assertEqual(response.data["currentSession"]["session_id"], session.session_id)
        self.assertEqual(response.data["latestResult"]["id"], result.id)
        self.assertEqual(response.data["latestResult"]["detailedResults"], "не json")
        self.assertEqual(
            set(response.data["availableTests"][0].keys()),
            {
                "id",
                "name",
                "description",
                "entry",
                "eventId",
                "specializationId",
                "passingScore",
                "timeLimit",
                "questionCount",
                "testType",
                "is_active",
            },
        )

    def test_testing_context_without_relations_and_sessions(self):
        bare = self.create_application(
            user=self.other_projectant, event=None, direction=None, specialization=None
        )

        response = self.client.get(
            reverse("integration-application-testing-context", kwargs={"application_id": bare.id}),
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["event"])
        self.assertIsNone(response.data["direction"])
        self.assertIsNone(response.data["specialization"])
        self.assertIsNone(response.data["currentSession"])
        self.assertIsNone(response.data["latestResult"])

    def test_testing_context_uses_latest_result_when_session_has_none(self):
        old_session = self.create_session("old-session")
        current = self.create_session("current-session")
        # Явный порядок: иначе две сессии могут получить одинаковое created_at.
        TestSession.objects.filter(pk=old_session.pk).update(created_at=timezone.now() - timedelta(hours=1))
        self.application.test_session_id = "unknown-session"
        self.application.save(update_fields=["test_session_id"])
        result = TestResult.objects.create(
            score=80,
            max_score=100,
            is_passed=True,
            completed_at=timezone.now(),
            started_at=timezone.now(),
            application=self.application,
            session=old_session,
            test=self.test,
            user=self.projectant,
            correct_answers=3,
            total_questions=3,
            percentage="80.00",
            time_spent_seconds=60,
            result_status="passed",
            detailed_results=json.dumps({"ok": True}),
        )

        response = self.client.get(self.context_url(), **self.headers)

        self.assertEqual(response.data["currentSession"]["session_id"], current.session_id)
        self.assertEqual(response.data["latestResult"]["id"], result.id)
        self.assertEqual(response.data["latestResult"]["detailedResults"], {"ok": True})

    # --- экспорт теста ---

    def test_test_export_contract(self):
        question = Question.objects.create(
            name="Что такое HTTP?", count=1, test=self.test, points=10, question_type="single"
        )
        Answer.objects.create(
            answer="Протокол", count=1, question=question, user=self.projectant, answered_at=timezone.now()
        )
        TrueAnswer.objects.create(true_answer="Протокол", question=question, points=10)

        response = self.client.get(
            reverse("integration-test-export", kwargs={"test_id": self.test.id}), **self.headers
        )
        missing = self.client.get(reverse("integration-test-export", kwargs={"test_id": 999999}), **self.headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        question_data = response.data["questions"][0]
        self.assertEqual(
            set(question_data.keys()),
            {"id", "name", "count", "points", "question_type", "answers", "true_answers"},
        )
        self.assertEqual(set(question_data["answers"][0].keys()), {"id", "answer", "count"})
        self.assertEqual(set(question_data["true_answers"][0].keys()), {"id", "true_answer", "points"})
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)

    # --- сессии тестирования ---

    def test_session_upsert_creates_then_updates_and_stores_answers(self):
        payload = {
            "test_id": self.test.id,
            "session_id": "upsert-session",
            "expires_at": (timezone.now() + timedelta(hours=1)).isoformat(),
            "answers_data": {"q1": ["a"]},
        }

        first = self.client.post(self.session_url(), payload, format="json", **self.headers)
        second = self.client.post(
            self.session_url(), {**payload, "status": "in_progress"}, format="json", **self.headers
        )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.data)
        self.assertEqual(
            set(first.data.keys()),
            {"id", "session_id", "applicationId", "testId", "userId", "createdAt", "expiresAt", "status"},
        )
        self.assertEqual(first.data["status"], "assigned")
        self.assertEqual(second.status_code, status.HTTP_200_OK, second.data)
        self.assertEqual(second.data["status"], "in_progress")
        session = TestSession.objects.get(session_id="upsert-session")
        self.assertEqual(json.loads(session.answers_data), {"q1": ["a"]})

    def test_session_upsert_creates_testing_status_if_missing(self):
        Application.objects.filter(pk=self.application.pk).update(status=self.submitted_status)
        Status.objects.filter(name="Прохождение тестирования").delete()
        self.application.refresh_from_db()

        response = self.client.post(
            self.session_url(),
            {
                "test_id": self.test.id,
                "session_id": "new-status-session",
                "expires_at": (timezone.now() + timedelta(hours=1)).isoformat(),
            },
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status.name, "Прохождение тестирования")

    def test_session_upsert_validation(self):
        other_application = self.create_application(user=self.other_projectant)
        self.create_session("taken-session", application=other_application)
        other_event_test = self.create_test(event=self.create_event())
        other_specialization, _ = Specialization.objects.get_or_create(name="QA инженер", defaults={"description": ""})
        other_spec_test = self.create_test(specialization=other_specialization)
        inactive_test = self.create_test(is_active=False)
        expires = (timezone.now() + timedelta(hours=1)).isoformat()
        cases = {
            "session of other application": (
                {"test_id": self.test.id, "session_id": "taken-session", "expires_at": expires},
                "session_id",
            ),
            "test of other event": (
                {"test_id": other_event_test.id, "session_id": "s1", "expires_at": expires},
                "test_id",
            ),
            "test of other specialization": (
                {"test_id": other_spec_test.id, "session_id": "s2", "expires_at": expires},
                "test_id",
            ),
            "inactive test": ({"test_id": inactive_test.id, "session_id": "s3", "expires_at": expires}, "test_id"),
        }

        for name, (payload, field) in cases.items():
            with self.subTest(case=name):
                response = self.client.post(self.session_url(), payload, format="json", **self.headers)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
                self.assertIn(field, response.data)

    # --- результаты тестирования ---

    def test_result_contract_and_defaults(self):
        session = self.create_session()

        response = self.client.post(
            self.result_url(),
            self.result_payload(session, answers_data={"q1": "b"}),
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(
            set(response.data.keys()),
            {
                "id",
                "applicationId",
                "sessionId",
                "testId",
                "userId",
                "score",
                "max_score",
                "is_passed",
                "startedAt",
                "completedAt",
                "correctAnswers",
                "totalQuestions",
                "percentage",
                "timeSpentSeconds",
                "resultStatus",
                "detailedResults",
            },
        )
        self.assertFalse(response.data["is_passed"])
        self.assertEqual(response.data["resultStatus"], "failed")
        self.assertEqual(response.data["correctAnswers"], 0)
        self.assertEqual(response.data["totalQuestions"], self.test.question_count)
        self.assertEqual(response.data["percentage"], "30.00")
        self.assertIsNone(response.data["detailedResults"])
        session.refresh_from_db()
        self.assertEqual(session.status, "completed")
        self.assertEqual(json.loads(session.answers_data), {"q1": "b"})
        self.application.refresh_from_db()
        self.assertTrue(self.application.tests_assigned)
        self.assertEqual(self.application.test_session_id, session.session_id)

    def test_result_with_zero_max_score_has_zero_percentage(self):
        session = self.create_session()

        response = self.client.post(
            self.result_url(),
            self.result_payload(session, score=0, max_score=0, is_passed=False),
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["percentage"], "0.00")

    def test_failed_final_result_moves_application_to_failed_status(self):
        failed = get_status("Не прошел тестирование")
        session = self.create_session()

        with patch("users.automation_engine.run_crm_automation") as automation_mock:
            response = self.client.post(
                self.result_url(),
                self.result_payload(session, result_status="failed_final"),
                format="json",
                **self.headers,
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status_id, failed.id)
        self.assertEqual(automation_mock.call_args.args[1], "request.status_changed")
        self.assertEqual(automation_mock.call_args.kwargs["previous_status"], "Прохождение тестирования")

    def test_result_accepts_application_status_as_id(self):
        failed = get_status("Не прошел тестирование")
        session = self.create_session()

        response = self.client.post(
            self.result_url(),
            self.result_payload(session, application_status=str(failed.id)),
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status_id, failed.id)

    def test_result_validation(self):
        own_session = self.create_session("own-session")
        other_application = self.create_application(user=self.other_projectant)
        foreign_session = self.create_session("foreign-session", application=other_application)
        other_test = self.create_test(name="Other test")
        started = timezone.now()
        cases = {
            "unknown session": (self.result_payload(own_session, session_id="nope"), "session_id"),
            "session of other application": (self.result_payload(foreign_session), "session_id"),
            "test mismatch": (self.result_payload(own_session, test_id=other_test.id), "test_id"),
            "completed before started": (
                self.result_payload(
                    own_session,
                    started_at=started.isoformat(),
                    completed_at=(started - timedelta(minutes=1)).isoformat(),
                ),
                "completed_at",
            ),
            "unknown application status": (
                self.result_payload(own_session, application_status="Нет такого статуса"),
                "application_status",
            ),
        }

        for name, (payload, field) in cases.items():
            with self.subTest(case=name):
                response = self.client.post(self.result_url(), payload, format="json", **self.headers)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
                self.assertIn(field, response.data)

    # --- SSO ---

    def test_sso_link_requires_configured_testing_url(self):
        self.auth(self.projectant)

        with self.settings(TESTING_SERVICE_URL=""):
            response = self.client.post(reverse("integration-testing-sso-link"), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_sso_link_for_foreign_application_is_forbidden(self):
        self.auth(self.other_projectant)

        response = self.client.post(
            reverse("integration-testing-sso-link"), {"applicationId": self.application.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_sso_link_allowed_for_curator_and_event_organizer(self):
        for user in (self.curator, self.event_organizer):
            with self.subTest(user=user.email):
                self.auth(user)
                response = self.client.post(
                    reverse("integration-testing-sso-link"),
                    {"application_id": self.application.id},
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_sso_link_without_application_passes_next_and_exchange_returns_user(self):
        self.auth(self.curator)
        link = self.client.post(reverse("integration-testing-sso-link"), {"next": "/tests/5"}, format="json")
        self.client.force_authenticate(user=None)

        exchange = self.client.post(
            reverse("integration-testing-sso-exchange"),
            {"ticket": link.data["ticket"]},
            format="json",
            **self.headers,
        )

        self.assertEqual(link.status_code, status.HTTP_200_OK)
        self.assertEqual(set(link.data.keys()), {"url", "ticket", "expiresIn"})
        self.assertTrue(link.data["url"].startswith(f"{TESTING_URL}/sso?"))
        self.assertIn("next=%2Ftests%2F5", link.data["url"])
        self.assertEqual(exchange.status_code, status.HTTP_200_OK, exchange.data)
        self.assertIsNone(exchange.data["application"])
        self.assertEqual(exchange.data["next"], "/tests/5")
        user_payload = exchange.data["user"]
        self.assertEqual(
            set(user_payload.keys()),
            {
                "id",
                "email",
                "first_name",
                "last_name",
                "display_name",
                "role",
                "managed_event_ids",
                "managedEventIds",
                "is_global_organizer",
                "isGlobalOrganizer",
                "vk",
                "vk_confirmed",
                "course",
                "specialty",
                "specializations",
            },
        )
        self.assertEqual(user_payload["role"], "organizer")
        self.assertTrue(user_payload["isGlobalOrganizer"])
        self.assertEqual(user_payload["display_name"], "Tor Cura")

    def test_sso_exchange_rejects_bad_tickets(self):
        missing = self.client.post(reverse("integration-testing-sso-exchange"), {}, format="json", **self.headers)
        forged = self.client.post(
            reverse("integration-testing-sso-exchange"), {"ticket": "forged:ticket"}, format="json", **self.headers
        )

        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(forged.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sso_exchange_rejects_expired_ticket(self):
        self.auth(self.projectant)
        link = self.client.post(reverse("integration-testing-sso-link"), {}, format="json")
        self.client.force_authenticate(user=None)

        with self.settings(TESTING_SSO_TICKET_TTL_SECONDS=-1):
            response = self.client.post(
                reverse("integration-testing-sso-exchange"),
                {"ticket": link.data["ticket"]},
                format="json",
                **self.headers,
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# --------------------------------------------------------------------------
# Permissions и вспомогательные функции
# --------------------------------------------------------------------------


class _FakeView:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class PermissionsUnitTests(APIFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

    def make_request(self, user, method="get", data=None):
        request = getattr(self.factory, method)("/api/users/", data or {}, format="json")
        request.user = user
        # DRF-представление request.data: для юнит-проверки достаточно dict.
        request.data = data or {}
        return request

    def test_has_curator_or_admin_role(self):
        admin_user = self.create_user("admin-role@example.test")
        CRMRole.objects.create(
            user=admin_user, role_type=ROLE_ADMIN, content_type=self.event_content_type, object_id=0
        )
        superuser = self.create_user("super-role@example.test", is_superuser=True)

        self.assertFalse(has_curator_or_admin_role(None))
        self.assertFalse(has_curator_or_admin_role(AnonymousUser()))
        self.assertFalse(has_curator_or_admin_role(self.projectant))
        self.assertTrue(has_curator_or_admin_role(self.curator))
        self.assertTrue(has_curator_or_admin_role(admin_user))
        self.assertTrue(has_curator_or_admin_role(superuser))

    def test_is_event_organizer(self):
        self.event.organizers.add(self.other_projectant)

        self.assertTrue(is_event_organizer(self.event_organizer, self.event.id))
        self.assertTrue(is_event_organizer(self.other_projectant, self.event.id))
        self.assertFalse(is_event_organizer(self.projectant, self.event.id))
        self.assertFalse(is_event_organizer(self.event_organizer, None))
        self.assertFalse(is_event_organizer(AnonymousUser(), self.event.id))

    def test_resolve_event_id_from_kwargs_and_body(self):
        request = self.make_request(self.curator)
        cases = (
            ({"event_id": self.event.id}, {}, self.event.id),
            ({"direction_id": self.direction.id}, {}, self.event.id),
            ({"project_id": self.project.id}, {}, self.event.id),
            ({}, {"event": self.event.id}, self.event.id),
            ({}, {"direction_id": self.direction.id}, self.event.id),
            ({}, {"project": self.project.id}, self.event.id),
            ({}, {}, None),
        )

        for view_kwargs, data, expected in cases:
            with self.subTest(view_kwargs=view_kwargs, data=data):
                request.data = data
                self.assertEqual(resolve_event_id_from_request(request, _FakeView(**view_kwargs)), expected)

    def test_role_permission_classes(self):
        staff = self.create_user("staff-perm@example.test", is_staff=True)
        view = _FakeView()

        self.assertFalse(RolePermission().has_permission(self.make_request(AnonymousUser()), view))
        self.assertTrue(RolePermission().has_permission(self.make_request(staff), view))
        # У базового класса нет разрешённых ролей.
        self.assertFalse(RolePermission().has_permission(self.make_request(self.curator), view))
        self.assertTrue(CuratorOnlyPermission().has_permission(self.make_request(self.curator), view))
        self.assertFalse(AdminOnlyPermission().has_permission(self.make_request(self.curator), view))
        self.assertTrue(
            CuratorOrAdminPermission().has_permission(
                self.make_request(self.event_organizer), _FakeView(event_id=self.event.id)
            )
        )
        self.assertFalse(
            CuratorOrAdminPermission().has_permission(
                self.make_request(self.projectant), _FakeView(event_id=self.event.id)
            )
        )

    @override_settings(TESTING_SERVICE_TOKEN=SERVICE_TOKEN)
    def test_testing_service_permission(self):
        permission = TestingServicePermission()
        view = _FakeView()

        no_token = self.factory.get("/")
        header = self.factory.get("/", HTTP_X_SERVICE_TOKEN=SERVICE_TOKEN)
        bearer = self.factory.get("/", HTTP_AUTHORIZATION=f"Bearer {SERVICE_TOKEN}")
        wrong = self.factory.get("/", HTTP_AUTHORIZATION="Bearer wrong")
        basic = self.factory.get("/", HTTP_AUTHORIZATION=f"Basic {SERVICE_TOKEN}")

        self.assertFalse(permission.has_permission(no_token, view))
        self.assertTrue(permission.has_permission(header, view))
        self.assertTrue(permission.has_permission(bearer, view))
        self.assertFalse(permission.has_permission(wrong, view))
        self.assertFalse(permission.has_permission(basic, view))


class SerializerHelpersUnitTests(APIFixtureMixin, TestCase):
    def test_build_user_display_name(self):
        nameless = self.create_user("nameless@example.test")
        Profile.objects.filter(user=nameless).update(name="", surname="")
        nameless.refresh_from_db()

        self.assertEqual(build_user_display_name(None), "")
        self.assertEqual(build_user_display_name(self.projectant), "Student Ivan")
        self.assertEqual(build_user_display_name(nameless), "nameless@example.test")

    def test_resolve_status_by_name_reuses_or_creates(self):
        existing = resolve_status_by_name("Прислал заявку")
        created = resolve_status_by_name("Совсем новый статус", description="desc", is_positive=False)

        self.assertEqual(existing.id, self.submitted_status.id)
        self.assertEqual(created.name, "Совсем новый статус")
        self.assertFalse(created.is_positive)

    def test_flexible_status_field(self):
        field = FlexibleStatusField(queryset=Status.objects.all(), allow_null=True)

        self.assertIsNone(field.to_internal_value(None))
        self.assertIsNone(field.to_internal_value("   "))
        self.assertEqual(field.to_internal_value("прислал заявку").id, self.submitted_status.id)
        self.assertEqual(field.to_internal_value(str(self.submitted_status.id)).id, self.submitted_status.id)

    def test_user_serializer_managed_events_for_anonymous(self):
        self.assertEqual(UserSerializer().get_managedEventIds(AnonymousUser()), [])


class ModelStrTests(APIFixtureMixin, TestCase):
    def test_model_string_representations(self):
        application = self.create_application()
        profile = Profile.objects.get(user=self.projectant)
        contact = Contact.objects.create(type="vk", data="id1", profile=profile)
        role = CRMRole.objects.filter(user=self.curator, role_type=ROLE_CURATOR).first()
        event_spec = EventSpecialization.objects.create(event=self.event, specialization=self.specialization)
        notification = Notification.objects.create(user=self.projectant, title="T")
        config = CRMAutomationConfig.objects.create(event=self.event)
        log = CRMAutomationExecutionLog.objects.create(
            config=config,
            event_id=self.event.id,
            entity_id="1",
            event_code="x",
            rule_kind="robot",
            rule_id="r1",
            run_key="str-run-key",
        )
        test = self.create_test(name="Тест")
        session = TestSession.objects.create(
            session_id="s-str",
            application=application,
            test=test,
            user=self.projectant,
            expires_at=timezone.now(),
            status="assigned",
        )
        result = TestResult.objects.create(
            score=5,
            max_score=10,
            completed_at=timezone.now(),
            started_at=timezone.now(),
            application=application,
            test=test,
            user=self.projectant,
            correct_answers=1,
            total_questions=2,
            percentage="50.00",
            time_spent_seconds=1,
            result_status="failed",
        )
        question = Question.objects.create(name="Вопрос", count=1, test=test, points=1, question_type="single")
        true_answer = TrueAnswer.objects.create(true_answer="Да", question=question, points=1)
        answer = Answer.objects.create(
            answer="Да", count=1, question=question, user=self.projectant, answered_at=timezone.now()
        )
        attachment = CRMAutomationAttachment.objects.create(event=self.event, file_name="a.txt", content=b"x")

        self.assertEqual(str(profile), f"Student Ivan ({self.projectant.username})")
        self.assertEqual(str(contact), f"{profile} — vk: id1")
        self.assertIn("curator", str(role))
        self.assertEqual(str(self.submitted_status), "Прислал заявку")
        self.assertEqual(str(self.specialization), self.specialization.name)
        self.assertEqual(str(self.event), "API Event")
        self.assertEqual(str(self.direction), "Backend (API Event)")
        self.assertEqual(str(self.project), "CRM API")
        self.assertEqual(str(event_spec), f"API Event — {self.specialization.name}")
        self.assertEqual(str(application), f"Заявка #{application.id} — {self.projectant}")
        self.assertEqual(str(notification), f"Уведомление #{notification.id} для {self.projectant}")
        self.assertEqual(str(config), f"crm:{self.event.id}")
        self.assertEqual(str(log), "robot:r1:pending")
        self.assertEqual(str(test), "Тест")
        self.assertEqual(str(session), f"Сессия s-str — {self.projectant}")
        self.assertEqual(str(result), f"Результат {self.projectant} — Тест: 5/10")
        self.assertEqual(str(question), "Вопрос 1: Вопрос...")
        self.assertEqual(str(true_answer), "Правильный ответ: Да")
        self.assertEqual(str(answer), f"Ответ {self.projectant} на '{question}': Да")
        self.assertEqual(str(attachment), "a.txt")
