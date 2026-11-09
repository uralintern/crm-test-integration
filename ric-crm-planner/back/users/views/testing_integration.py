"""Интеграция с сервисом тестирования: SSO, сессии, результаты, статус заявки."""

from django.conf import settings
import secrets
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db.models import Q
from django.shortcuts import get_object_or_404
from urllib.parse import urlencode
from rest_framework import status
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from users.permissions import TestingServicePermission
from users.serializers import (
    ApplicationSerializer,
    IntegrationApplicationTestingContextSerializer,
    IntegrationTestExportSerializer,
    IntegrationTestResultCallbackSerializer,
    IntegrationTestResultSerializer,
    IntegrationTestSessionSerializer,
    IntegrationTestSessionUpsertSerializer,
    UserSerializer,
    SpecializationSerializer,
)
from users.models import Application, Specialization, Status, Test, TestSession
from users.automation_engine import run_crm_automation
from .schema import ERROR_RESPONSE_SCHEMA, INTEGRATION_TOKEN_PARAMETER, TAG_INTEGRATION
from .access import _user_can_access_application


TESTING_SSO_SIGNER_SALT = "testing-service-sso"
TESTING_SSO_CACHE_PREFIX = "testing_sso_ticket"


def _get_available_tests_for_application(application: Application):
    queryset = Test.objects.filter(is_active=True)

    if application.event_id:
        queryset = queryset.filter(
            Q(event__isnull=True) | Q(event_id=application.event_id)
        )

    if application.specialization_id:
        queryset = queryset.filter(
            Q(specialization__isnull=True)
            | Q(specialization_id=application.specialization_id)
        )

    return queryset.select_related("event", "specialization").order_by("entry", "name")


def _get_application_current_session(application: Application):
    session_queryset = application.test_sessions.select_related("test", "user").order_by(
        "-created_at"
    )
    if application.test_session_id:
        current_session = session_queryset.filter(
            session_id=application.test_session_id
        ).first()
        if current_session:
            return current_session
    return session_queryset.first()


def _get_application_latest_result(
    application: Application, current_session: TestSession | None
):
    if current_session and hasattr(current_session, "result"):
        return current_session.result

    return application.test_results.select_related("test", "user", "session").order_by(
        "-completed_at",
        "-id",
    ).first()


def _get_testing_sso_signer():
    return TimestampSigner(salt=TESTING_SSO_SIGNER_SALT)


def _get_testing_sso_cache_key(nonce: str) -> str:
    return f"{TESTING_SSO_CACHE_PREFIX}:{nonce}"


def _build_testing_sso_user_payload(user):
    profile = getattr(user, "crm_profile", None)
    first_name = getattr(user, "first_name", "") or getattr(profile, "name", "")
    last_name = getattr(user, "last_name", "") or getattr(profile, "surname", "")
    display_name = " ".join(part for part in (last_name, first_name) if part).strip()
    user_specializations = Specialization.objects.filter(
        applications__user=user,
    ).distinct().order_by("name")

    user_serializer = UserSerializer()
    managed_event_ids = user_serializer.get_managedEventIds(user)
    is_global_organizer = user_serializer.get_isGlobalOrganizer(user)

    return {
        "id": user.id,
        "email": user.email,
        "first_name": first_name,
        "last_name": last_name,
        "display_name": display_name or user.email,
        "role": user_serializer.get_role(user),
        "managed_event_ids": managed_event_ids,
        "managedEventIds": managed_event_ids,
        "is_global_organizer": is_global_organizer,
        "isGlobalOrganizer": is_global_organizer,
        "vk": getattr(profile, "vk", ""),
        "vk_confirmed": bool(getattr(profile, "vk_confirmed_at", None)),
        "course": getattr(profile, "course", None),
        "specialty": getattr(profile, "specialty", ""),
        "specializations": SpecializationSerializer(user_specializations, many=True).data,
    }


def _build_testing_application_context(application: Application, request):
    available_tests = list(_get_available_tests_for_application(application))
    current_session = _get_application_current_session(application)
    latest_result = _get_application_latest_result(application, current_session)
    return IntegrationApplicationTestingContextSerializer(
        application,
        context={
            "request": request,
            "available_tests": available_tests,
            "current_session": current_session,
            "latest_result": latest_result,
        },
    ).data


class IntegrationApplicationMixin:
    authentication_classes = ()
    permission_classes = (TestingServicePermission,)

    def get_application(self):
        return get_object_or_404(
            Application.objects.select_related(
                "user",
                "event",
                "direction",
                "project",
                "specialization",
                "status",
            ),
            pk=self.kwargs.get("application_id"),
        )


class IntegrationApplicationTestingContextView(IntegrationApplicationMixin, APIView):
    @swagger_auto_schema(
        tags=[TAG_INTEGRATION],
        operation_summary="Get testing context for application",
        operation_description="Returns CRM context required by the testing backend.",
        manual_parameters=[INTEGRATION_TOKEN_PARAMETER],
        responses={
            200: IntegrationApplicationTestingContextSerializer,
            403: ERROR_RESPONSE_SCHEMA,
            404: ERROR_RESPONSE_SCHEMA,
        },
    )
    def get(self, request, *args, **kwargs):
        application = self.get_application()
        available_tests = list(_get_available_tests_for_application(application))
        current_session = _get_application_current_session(application)
        latest_result = _get_application_latest_result(application, current_session)
        serializer = IntegrationApplicationTestingContextSerializer(
            application,
            context={
                "request": request,
                "available_tests": available_tests,
                "current_session": current_session,
                "latest_result": latest_result,
            },
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class TestingSSOLinkView(APIView):
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(
        tags=[TAG_INTEGRATION],
        operation_summary="Create testing service SSO link",
        operation_description="Creates one-time SSO ticket and returns URL for opening the testing module.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "application_id": openapi.Schema(type=openapi.TYPE_INTEGER),
                "applicationId": openapi.Schema(type=openapi.TYPE_INTEGER),
                "next": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        responses={200: openapi.Schema(type=openapi.TYPE_OBJECT), 400: ERROR_RESPONSE_SCHEMA, 503: ERROR_RESPONSE_SCHEMA},
    )
    def post(self, request, *args, **kwargs):
        testing_service_url = (getattr(settings, "TESTING_SERVICE_URL", "") or "").strip().rstrip("/")
        if not testing_service_url:
            return Response(
                {"detail": "Testing service URL is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        application_id = request.data.get("application_id") or request.data.get("applicationId")
        application = None
        if application_id:
            application = get_object_or_404(
                Application.objects.select_related(
                    "user",
                    "event",
                    "direction",
                    "project",
                    "specialization",
                    "status",
                ),
                pk=application_id,
            )
            if not _user_can_access_application(request.user, application):
                return Response(status=status.HTTP_403_FORBIDDEN)

        nonce = secrets.token_urlsafe(32)
        ttl = getattr(settings, "TESTING_SSO_TICKET_TTL_SECONDS", 300)
        payload = {
            "user_id": request.user.id,
            "application_id": application.id if application else None,
            "next": request.data.get("next") or "",
        }
        cache.set(_get_testing_sso_cache_key(nonce), payload, ttl)

        ticket = _get_testing_sso_signer().sign(nonce)
        query = {"ticket": ticket}
        if payload["next"]:
            query["next"] = payload["next"]

        return Response(
            {
                "url": f"{testing_service_url}/sso?{urlencode(query)}",
                "ticket": ticket,
                "expiresIn": ttl,
            },
            status=status.HTTP_200_OK,
        )


class TestingSSOExchangeView(APIView):
    authentication_classes = ()
    permission_classes = (TestingServicePermission,)

    @swagger_auto_schema(
        tags=[TAG_INTEGRATION],
        operation_summary="Exchange testing service SSO ticket",
        operation_description="Exchanges one-time SSO ticket for CRM user and application context.",
        manual_parameters=[INTEGRATION_TOKEN_PARAMETER],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["ticket"],
            properties={"ticket": openapi.Schema(type=openapi.TYPE_STRING)},
        ),
        responses={200: openapi.Schema(type=openapi.TYPE_OBJECT), 400: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA},
    )
    def post(self, request, *args, **kwargs):
        ticket = str(request.data.get("ticket") or "").strip()
        if not ticket:
            return Response({"detail": "Ticket is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            nonce = _get_testing_sso_signer().unsign(
                ticket,
                max_age=getattr(settings, "TESTING_SSO_TICKET_TTL_SECONDS", 300),
            )
        except SignatureExpired:
            return Response({"detail": "SSO ticket expired."}, status=status.HTTP_400_BAD_REQUEST)
        except BadSignature:
            return Response({"detail": "Invalid SSO ticket."}, status=status.HTTP_400_BAD_REQUEST)

        cache_key = _get_testing_sso_cache_key(nonce)
        payload = cache.get(cache_key)
        if not payload:
            return Response({"detail": "SSO ticket expired or already used."}, status=status.HTTP_400_BAD_REQUEST)
        cache.delete(cache_key)

        user = get_object_or_404(get_user_model().objects.select_related("crm_profile"), pk=payload.get("user_id"))
        application = None
        application_id = payload.get("application_id")
        if application_id:
            application = get_object_or_404(
                Application.objects.select_related(
                    "user",
                    "event",
                    "direction",
                    "project",
                    "specialization",
                    "status",
                ),
                pk=application_id,
            )

        return Response(
            {
                "user": _build_testing_sso_user_payload(user),
                "application": _build_testing_application_context(application, request) if application else None,
                "next": payload.get("next") or "",
            },
            status=status.HTTP_200_OK,
        )


class IntegrationTestExportView(APIView):
    authentication_classes = ()
    permission_classes = (TestingServicePermission,)

    @swagger_auto_schema(
        tags=[TAG_INTEGRATION],
        operation_summary="Export test definition",
        operation_description="Returns full test structure, questions and answers for the testing backend.",
        manual_parameters=[INTEGRATION_TOKEN_PARAMETER],
        responses={
            200: IntegrationTestExportSerializer,
            403: ERROR_RESPONSE_SCHEMA,
            404: ERROR_RESPONSE_SCHEMA,
        },
    )
    def get(self, request, *args, **kwargs):
        test = get_object_or_404(
            Test.objects.select_related("event", "specialization").prefetch_related(
                "questions__answers",
                "questions__true_answers",
            ),
            pk=self.kwargs.get("test_id"),
        )
        serializer = IntegrationTestExportSerializer(test)
        return Response(serializer.data, status=status.HTTP_200_OK)


class IntegrationApplicationTestSessionView(IntegrationApplicationMixin, APIView):
    @swagger_auto_schema(
        tags=[TAG_INTEGRATION],
        operation_summary="Assign or sync test session",
        operation_description="Creates or updates a test session for the given application.",
        manual_parameters=[INTEGRATION_TOKEN_PARAMETER],
        request_body=IntegrationTestSessionUpsertSerializer,
        responses={
            200: IntegrationTestSessionSerializer,
            201: IntegrationTestSessionSerializer,
            400: ERROR_RESPONSE_SCHEMA,
            403: ERROR_RESPONSE_SCHEMA,
            404: ERROR_RESPONSE_SCHEMA,
        },
    )
    def post(self, request, *args, **kwargs):
        application = self.get_application()
        serializer = IntegrationTestSessionUpsertSerializer(
            data=request.data,
            context={"request": request, "application": application},
        )
        serializer.is_valid(raise_exception=True)
        session = serializer.save()
        response_serializer = IntegrationTestSessionSerializer(session)
        created = bool(serializer.context.get("created"))
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class IntegrationApplicationTestResultView(IntegrationApplicationMixin, APIView):
    @swagger_auto_schema(
        tags=[TAG_INTEGRATION],
        operation_summary="Submit test result callback",
        operation_description="Accepts final test result from the testing backend and syncs it into CRM.",
        manual_parameters=[INTEGRATION_TOKEN_PARAMETER],
        request_body=IntegrationTestResultCallbackSerializer,
        responses={
            200: IntegrationTestResultSerializer,
            201: IntegrationTestResultSerializer,
            400: ERROR_RESPONSE_SCHEMA,
            403: ERROR_RESPONSE_SCHEMA,
            404: ERROR_RESPONSE_SCHEMA,
        },
    )
    def post(self, request, *args, **kwargs):
        application = self.get_application()
        serializer = IntegrationTestResultCallbackSerializer(
            data=request.data,
            context={"request": request, "application": application},
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        response_serializer = IntegrationTestResultSerializer(result)
        created = bool(serializer.context.get("created"))
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class IntegrationApplicationStatusView(IntegrationApplicationMixin, APIView):
    @swagger_auto_schema(
        tags=[TAG_INTEGRATION],
        operation_summary="Update application status from testing service",
        operation_description="Updates CRM application status when the testing module does not have a CRM test session.",
        manual_parameters=[INTEGRATION_TOKEN_PARAMETER],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["application_status"],
            properties={
                "application_status": openapi.Schema(type=openapi.TYPE_STRING),
                "reason": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        responses={200: ApplicationSerializer, 400: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    )
    def post(self, request, *args, **kwargs):
        application = self.get_application()
        status_name = str(request.data.get("application_status") or "").strip()
        if not status_name:
            return Response({"application_status": "Application status is required."}, status=status.HTTP_400_BAD_REQUEST)

        status_obj = Status.objects.filter(name__iexact=status_name).first()
        if not status_obj:
            return Response({"application_status": "Application status was not found."}, status=status.HTTP_400_BAD_REQUEST)

        previous_status = application.status.name if application.status_id else ""
        if previous_status != status_obj.name:
            application.status = status_obj
            application.save(update_fields=["status"])
            application.refresh_from_db()
            run_crm_automation(
                application,
                "request.status_changed",
                previous_status=previous_status,
                request=request,
            )
            if status_obj.name == "Набор завершён":
                run_crm_automation(
                    application,
                    "enrollment.closed",
                    previous_status=previous_status,
                    request=request,
                )

        return Response(ApplicationSerializer(application, context={"request": request}).data, status=status.HTTP_200_OK)
