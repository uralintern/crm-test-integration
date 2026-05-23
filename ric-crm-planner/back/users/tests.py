from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.tokens import default_token_generator
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import (
    Answer,
    Application,
    CRMRole,
    Direction,
    Event,
    Profile,
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
from users.decorators import role_required
from users.serializers import (
    EmailConfirmationSerializer,
    LoginUserSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterUserSerializer,
    UserSerializer,
)


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class SerializerTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.password = "StrongPass123"
        self.user = self.user_model.objects.create_user(
            email="user@example.com",
            username="user@example.com",
            password=self.password,
            first_name="John",
            last_name="Doe",
            is_active=True,
        )

    def test_register_user_serializer_creates_active_user(self):
        data = {
            "email": "new@example.com",
            "first_name": "New",
            "last_name": "User",
            "vk": "https://vk.com/id1001",
            "password": self.password,
            "password_confirmation": self.password,
        }

        serializer = RegisterUserSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()

        self.assertTrue(user.is_active)
        self.assertEqual(user.username, data["email"])

    def test_register_user_serializer_checks_password_confirmation(self):
        serializer = RegisterUserSerializer(
            data={
                "email": "mismatch@example.com",
                "first_name": "Test",
                "last_name": "Mismatch",
                "vk": "https://vk.com/id1002",
                "password": "Password1",
                "password_confirmation": "Password2",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("password_confirmation", serializer.errors)

    def test_register_user_serializer_rejects_duplicate_email(self):
        serializer = RegisterUserSerializer(
            data={
                "email": self.user.email,
                "first_name": "Dup",
                "last_name": "User",
                "vk": "https://vk.com/id1003",
                "password": self.password,
                "password_confirmation": self.password,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("email", serializer.errors)

    def test_login_user_serializer_validates_credentials(self):
        serializer = LoginUserSerializer(
            data={"email": self.user.email, "password": self.password}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data, self.user)

    def test_new_user_receives_default_projectant_role(self):
        new_user = self.user_model.objects.create_user(
            email="rolecheck@example.com",
            username="rolecheck@example.com",
            password=self.password,
            first_name="Role",
            last_name="Check",
            is_active=True,
        )

        role = CRMRole.objects.filter(user=new_user, role_type=ROLE_PROJECTANT).first()

        self.assertIsNotNone(role)
        self.assertEqual(role.content_type, ContentType.objects.get_for_model(Profile))
        self.assertEqual(role.object_id, new_user.crm_profile.pk)

    def test_user_serializer_prefers_curator_role_over_default_projectant_role(self):
        CRMRole.objects.create(
            user=self.user,
            role_type=ROLE_CURATOR,
            content_type=ContentType.objects.get_for_model(Profile),
            object_id=self.user.crm_profile.pk,
        )

        data = UserSerializer(self.user).data

        self.assertEqual(data["role"], "organizer")

    def test_email_confirmation_serializer_activates_user(self):
        inactive_user = self.user_model.objects.create_user(
            email="inactive@example.com",
            username="inactive@example.com",
            password=self.password,
            first_name="In",
            last_name="Active",
            is_active=False,
        )
        token = default_token_generator.make_token(inactive_user)
        serializer = EmailConfirmationSerializer(
            data={"email": inactive_user.email, "token": token}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        inactive_user.refresh_from_db()
        self.assertTrue(inactive_user.is_active)

    def test_password_reset_request_serializer_requires_active_user(self):
        inactive_user = self.user_model.objects.create_user(
            email="inactive2@example.com",
            username="inactive2@example.com",
            password=self.password,
            first_name="In",
            last_name="Active",
            is_active=False,
        )

        serializer = PasswordResetRequestSerializer(data={"email": inactive_user.email})
        self.assertFalse(serializer.is_valid())
        self.assertIn("email", serializer.errors)

    def test_password_reset_confirm_serializer_sets_new_password(self):
        token = default_token_generator.make_token(self.user)
        new_password = "AnotherPass123"
        serializer = PasswordResetConfirmSerializer(
            data={
                "email": self.user.email,
                "token": token,
                "new_password": new_password,
                "new_password_confirmation": new_password,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class ViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_model = get_user_model()
        self.password = "StrongPass123"

        self.projectant = self.user_model.objects.create_user(
            email="projectant@example.com",
            username="projectant@example.com",
            password=self.password,
            first_name="Project",
            last_name="Ant",
            is_active=True,
        )
        self.curator = self.user_model.objects.create_user(
            email="curator@example.com",
            username="curator@example.com",
            password=self.password,
            first_name="Cura",
            last_name="Tor",
            is_active=True,
        )
        self.superuser = self.user_model.objects.create_superuser(
            email="admin@example.com",
            username="admin@example.com",
            password=self.password,
            first_name="Admin",
            last_name="User",
        )

        self.event_content_type = ContentType.objects.get_for_model(Event)
        self.role_kwargs = {
            "content_type": self.event_content_type,
            "object_id": 0,
        }

        CRMRole.objects.create(user=self.projectant, role_type=ROLE_PROJECTANT, **self.role_kwargs)
        CRMRole.objects.create(user=self.curator, role_type=ROLE_CURATOR, **self.role_kwargs)

        self.event = Event.objects.create(
            specialization=None,
            name="Demo Event",
            description="Test event",
            stage="draft",
            start_date=timezone.now().date(),
            end_date=timezone.now().date(),
            end_app_date=timezone.now() + timedelta(days=2),
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_login_view_sets_jwt_cookies(self):
        response = self.client.post(
            reverse("user-login"),
            {"email": self.projectant.email, "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.cookies)
        self.assertIn("refresh_token", response.cookies)

    def test_registration_view_returns_400_for_duplicate_email(self):
        response = self.client.post(
            reverse("registration"),
            {
                "email": self.projectant.email,
                "first_name": "Duplicate",
                "last_name": "User",
                "password": self.password,
                "password_confirmation": self.password,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_cookie_token_refresh_issues_new_access_token(self):
        refresh = RefreshToken.for_user(self.projectant)
        self.client.cookies["refresh_token"] = str(refresh)
        response = self.client.post(reverse("token-refresh"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.cookies)

    def test_logout_view_blacklists_refresh_and_clears_cookies(self):
        refresh = RefreshToken.for_user(self.projectant)
        self.client.cookies["refresh_token"] = str(refresh)
        self.authenticate(self.projectant)

        response = self.client.post(reverse("user-logout"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.cookies["access_token"].value, "")
        self.assertEqual(response.cookies["refresh_token"].value, "")

    def test_profile_view_creates_profile_if_missing(self):
        self.authenticate(self.projectant)
        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        profile = Profile.objects.get(user=self.projectant)
        self.assertEqual(profile.email, self.projectant.email)
        self.assertEqual(response.data["email"], self.projectant.email)

    def test_projectant_can_view_events_but_cannot_create(self):
        self.authenticate(self.projectant)
        list_response = self.client.get(reverse("event-list-create"))
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)

        create_response = self.client.post(
            reverse("event-list-create"),
            {
                "name": "New Event",
                "description": "desc",
                "stage": "open",
                "start_date": timezone.now().date(),
                "end_date": timezone.now().date(),
                "end_app_date": timezone.now() + timedelta(days=1),
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_curator_can_create_event(self):
        self.authenticate(self.curator)
        response = self.client.post(
            reverse("event-list-create"),
            {
                "name": "Curated Event",
                "description": "desc",
                "stage": "open",
                "start_date": timezone.now().date(),
                "end_date": timezone.now().date(),
                "end_app_date": timezone.now() + timedelta(days=1),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_superuser_can_manage_events_without_crm_role(self):
        self.authenticate(self.superuser)

        event_response = self.client.post(
            reverse("event-list-create"),
            {
                "name": "Admin Event",
                "description": "desc",
                "stage": "open",
                "start_date": timezone.now().date(),
                "end_date": timezone.now().date(),
                "end_app_date": timezone.now() + timedelta(days=1),
            },
            format="json",
        )
        self.assertEqual(event_response.status_code, status.HTTP_201_CREATED)

        direction_response = self.client.post(
            reverse("direction-list-create", kwargs={"event_id": self.event.id}),
            {"name": "DevOps", "description": "Ops", "leader": self.superuser.id},
            format="json",
        )
        self.assertEqual(direction_response.status_code, status.HTTP_201_CREATED)

    def test_curator_can_create_direction_for_event(self):
        self.authenticate(self.curator)
        response = self.client.post(
            reverse("direction-list-create", kwargs={"event_id": self.event.id}),
            {"name": "Backend", "description": "Python", "leader": self.curator.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        direction = Direction.objects.get(pk=response.data["id"])
        self.assertEqual(direction.event, self.event)

    def test_application_creation_validations(self):
        self.authenticate(self.projectant)
        direction = Direction.objects.create(
            event=self.event,
            name="Data",
            description="ML",
            leader=self.curator,
        )

        create_response = self.client.post(
            reverse(
                "direction-application-create",
                kwargs={"event_id": self.event.id, "direction_id": direction.id},
            ),
            {"message": "First"},
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        duplicate_response = self.client.post(
            reverse(
                "direction-application-create",
                kwargs={"event_id": self.event.id, "direction_id": direction.id},
            ),
            {"message": "Second"},
            format="json",
        )
        self.assertEqual(duplicate_response.status_code, status.HTTP_400_BAD_REQUEST)

        past_event = Event.objects.create(
            specialization=None,
            name="Past Event",
            description="Closed",
            stage="closed",
            start_date=timezone.now().date(),
            end_date=timezone.now().date(),
            end_app_date=timezone.now() - timedelta(days=1),
        )
        past_direction = Direction.objects.create(
            event=past_event,
            name="Frontend",
            description="UI",
            leader=self.curator,
        )

        deadline_response = self.client.post(
            reverse(
                "direction-application-create",
                kwargs={"event_id": past_event.id, "direction_id": past_direction.id},
            ),
            {"message": "Late"},
            format="json",
        )
        self.assertEqual(deadline_response.status_code, status.HTTP_400_BAD_REQUEST)

class RoleDecoratorTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.factory = APIRequestFactory()
        self.password = "StrongPass123"
        self.event_content_type = ContentType.objects.get_for_model(Event)

        self.superuser = self.user_model.objects.create_superuser(
            email="super@example.com",
            username="super@example.com",
            password=self.password,
        )

        self.admin_user = self.user_model.objects.create_user(
            email="admin-role@example.com",
            username="admin-role@example.com",
            password=self.password,
            is_active=True,
        )
        CRMRole.objects.create(
            user=self.admin_user,
            role_type=ROLE_ADMIN,
            content_type=self.event_content_type,
            object_id=0,
        )

        self.regular_user = self.user_model.objects.create_user(
            email="regular@example.com",
            username="regular@example.com",
            password=self.password,
            is_active=True,
        )

        self.decorated_view = role_required(ROLE_ADMIN)(lambda request: "ok")

    def test_superuser_bypasses_role_checks(self):
        request = self.factory.get("/")
        request.user = self.superuser

        self.assertEqual(self.decorated_view(request), "ok")

    def test_user_with_role_passes(self):
        request = self.factory.get("/")
        request.user = self.admin_user

        self.assertEqual(self.decorated_view(request), "ok")

    def test_user_without_role_denied(self):
        request = self.factory.get("/")
        request.user = self.regular_user

        with self.assertRaises(PermissionDenied):
            self.decorated_view(request)

    def test_anonymous_user_rejected(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()

        with self.assertRaises(NotAuthenticated):
            self.decorated_view(request)


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    TESTING_SERVICE_TOKEN="integration-secret",
    TESTING_SERVICE_URL="https://testing.example.test",
)
class IntegrationViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user_model = get_user_model()
        self.password = "StrongPass123"
        self.integration_headers = {"HTTP_X_SERVICE_TOKEN": "integration-secret"}

        self.projectant = self.user_model.objects.create_user(
            email="integration-student@example.com",
            username="integration-student@example.com",
            password=self.password,
            first_name="Integration",
            last_name="Student",
            is_active=True,
        )
        self.curator = self.user_model.objects.create_user(
            email="integration-curator@example.com",
            username="integration-curator@example.com",
            password=self.password,
            first_name="Integration",
            last_name="Curator",
            is_active=True,
        )

        event_content_type = ContentType.objects.get_for_model(Event)
        CRMRole.objects.create(
            user=self.projectant,
            role_type=ROLE_PROJECTANT,
            content_type=event_content_type,
            object_id=0,
        )
        CRMRole.objects.create(
            user=self.curator,
            role_type=ROLE_CURATOR,
            content_type=event_content_type,
            object_id=0,
        )

        self.specialization, _ = Specialization.objects.get_or_create(
            name="Backend разработчик",
            defaults={"description": ""},
        )
        self.submitted_status = Status.objects.create(
            name="Прислал заявку",
            description="",
            is_positive=True,
        )
        self.testing_status = Status.objects.create(
            name="Прохождение тестирования",
            description="",
            is_positive=True,
        )

        self.event = Event.objects.create(
            specialization=self.specialization,
            leader=self.curator,
            name="Integration Event",
            description="CRM integration event",
            stage="open",
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=14),
            end_app_date=timezone.now() + timedelta(days=7),
        )
        self.direction = Direction.objects.create(
            name="Backend",
            description="API integration",
            event=self.event,
            leader=self.curator,
        )
        self.application = Application.objects.create(
            user=self.projectant,
            event=self.event,
            direction=self.direction,
            specialization=self.specialization,
            status=self.submitted_status,
            message="Ready for testing",
            date_sub=timezone.now(),
            date_end=self.event.end_app_date,
        )
        self.test = Test.objects.create(
            name="Backend Basics",
            description="Integration export test",
            entry=1,
            event=self.event,
            specialization=self.specialization,
            passing_score=60,
            time_limit=30,
            is_active=True,
            question_count=1,
            test_type="online",
        )
        self.question = Question.objects.create(
            name="What is HTTP?",
            count=1,
            test=self.test,
            points=100,
            question_type="single",
        )
        Answer.objects.create(
            answer="A protocol",
            count=1,
            question=self.question,
            user=self.projectant,
            is_selected=False,
            answered_at=timezone.now(),
        )
        Answer.objects.create(
            answer="A database",
            count=2,
            question=self.question,
            user=self.projectant,
            is_selected=False,
            answered_at=timezone.now(),
        )
        TrueAnswer.objects.create(
            true_answer="A protocol",
            question=self.question,
            points=100,
        )

    def test_integration_requires_service_token(self):
        response = self.client.get(
            reverse(
                "integration-application-testing-context",
                kwargs={"application_id": self.application.id},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_service_can_fetch_testing_context_and_export_test(self):
        context_response = self.client.get(
            reverse(
                "integration-application-testing-context",
                kwargs={"application_id": self.application.id},
            ),
            **self.integration_headers,
        )

        self.assertEqual(context_response.status_code, status.HTTP_200_OK)
        self.assertEqual(context_response.data["application"]["id"], self.application.id)
        self.assertEqual(context_response.data["applicant"]["email"], self.projectant.email)
        self.assertEqual(len(context_response.data["availableTests"]), 1)
        self.assertEqual(context_response.data["availableTests"][0]["id"], self.test.id)

        export_response = self.client.get(
            reverse("integration-test-export", kwargs={"test_id": self.test.id}),
            **self.integration_headers,
        )

        self.assertEqual(export_response.status_code, status.HTTP_200_OK)
        self.assertEqual(export_response.data["id"], self.test.id)
        self.assertEqual(len(export_response.data["questions"]), 1)
        self.assertEqual(len(export_response.data["questions"][0]["answers"]), 2)
        self.assertEqual(len(export_response.data["questions"][0]["true_answers"]), 1)

    def test_user_can_create_testing_sso_link_and_service_exchanges_ticket_once(self):
        self.client.force_authenticate(user=self.projectant)
        link_response = self.client.post(
            reverse("integration-testing-sso-link"),
            {"application_id": self.application.id},
            format="json",
        )

        self.assertEqual(link_response.status_code, status.HTTP_200_OK, link_response.data)
        self.assertTrue(link_response.data["url"].startswith("https://testing.example.test/sso?"))
        self.assertIn("ticket", link_response.data)

        self.client.force_authenticate(user=None)
        exchange_response = self.client.post(
            reverse("integration-testing-sso-exchange"),
            {"ticket": link_response.data["ticket"]},
            format="json",
            **self.integration_headers,
        )
        second_exchange_response = self.client.post(
            reverse("integration-testing-sso-exchange"),
            {"ticket": link_response.data["ticket"]},
            format="json",
            **self.integration_headers,
        )

        self.assertEqual(exchange_response.status_code, status.HTTP_200_OK, exchange_response.data)
        self.assertEqual(exchange_response.data["user"]["email"], self.projectant.email)
        self.assertEqual(
            exchange_response.data["application"]["application"]["id"],
            self.application.id,
        )
        self.assertEqual(second_exchange_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_testing_sso_exchange_requires_service_token(self):
        self.client.force_authenticate(user=self.projectant)
        link_response = self.client.post(
            reverse("integration-testing-sso-link"),
            {"application_id": self.application.id},
            format="json",
        )
        self.client.force_authenticate(user=None)

        response = self.client.post(
            reverse("integration-testing-sso-exchange"),
            {"ticket": link_response.data["ticket"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_service_can_assign_test_session(self):
        expires_at = timezone.now() + timedelta(hours=2)
        response = self.client.post(
            reverse(
                "integration-application-test-session",
                kwargs={"application_id": self.application.id},
            ),
            {
                "test_id": self.test.id,
                "session_id": "session-123",
                "expires_at": expires_at.isoformat(),
                "status": "assigned",
            },
            format="json",
            **self.integration_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.application.refresh_from_db()
        session = TestSession.objects.get(session_id="session-123")

        self.assertTrue(self.application.tests_assigned)
        self.assertEqual(self.application.test_session_id, "session-123")
        self.assertEqual(self.application.status.name, self.testing_status.name)
        self.assertEqual(session.application_id, self.application.id)
        self.assertEqual(session.test_id, self.test.id)

    def test_service_can_sync_result_idempotently(self):
        session = TestSession.objects.create(
            session_id="session-456",
            application=self.application,
            test=self.test,
            user=self.projectant,
            expires_at=timezone.now() + timedelta(hours=2),
            status="assigned",
        )
        self.application.tests_assigned = True
        self.application.tests_assigned_at = timezone.now()
        self.application.test_session_id = session.session_id
        self.application.status = self.testing_status
        self.application.save(
            update_fields=[
                "tests_assigned",
                "tests_assigned_at",
                "test_session_id",
                "status",
            ]
        )

        payload = {
            "session_id": session.session_id,
            "score": 80,
            "max_score": 100,
            "started_at": timezone.now().isoformat(),
            "completed_at": (timezone.now() + timedelta(minutes=20)).isoformat(),
            "time_spent_seconds": 1200,
            "application_status": self.testing_status.name,
            "detailed_results": {"answers": [{"question_id": self.question.id, "selected": [1]}]},
        }

        first_response = self.client.post(
            reverse(
                "integration-application-test-result",
                kwargs={"application_id": self.application.id},
            ),
            payload,
            format="json",
            **self.integration_headers,
        )
        second_response = self.client.post(
            reverse(
                "integration-application-test-result",
                kwargs={"application_id": self.application.id},
            ),
            payload,
            format="json",
            **self.integration_headers,
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED, first_response.data)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK, second_response.data)
        self.assertEqual(TestResult.objects.count(), 1)

        result = TestResult.objects.get()
        session.refresh_from_db()
        self.application.refresh_from_db()

        self.assertEqual(result.session_id, session.id)
        self.assertTrue(result.is_passed)
        self.assertEqual(result.result_status, "passed")
        self.assertEqual(session.status, "completed")
        self.assertEqual(self.application.status.name, self.testing_status.name)

    def test_service_passed_result_moves_application_to_chat_link_status(self):
        chat_status = Status.objects.create(
            name="Отправлена ссылка на орг. чат",
            description="",
            is_positive=True,
        )
        session = TestSession.objects.create(
            session_id="session-passed",
            application=self.application,
            test=self.test,
            user=self.projectant,
            expires_at=timezone.now() + timedelta(hours=2),
            status="assigned",
        )
        self.application.tests_assigned = True
        self.application.tests_assigned_at = timezone.now()
        self.application.test_session_id = session.session_id
        self.application.status = self.testing_status
        self.application.save(
            update_fields=[
                "tests_assigned",
                "tests_assigned_at",
                "test_session_id",
                "status",
            ]
        )

        response = self.client.post(
            reverse(
                "integration-application-test-result",
                kwargs={"application_id": self.application.id},
            ),
            {
                "session_id": session.session_id,
                "score": 90,
                "max_score": 100,
                "is_passed": True,
                "started_at": timezone.now().isoformat(),
                "completed_at": (timezone.now() + timedelta(minutes=20)).isoformat(),
                "time_spent_seconds": 1200,
            },
            format="json",
            **self.integration_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status.name, chat_status.name)
