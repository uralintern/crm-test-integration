from django.conf import settings
import secrets
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from urllib.parse import urlencode
from rest_framework import status
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.generics import (
    CreateAPIView,
    ListAPIView,
    ListCreateAPIView,
    RetrieveAPIView,
    RetrieveUpdateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.mixins import CreateModelMixin
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from users.permissions import (
    CuratorOrAdminPermission,
    PublicReadCuratorAdminWritePermission,
    ProjectantOnlyPermission,
    TestingServicePermission,
    has_curator_or_admin_role,
    is_event_organizer,
)
from users.serializers import (
    ApplicationCreateSerializer,
    ApplicationSerializer,
    CRMAutomationConfigPayloadSerializer,
    CRMAutomationConfigSerializer,
    CRMAutomationExecutionLogSerializer,
    DirectionSerializer,
    EmailConfirmationSerializer,
    EventSerializer,
    IntegrationApplicationTestingContextSerializer,
    IntegrationTestExportSerializer,
    IntegrationTestResultCallbackSerializer,
    IntegrationTestResultSerializer,
    IntegrationTestSessionSerializer,
    IntegrationTestSessionUpsertSerializer,
    LoginUserSerializer,
    NotificationCreateSerializer,
    NotificationSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileSerializer,
    ProjectSerializer,
    RegisterUserSerializer,
    UserSerializer,
    SpecializationSerializer,
    StatusSerializer,
)
from users.models import (
    Application,
    Answer,
    CRMAutomationConfig,
    CRMAutomationExecutionLog,
    Direction,
    Event,
    Notification,
    Profile,
    Project,
    Question,
    Specialization,
    Status,
    Test,
    TestResult,
    TestSession,
    TrueAnswer,
)
from users.automation_defaults import create_default_crm_automation_config
from users.automation_engine import normalize_crm_automation_config_dict, run_crm_automation, run_due_crm_automation

TAG_AUTH = "Auth"
TAG_USERS = "Users"
TAG_PROFILE = "Profile"
TAG_EVENTS = "Events"
TAG_DIRECTIONS = "Directions"
TAG_PROJECTS = "Projects"
TAG_APPLICATIONS = "Applications"
TAG_NOTIFICATIONS = "Уведомления"
TAG_REFERENCE = "Reference"
TAG_INTEGRATION = "Integration"

MESSAGE_RESPONSE_SCHEMA = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={"message": openapi.Schema(type=openapi.TYPE_STRING)},
)

ERROR_RESPONSE_SCHEMA = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    additional_properties=openapi.Schema(type=openapi.TYPE_STRING),
)

LOGIN_RESPONSE_SCHEMA = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={"user": openapi.Schema(type=openapi.TYPE_OBJECT)},
)

REFRESH_RESPONSE_SCHEMA = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "access": openapi.Schema(type=openapi.TYPE_STRING),
        "refresh": openapi.Schema(type=openapi.TYPE_STRING),
    },
)

INTEGRATION_TOKEN_PARAMETER = openapi.Parameter(
    "X-Service-Token",
    openapi.IN_HEADER,
    description="Shared token for CRM and testing service integration.",
    type=openapi.TYPE_STRING,
    required=True,
)

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

    return {
        "id": user.id,
        "email": user.email,
        "first_name": first_name,
        "last_name": last_name,
        "display_name": display_name or user.email,
        "role": UserSerializer().get_role(user),
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


def _user_can_access_application(user, application: Application) -> bool:
    if application.user_id == user.id:
        return True
    if has_curator_or_admin_role(user):
        return True
    return is_event_organizer(user, application.event_id)


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_USERS],
        operation_summary="Get current user info",
        operation_description="Get current user info",
        responses={200: UserSerializer, 401: ERROR_RESPONSE_SCHEMA},
    ),
)
class UserInfoView(RetrieveAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        tags=[TAG_AUTH],
        operation_summary="Register user",
        operation_description="Register user",
        request_body=RegisterUserSerializer,
        responses={201: UserSerializer, 400: ERROR_RESPONSE_SCHEMA},
    ),
)
class UserRegistrationView(CreateAPIView):
    permission_classes = (AllowAny,)
    serializer_class = RegisterUserSerializer

@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_USERS],
        operation_summary="List users",
        operation_description="List users",
        responses={200: UserSerializer(many=True), 401: ERROR_RESPONSE_SCHEMA},
    ),
)
class UserListView(ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = UserSerializer
    queryset = get_user_model().objects.all()

def _set_auth_cookies(response, access_token: str, refresh_token: RefreshToken | None = None):
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )

    if refresh_token is not None:
        response.set_cookie(
            key="refresh_token",
            value=str(refresh_token),
            httponly=True,
            secure=settings.SESSION_COOKIE_SECURE,
            samesite=settings.SESSION_COOKIE_SAMESITE,
        )


def _set_csrf_cookie(response):
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        key="csrftoken",
        value=csrf_token,
        httponly=False,
        secure=settings.CSRF_COOKIE_SECURE,
        samesite=settings.CSRF_COOKIE_SAMESITE,
    )
    return csrf_token

class LoginView(APIView):
    permission_classes = (AllowAny,)

    @swagger_auto_schema(
        tags=[TAG_AUTH],
        operation_summary="Login",
        operation_description="Login",
        request_body=LoginUserSerializer,
        responses={200: LOGIN_RESPONSE_SCHEMA, 400: ERROR_RESPONSE_SCHEMA},
    )
    def post(self, request):
        serializer = LoginUserSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.validated_data
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

            response = Response({"user": UserSerializer(user).data}, status=status.HTTP_200_OK)

            _set_auth_cookies(response, access_token, refresh)
            _set_csrf_cookie(response)

            return response
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(
        tags=[TAG_AUTH],
        operation_summary="Logout",
        operation_description="Logout",
        responses={200: MESSAGE_RESPONSE_SCHEMA, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA},
    )
    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")
        if refresh_token:
            try:
                refresh = RefreshToken(refresh_token)
                refresh.blacklist()
            except Exception as e:
                return Response({"error": "Ошибка" + str(e)}, status=status.HTTP_400_BAD_REQUEST)

        response = Response({"message": "Successfully loged out"}, status=status.HTTP_200_OK)
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")
        return response


class CookieTokenRefreshView(TokenRefreshView):
    permission_classes = (AllowAny,)

    @swagger_auto_schema(
        tags=[TAG_AUTH],
        operation_summary="Refresh access token",
        operation_description="Refresh access token",
        responses={200: REFRESH_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA},
    )
    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")

        if not refresh_token:
            return Response({"error": "Refresh token not provided"}, status=status.HTTP_401_UNAUTHORIZED)
        serializer = self.get_serializer(data={"refresh": refresh_token})

        try:
            serializer.is_valid(raise_exception=True)
        except InvalidToken:
            return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)
        token_data = serializer.validated_data
        access_token = token_data.get("access")
        rotated_refresh = token_data.get("refresh")

        response = Response(token_data, status=status.HTTP_200_OK)
        _set_auth_cookies(response, access_token, rotated_refresh)
        _set_csrf_cookie(response)
        return response


class PasswordResetRequestView(APIView):
    permission_classes = (AllowAny,)

    @swagger_auto_schema(
        tags=[TAG_AUTH],
        operation_summary="Request password reset",
        operation_description="Request password reset",
        request_body=PasswordResetRequestSerializer,
        responses={200: MESSAGE_RESPONSE_SCHEMA, 400: ERROR_RESPONSE_SCHEMA},
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data, context={"request": request})

        if serializer.is_valid():
            serializer.save(request=request)
            return Response({"message": "Инструкции по сбросу отправлены на почту"}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmView(APIView):
    permission_classes = (AllowAny,)

    @swagger_auto_schema(
        tags=[TAG_AUTH],
        operation_summary="Validate password reset token",
        operation_description="Validate password reset token",
        manual_parameters=[
            openapi.Parameter("email", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=True),
            openapi.Parameter("token", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=True),
        ],
        responses={200: MESSAGE_RESPONSE_SCHEMA, 400: ERROR_RESPONSE_SCHEMA},
    )
    def get(self, request):
        email = request.query_params.get("email")
        token = request.query_params.get("token")

        if not email or not token:
            return Response(
                {"detail": "Не указан email или токен"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = get_user_model().objects.get(email=email)
        except get_user_model().DoesNotExist:
            return Response(
                {"email": "Пользователь с таким email не найден"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not default_token_generator.check_token(user, token):
            return Response(
                {"token": "Недействительный или истёкший токен"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"message": "Токен подтверждён"}, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        tags=[TAG_AUTH],
        operation_summary="Confirm password reset",
        operation_description="Confirm password reset",
        request_body=PasswordResetConfirmSerializer,
        responses={200: MESSAGE_RESPONSE_SCHEMA, 400: ERROR_RESPONSE_SCHEMA},
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Пароль успешно обновлён"}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EmailConfirmationView(APIView):
    permission_classes = (AllowAny,)

    @swagger_auto_schema(
        tags=[TAG_AUTH],
        operation_summary="Confirm email by query params",
        operation_description="Confirm email by query params",
        manual_parameters=[
            openapi.Parameter("email", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=True),
            openapi.Parameter("token", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=True),
        ],
        responses={200: MESSAGE_RESPONSE_SCHEMA, 400: ERROR_RESPONSE_SCHEMA},
    )
    def get(self, request):
        serializer = EmailConfirmationSerializer(data=request.query_params)

        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Аккаунт подтверждён"}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=[TAG_AUTH],
        operation_summary="Confirm email by body",
        operation_description="Confirm email by body",
        request_body=EmailConfirmationSerializer,
        responses={200: MESSAGE_RESPONSE_SCHEMA, 400: ERROR_RESPONSE_SCHEMA},
    )
    def post(self, request):
        serializer = EmailConfirmationSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Аккаунт подтверждён"}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_PROFILE],
        operation_summary="Get current profile",
        operation_description="Get current profile",
        responses={200: ProfileSerializer, 401: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="put",
    decorator=swagger_auto_schema(
        tags=[TAG_PROFILE],
        operation_summary="Replace current profile",
        operation_description="Replace current profile",
        request_body=ProfileSerializer,
        responses={200: ProfileSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="patch",
    decorator=swagger_auto_schema(
        tags=[TAG_PROFILE],
        operation_summary="Update current profile",
        operation_description="Update current profile",
        request_body=ProfileSerializer,
        responses={200: ProfileSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA},
    ),
)
class ProfileView(RetrieveUpdateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = ProfileSerializer

    def get_object(self):
        profile, _ = Profile.objects.get_or_create(
            user=self.request.user,
            defaults={
                "surname": self.request.user.last_name or "",
                "name": self.request.user.first_name or "",
                "patronymic": "",
                "telegram": "",
                "email": self.request.user.email,
                "course": 0,
                "university": "",
                "vk": "",
                "job": "",
                "workplace": "",
                "specialty": "",
                "about": "",
            },
        )
        return profile


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_EVENTS],
        operation_summary="List events",
        operation_description="List events",
        responses={200: EventSerializer(many=True), 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        tags=[TAG_EVENTS],
        operation_summary="Create event",
        operation_description="Create event",
        request_body=EventSerializer,
        responses={201: EventSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA},
    ),
)
class EventListCreateView(ListCreateAPIView):
    permission_classes = (PublicReadCuratorAdminWritePermission,)
    serializer_class = EventSerializer
    queryset = Event.objects.all().select_related("leader", "specialization").prefetch_related("organizers")
    lookup_url_kwarg = "event_id"

    def get_queryset(self):
        archived = str(self.request.query_params.get("archived", "")).lower() in ("1", "true", "yes")
        return self.queryset.filter(is_archived=archived)


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_EVENTS],
        operation_summary="Get event",
        operation_description="Get event",
        responses={200: EventSerializer, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="put",
    decorator=swagger_auto_schema(
        tags=[TAG_EVENTS],
        operation_summary="Replace event",
        operation_description="Replace event",
        request_body=EventSerializer,
        responses={200: EventSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="patch",
    decorator=swagger_auto_schema(
        tags=[TAG_EVENTS],
        operation_summary="Update event",
        operation_description="Update event",
        request_body=EventSerializer,
        responses={200: EventSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="delete",
    decorator=swagger_auto_schema(
        tags=[TAG_EVENTS],
        operation_summary="Delete event",
        operation_description="Delete event",
        responses={204: "No content", 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
class EventDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = (PublicReadCuratorAdminWritePermission,)
    serializer_class = EventSerializer
    queryset = Event.objects.all().select_related("leader", "specialization").prefetch_related("organizers")
    lookup_url_kwarg = "event_id"

    def perform_destroy(self, instance):
        instance.is_archived = True
        instance.archived_at = timezone.now()
        instance.save(update_fields=("is_archived", "archived_at"))

@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_REFERENCE],
        operation_summary="List statuses",
        operation_description="List statuses",
        responses={200: StatusSerializer(many=True)},
    ),
)
class StatusListView(ListAPIView):
    permission_classes = (AllowAny,)
    serializer_class = StatusSerializer
    queryset = Status.objects.all()


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_REFERENCE],
        operation_summary="List specializations",
        operation_description="List specializations",
        responses={200: SpecializationSerializer(many=True)},
    ),
)
class SpecializationListView(ListAPIView):
    permission_classes = (AllowAny,)
    serializer_class = SpecializationSerializer
    queryset = Specialization.objects.all()
    
@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_DIRECTIONS],
        operation_summary="List directions in event",
        operation_description="List directions in event",
        responses={200: DirectionSerializer(many=True), 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        tags=[TAG_DIRECTIONS],
        operation_summary="Create direction in event",
        operation_description="Create direction in event",
        request_body=DirectionSerializer,
        responses={201: DirectionSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
class DirectionListCreateView(ListCreateAPIView):
    permission_classes = (PublicReadCuratorAdminWritePermission,)
    serializer_class = DirectionSerializer

    def get_queryset(self):
        event = get_object_or_404(Event, pk=self.kwargs.get("event_id"), is_archived=False)
        return Direction.objects.filter(event=event).select_related("event", "leader")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["event"] = get_object_or_404(Event, pk=self.kwargs.get("event_id"), is_archived=False)
        return context


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_DIRECTIONS],
        operation_summary="Get direction",
        operation_description="Get direction",
        responses={200: DirectionSerializer, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="put",
    decorator=swagger_auto_schema(
        tags=[TAG_DIRECTIONS],
        operation_summary="Replace direction",
        operation_description="Replace direction",
        request_body=DirectionSerializer,
        responses={200: DirectionSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="patch",
    decorator=swagger_auto_schema(
        tags=[TAG_DIRECTIONS],
        operation_summary="Update direction",
        operation_description="Update direction",
        request_body=DirectionSerializer,
        responses={200: DirectionSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="delete",
    decorator=swagger_auto_schema(
        tags=[TAG_DIRECTIONS],
        operation_summary="Delete direction",
        operation_description="Delete direction",
        responses={204: "No content", 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
class DirectionDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = (PublicReadCuratorAdminWritePermission,)
    serializer_class = DirectionSerializer
    lookup_url_kwarg = "direction_id"

    def get_queryset(self):
        event = get_object_or_404(Event, pk=self.kwargs.get("event_id"), is_archived=False)
        return Direction.objects.filter(event=event).select_related("event", "leader")

@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_PROJECTS],
        operation_summary="List projects in direction",
        operation_description="List projects in direction",
        responses={200: ProjectSerializer(many=True), 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        tags=[TAG_PROJECTS],
        operation_summary="Create project in direction",
        operation_description="Create project in direction",
        request_body=ProjectSerializer,
        responses={201: ProjectSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
class ProjectListCreateView(ListCreateAPIView):
    permission_classes = (PublicReadCuratorAdminWritePermission,)
    serializer_class = ProjectSerializer

    def get_queryset(self):
        event = get_object_or_404(Event, pk=self.kwargs.get("event_id"), is_archived=False)
        direction = get_object_or_404(
            Direction, pk=self.kwargs.get("direction_id"), event=event
        )
        return Project.objects.filter(direction=direction).select_related(
            "direction", "curator", "direction__event"
        )
        

    def get_serializer_context(self):
        context = super().get_serializer_context()
        event = get_object_or_404(Event, pk=self.kwargs.get("event_id"), is_archived=False)
        direction = get_object_or_404(
            Direction, pk=self.kwargs.get("direction_id"), event=event
        )
        context["direction"] = direction
        return context


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_PROJECTS],
        operation_summary="Get project",
        operation_description="Get project",
        responses={200: ProjectSerializer, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="put",
    decorator=swagger_auto_schema(
        tags=[TAG_PROJECTS],
        operation_summary="Replace project",
        operation_description="Replace project",
        request_body=ProjectSerializer,
        responses={200: ProjectSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="patch",
    decorator=swagger_auto_schema(
        tags=[TAG_PROJECTS],
        operation_summary="Update project",
        operation_description="Update project",
        request_body=ProjectSerializer,
        responses={200: ProjectSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="delete",
    decorator=swagger_auto_schema(
        tags=[TAG_PROJECTS],
        operation_summary="Delete project",
        operation_description="Delete project",
        responses={204: "No content", 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
class ProjectDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = (PublicReadCuratorAdminWritePermission,)
    serializer_class = ProjectSerializer
    lookup_url_kwarg = "project_id"
    queryset = Project.objects.filter(direction__event__is_archived=False).select_related("direction", "curator", "direction__event")

@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_PROJECTS],
        operation_summary="List all projects",
        operation_description="List all projects",
        responses={200: ProjectSerializer(many=True), 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        tags=[TAG_PROJECTS],
        operation_summary="Create project",
        operation_description="Create project",
        request_body=ProjectSerializer,
        responses={201: ProjectSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA},
    ),
)
class UserProjectListCreateView(ListCreateAPIView):
    permission_classes = (PublicReadCuratorAdminWritePermission,)
    serializer_class = ProjectSerializer
    queryset = Project.objects.filter(direction__event__is_archived=False).select_related("direction", "curator", "direction__event")


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_DIRECTIONS],
        operation_summary="List all directions",
        operation_description="List all directions",
        responses={200: DirectionSerializer(many=True), 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA},
    ),
)
class UserDirectionListView(ListAPIView):
    permission_classes = (PublicReadCuratorAdminWritePermission,)
    serializer_class = DirectionSerializer
    queryset = Direction.objects.filter(event__is_archived=False).select_related("event", "leader")

class ApplicationListView(ListCreateAPIView):
    """List and create applications."""

    filter_parameters = [
        openapi.Parameter(
            "event",
            openapi.IN_QUERY,
            description="ID мероприятия",
            type=openapi.TYPE_INTEGER,
        ),
        openapi.Parameter(
            "direction",
            openapi.IN_QUERY,
            description="ID направления",
            type=openapi.TYPE_INTEGER,
        ),
        openapi.Parameter(
            "specialization",
            openapi.IN_QUERY,
            description="ID специализации",
            type=openapi.TYPE_INTEGER,
        ),
        openapi.Parameter(
            "status",
            openapi.IN_QUERY,
            description="ID статуса",
            type=openapi.TYPE_INTEGER,
        ),
        openapi.Parameter(
            "user",
            openapi.IN_QUERY,
            description="ID пользователя",
            type=openapi.TYPE_INTEGER,
        ),
        openapi.Parameter(
            "is_approved",
            openapi.IN_QUERY,
            description="Фильтр по признаку одобрения заявки",
            type=openapi.TYPE_BOOLEAN,
        ),
        openapi.Parameter(
            "tests_assigned",
            openapi.IN_QUERY,
            description="Фильтр по назначению тестов",
            type=openapi.TYPE_BOOLEAN,
        ),
    ]
    def get_permissions(self):
        if self.request.method.lower() == "get":
            permissions = (IsAuthenticated,)
        else:
            permissions = (ProjectantOnlyPermission,)
        return [permission() for permission in permissions]

    def get_serializer_class(self):
        if self.request.method.lower() == "post":
            return ApplicationCreateSerializer
        return ApplicationSerializer
    @swagger_auto_schema(
        tags=[TAG_APPLICATIONS],
        operation_summary="List applications",
        operation_description="List applications",
        manual_parameters=filter_parameters,
        responses={200: ApplicationSerializer(many=True), 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=[TAG_APPLICATIONS],
        operation_summary="Create application",
        operation_description="Create application",
        request_body=ApplicationCreateSerializer,
        responses={201: ApplicationSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA},
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        run_crm_automation(instance, "application.created", request=request)
        output = ApplicationSerializer(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(output.data)
        return Response(output.data, status=status.HTTP_201_CREATED, headers=headers)

    def get_queryset(self):
        queryset = Application.objects.select_related(
            "user", "direction", "event", "project", "specialization", "status"
        ).filter(Q(event__is_archived=False) | Q(event__isnull=True)).order_by("-date_sub")
        
        if not has_curator_or_admin_role(self.request.user):
            assigned_event_ids = Event.objects.filter(
                Q(leader=self.request.user) | Q(organizers=self.request.user)
            ).values_list("id", flat=True)
            queryset = queryset.filter(Q(user=self.request.user) | Q(event_id__in=assigned_event_ids))

        filters = {
            "event": "event_id",
            "direction": "direction_id",
            "specialization": "specialization_id",
            "status": "status_id",
            "user": "user_id",
        }

        for param, field in filters.items():
            value = self.request.query_params.get(param)
            if value:
                queryset = queryset.filter(**{field: value})

        boolean_params = {
            "is_approved": "is_approved",
            "tests_assigned": "tests_assigned",
        }
        for param, field in boolean_params.items():
            value = self.request.query_params.get(param)
            if value is not None:
                normalized = value.lower() in {"true", "1", "yes", "t"}
                queryset = queryset.filter(**{field: normalized})

        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.method.lower() == "post":
            event_id = self.request.data.get("event") or self.request.data.get("event_id")
            direction_id = self.request.data.get("direction") or self.request.data.get("direction_id")

            if event_id:
                context["event"] = get_object_or_404(Event, pk=event_id, is_archived=False)
            if direction_id:
                context["direction"] = get_object_or_404(Direction, pk=direction_id)

        return context
    
class ApplicationDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete a specific application."""

    serializer_class = ApplicationSerializer
    lookup_url_kwarg = "application_id"

    def get_queryset(self):
        queryset = Application.objects.select_related(
            "user", "direction", "event", "project", "specialization", "status"
        ).filter(Q(event__is_archived=False) | Q(event__isnull=True))

        if not has_curator_or_admin_role(self.request.user):
            assigned_event_ids = Event.objects.filter(
                Q(leader=self.request.user) | Q(organizers=self.request.user)
            ).values_list("id", flat=True)
            queryset = queryset.filter(Q(user=self.request.user) | Q(event_id__in=assigned_event_ids))

        return queryset

    def get_permissions(self):
        if self.request.method.lower() == "get":
            permissions = (IsAuthenticated,)
        elif self.request.method.lower() in {"put", "patch"}:
            permissions = (IsAuthenticated,)
        else:
            permissions = (IsAuthenticated,)
        return [permission() for permission in permissions]

    @swagger_auto_schema(
        tags=[TAG_APPLICATIONS],
        operation_summary="Get application",
        operation_description="Получение заявки",
        responses={200: ApplicationSerializer, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=[TAG_APPLICATIONS],
        operation_summary="Update application",
        operation_description="Обновление заявки",
        request_body=ApplicationSerializer,
        responses={200: ApplicationSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=[TAG_APPLICATIONS],
        operation_summary="Delete application",
        operation_description="Удаление заявки",
        responses={204: "No content", 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    )
    def delete(self, request, *args, **kwargs):
        application = self.get_object()
        is_curator_or_admin = CuratorOrAdminPermission().has_permission(request, self)
        is_assigned_event_organizer = is_event_organizer(request.user, application.event_id)
        is_owner = application.user_id == request.user.id

        if not (is_curator_or_admin or is_assigned_event_organizer or is_owner):
            return Response(status=status.HTTP_403_FORBIDDEN)

        self.perform_destroy(application)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_update(self, serializer):
        previous_status = serializer.instance.status.name if serializer.instance.status_id else ""
        instance = serializer.save()
        current_status = instance.status.name if instance.status_id else ""
        if previous_status == current_status:
            return

        run_crm_automation(
            instance,
            "request.status_changed",
            previous_status=previous_status,
            request=self.request,
        )
        if current_status == "Прохождение тестирования":
            run_crm_automation(
                instance,
                "testing.started",
                previous_status=previous_status,
                request=self.request,
            )
        if current_status == "Добавился в орг. чат":
            run_crm_automation(
                instance,
                "notification.chat_link_opened",
                previous_status=previous_status,
                request=self.request,
            )

    def get_queryset(self):
        queryset = Application.objects.select_related(
            "user", "direction", "event", "project", "specialization", "status"
        )

        if has_curator_or_admin_role(self.request.user):
            return queryset

        assigned_event_ids = Event.objects.filter(
            Q(leader=self.request.user) | Q(organizers=self.request.user)
        ).values_list("id", flat=True)
        return queryset.filter(Q(user=self.request.user) | Q(event_id__in=assigned_event_ids))


class CRMAutomationConfigView(RetrieveUpdateAPIView):
    permission_classes = (CuratorOrAdminPermission,)
    serializer_class = CRMAutomationConfigSerializer

    def get_object(self):
        event_id = int(self.kwargs["event_id"])
        config = CRMAutomationConfig.objects.filter(
            scope=CRMAutomationConfig.SCOPE_CRM,
            event_id=event_id,
        ).first()
        if config:
            return config
        event = get_object_or_404(Event, pk=event_id, is_archived=False)
        defaults = create_default_crm_automation_config(event_id)
        return CRMAutomationConfig.objects.create(
            scope=CRMAutomationConfig.SCOPE_CRM,
            event=event,
            stages=defaults["stages"],
            triggers=defaults["triggers"],
            robots=defaults["robots"],
        )

    def put(self, request, *args, **kwargs):
        return self._save_config(request)

    def patch(self, request, *args, **kwargs):
        return self._save_config(request, partial=True)

    def _save_config(self, request, partial=False):
        event_id = int(self.kwargs["event_id"])
        event = get_object_or_404(Event, pk=event_id, is_archived=False)
        config = self.get_object()
        serializer = CRMAutomationConfigPayloadSerializer(data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        config.scope = CRMAutomationConfig.SCOPE_CRM
        config.event = event
        if "stages" in data:
            config.stages = data["stages"]
        if "triggers" in data:
            config.triggers = data["triggers"]
        if "robots" in data:
            config.robots = data["robots"]
        normalized = normalize_crm_automation_config_dict(
            {
                "scope": config.scope,
                "eventId": event_id,
                "stages": config.stages,
                "triggers": config.triggers,
                "robots": config.robots,
            }
        )
        config.stages = normalized["stages"]
        config.triggers = normalized["triggers"]
        config.robots = normalized["robots"]
        config.save()
        return Response(CRMAutomationConfigSerializer(config).data)


class CRMAutomationExecutionLogListView(ListAPIView):
    permission_classes = (CuratorOrAdminPermission,)
    serializer_class = CRMAutomationExecutionLogSerializer

    def get_queryset(self):
        return CRMAutomationExecutionLog.objects.filter(
            event_id=self.kwargs["event_id"],
            config__scope=CRMAutomationConfig.SCOPE_CRM,
        ).select_related("config", "application")


class CRMAutomationPendingRunView(APIView):
    permission_classes = (CuratorOrAdminPermission,)

    def post(self, request, *args, **kwargs):
        return Response(run_due_crm_automation())


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


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        tags=[TAG_NOTIFICATIONS],
        operation_summary="Список уведомлений",
        operation_description="Получение уведомлений текущего пользователя",
        responses={200: NotificationSerializer(many=True), 401: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        tags=[TAG_NOTIFICATIONS],
        operation_summary="Создать уведомление",
        operation_description="Создание уведомления для текущего пользователя",
        request_body=NotificationCreateSerializer,
        responses={201: NotificationSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA},
    ),
)
class NotificationListCreateView(ListCreateAPIView):
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).select_related("user")

    def get_serializer_class(self):
        if self.request.method.lower() == "post":
            return NotificationCreateSerializer
        return NotificationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        output = NotificationSerializer(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(output.data)
        return Response(output.data, status=status.HTTP_201_CREATED, headers=headers)


@method_decorator(
    name="patch",
    decorator=swagger_auto_schema(
        tags=[TAG_NOTIFICATIONS],
        operation_summary="Обновить уведомление",
        operation_description="Обновление уведомления текущего пользователя",
        request_body=NotificationSerializer,
        responses={200: NotificationSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
@method_decorator(
    name="delete",
    decorator=swagger_auto_schema(
        tags=[TAG_NOTIFICATIONS],
        operation_summary="Удалить уведомление",
        operation_description="Удаление уведомления текущего пользователя",
        responses={204: "No content", 401: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
class NotificationDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = NotificationSerializer
    lookup_url_kwarg = "notification_id"

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).select_related("user")


@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        tags=[TAG_NOTIFICATIONS],
        operation_summary="Отметить все как прочитанные",
        operation_description="Отметить все уведомления текущего пользователя как прочитанные",
        responses={200: MESSAGE_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA},
    ),
)
class NotificationMarkAllReadView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        Notification.objects.filter(user=request.user, read=False).update(read=True)
        return Response({"message": "Все уведомления отмечены как прочитанные."}, status=status.HTTP_200_OK)


@method_decorator(
    name="delete",
    decorator=swagger_auto_schema(
        tags=[TAG_NOTIFICATIONS],
        operation_summary="Удалить все уведомления",
        operation_description="Удаление всех уведомлений текущего пользователя",
        responses={204: "No content", 401: ERROR_RESPONSE_SCHEMA},
    ),
)
class NotificationClearView(APIView):
    permission_classes = (IsAuthenticated,)

    def delete(self, request, *args, **kwargs):
        Notification.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        tags=[TAG_APPLICATIONS],
        operation_summary="Create application for direction",
        operation_description="Create application for direction",
        request_body=ApplicationCreateSerializer,
        responses={201: ApplicationSerializer, 400: ERROR_RESPONSE_SCHEMA, 401: ERROR_RESPONSE_SCHEMA, 403: ERROR_RESPONSE_SCHEMA, 404: ERROR_RESPONSE_SCHEMA},
    ),
)
class DirectionApplicationCreateView(CreateAPIView):
    permission_classes = (ProjectantOnlyPermission,)
    serializer_class = ApplicationCreateSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        event = get_object_or_404(Event, pk=self.kwargs.get("event_id"), is_archived=False)
        direction = get_object_or_404(
            Direction, pk=self.kwargs.get("direction_id"), event=event
        )
        context.update({"event": event, "direction": direction})
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        output = ApplicationSerializer(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(output.data)
        return Response(output.data, status=status.HTTP_201_CREATED, headers=headers)
