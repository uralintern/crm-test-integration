"""Характеризационные тесты инфраструктуры авторизации.

Покрывают вход по email (EmailBackend), JWT из cookie (CookieJWTAuthentication),
double-submit CSRF (DoubleSubmitCSRFMiddleware) и декоратор role_required.
Имена cookie и заголовков — часть контракта с фронтом, их менять нельзя.
"""

from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from users.auth_backends import EmailBackend
from users.decorators import role_required
from users.models import CRMRole, Event, ROLE_ADMIN, ROLE_CURATOR

PASSWORD = "StrongPass123"


def create_user(email, **extra):
    return get_user_model().objects.create_user(email=email, username=email, password=PASSWORD, **extra)


class EmailBackendTests(TestCase):
    def setUp(self):
        self.backend = EmailBackend()
        self.user = create_user("Person@Example.test", first_name="Имя", last_name="Фамилия")

    def test_authenticates_by_email_case_insensitive_and_trimmed(self):
        user = self.backend.authenticate(None, username="  person@example.TEST ", password=PASSWORD)

        self.assertEqual(user, self.user)

    def test_wrong_password_returns_none(self):
        self.assertIsNone(self.backend.authenticate(None, username="person@example.test", password="wrong"))

    def test_unknown_email_returns_none(self):
        self.assertIsNone(self.backend.authenticate(None, username="nobody@example.test", password=PASSWORD))

    def test_missing_credentials_return_none(self):
        self.assertIsNone(self.backend.authenticate(None, username=None, password=PASSWORD))
        self.assertIsNone(self.backend.authenticate(None, username="person@example.test", password=None))

    def test_inactive_user_is_rejected(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        self.assertIsNone(self.backend.authenticate(None, username="person@example.test", password=PASSWORD))


class CookieJWTAuthenticationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user("cookie@example.test", first_name="Кука", last_name="Тестова")
        self.url = reverse("user-info")

    def test_valid_access_token_cookie_authenticates(self):
        self.client.cookies["access_token"] = str(AccessToken.for_user(self.user))

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "cookie@example.test")

    def test_invalid_access_token_cookie_is_treated_as_anonymous(self):
        self.client.cookies["access_token"] = "not-a-jwt"

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authorization_header_works_without_cookie(self):
        token = str(AccessToken.for_user(self.user))

        response = self.client.get(self.url, HTTP_AUTHORIZATION=f"Bearer {token}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "cookie@example.test")

    def test_no_credentials_returns_401(self):
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)


class DoubleSubmitCSRFMiddlewareTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user("csrf@example.test")
        self.client.cookies["access_token"] = str(AccessToken.for_user(self.user))
        self.logout_url = reverse("user-logout")

    def test_unsafe_request_with_cookie_auth_and_no_csrf_is_rejected(self):
        response = self.client.post(self.logout_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json(), {"detail": "CSRF validation failed."})

    def test_mismatched_csrf_header_is_rejected(self):
        self.client.cookies["csrftoken"] = "cookie-value"

        response = self.client.post(self.logout_url, HTTP_X_CSRFTOKEN="other-value")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json(), {"detail": "CSRF validation failed."})

    def test_header_without_cookie_is_rejected(self):
        response = self.client.post(self.logout_url, HTTP_X_CSRFTOKEN="value")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_matching_x_csrftoken_header_passes(self):
        self.client.cookies["csrftoken"] = "same-value"

        response = self.client.post(self.logout_url, HTTP_X_CSRFTOKEN="same-value")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_matching_alternative_x_csrf_token_header_passes(self):
        self.client.cookies["csrftoken"] = "same-value"

        response = self.client.post(self.logout_url, HTTP_X_CSRF_TOKEN="same-value")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_safe_methods_are_not_checked(self):
        response = self.client.get(reverse("user-info"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_requests_without_access_cookie_are_not_checked(self):
        client = APIClient()
        client.force_authenticate(user=self.user)

        response = client.post(self.logout_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_login_sets_csrf_cookie_readable_by_frontend(self):
        response = APIClient().post(
            reverse("user-login"), {"email": "csrf@example.test", "password": PASSWORD}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.cookies["csrftoken"].value)
        self.assertFalse(response.cookies["csrftoken"]["httponly"])
        self.assertTrue(response.cookies["access_token"]["httponly"])


class RoleRequiredDecoratorTests(TestCase):
    def setUp(self):
        self.user = create_user("role@example.test")
        self.content_type = ContentType.objects.get_for_model(Event)

    def grant(self, role_type):
        CRMRole.objects.create(user=self.user, role_type=role_type, content_type=self.content_type, object_id=0)

    @staticmethod
    def request_for(user):
        return SimpleNamespace(user=user)

    def test_function_view_with_matching_role_is_called(self):
        self.grant(ROLE_CURATOR)

        @role_required(ROLE_CURATOR, ROLE_ADMIN)
        def view(request):
            return "ok"

        self.assertEqual(view(self.request_for(self.user)), "ok")

    def test_method_view_receives_request_as_second_argument(self):
        self.grant(ROLE_ADMIN)

        class View:
            @role_required(ROLE_ADMIN)
            def get(self, request):
                return "ok"

        self.assertEqual(View().get(self.request_for(self.user)), "ok")

    def test_user_without_role_gets_permission_denied(self):
        @role_required(ROLE_ADMIN)
        def view(request):
            return "ok"

        with self.assertRaises(PermissionDenied):
            view(self.request_for(self.user))

    def test_anonymous_user_gets_not_authenticated(self):
        @role_required(ROLE_ADMIN)
        def view(request):
            return "ok"

        with self.assertRaises(NotAuthenticated):
            view(self.request_for(AnonymousUser()))

    def test_missing_request_raises_permission_denied(self):
        @role_required(ROLE_ADMIN)
        def view(*args):
            return "ok"

        with self.assertRaises(PermissionDenied):
            view()
        with self.assertRaises(PermissionDenied):
            view(object(), object())

    def test_superuser_skips_role_check(self):
        superuser = get_user_model().objects.create_superuser(
            email="super@example.test", username="super@example.test", password=PASSWORD
        )

        @role_required()
        def view(request):
            return "ok"

        self.assertEqual(view(self.request_for(superuser)), "ok")

    def test_empty_role_list_denies_regular_user(self):
        @role_required()
        def view(request):
            return "ok"

        with self.assertRaises(PermissionDenied):
            view(self.request_for(self.user))
