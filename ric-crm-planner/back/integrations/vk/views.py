import logging
import secrets

from django.conf import settings
from django.core import signing
from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import Application, Profile
from users.permissions import CuratorOrAdminPermission
from users.vk_profiles import get_vk_bot_url, refresh_profile_vk_user_id

from .crm_notifications import (
    CHAT_LINK_PLACEHOLDER,
    inject_application_chat_link,
    mark_application_chat_link_opened,
    notify_organizers_about_vk_error,
    send_application_vk_message,
)
from .planner_invites import (
    handle_vk_message_event,
    handle_vk_message_new_event,
    send_planner_invites_for_event,
    send_vk_start_confirmation,
)
from .serializers import VKApplicationMessageSerializer, VKPlannerInviteSerializer, VKSendTestSerializer
from .services import VKAPIError, VKConfigurationError, normalize_vk_group_id, send_vk_message


logger = logging.getLogger(__name__)


def plain_response(text: str, status_code: int = status.HTTP_200_OK) -> HttpResponse:
    return HttpResponse(text, status=status_code, content_type="text/plain; charset=utf-8")


@method_decorator(csrf_exempt, name="dispatch")
class VKCallbackView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    @swagger_auto_schema(
        operation_summary="VK Callback API endpoint",
        operation_description="Accepts VK Callback API events and returns confirmation or ok.",
        request_body=openapi.Schema(type=openapi.TYPE_OBJECT),
        responses={200: "confirmation code or ok", 403: "Invalid secret"},
    )
    def post(self, request):
        payload = request.data if isinstance(request.data, dict) else {}
        event_type = str(payload.get("type", ""))

        if event_type == "confirmation":
            expected_group_id = normalize_vk_group_id()
            received_group_id = normalize_vk_group_id(payload.get("group_id"))
            if expected_group_id and received_group_id and expected_group_id != received_group_id:
                return Response({"detail": "Invalid VK group_id."}, status=status.HTTP_403_FORBIDDEN)
            if not settings.VK_CONFIRMATION_CODE:
                return Response(
                    {"detail": "VK confirmation code is not configured."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            return plain_response(settings.VK_CONFIRMATION_CODE)

        expected_secret = settings.VK_CALLBACK_SECRET or ""
        if expected_secret:
            received_secret = str(payload.get("secret", ""))
            if not secrets.compare_digest(received_secret, expected_secret):
                return Response({"detail": "Invalid VK callback secret."}, status=status.HTTP_403_FORBIDDEN)

        if event_type == "message_new":
            try:
                handle_vk_message_new_event(payload)
            except (VKConfigurationError, VKAPIError, ValueError) as exc:
                # VK must receive "ok"; business errors are handled by follow-up bot messages when possible.
                logger.warning("VK message_new handling failed: %s", exc, exc_info=True)
                pass
        elif event_type == "message_event":
            try:
                handle_vk_message_event(payload)
            except (VKConfigurationError, VKAPIError, ValueError) as exc:
                logger.warning("VK message_event handling failed: %s", exc, exc_info=True)
                pass

        return plain_response("ok")


class VKSendTestView(APIView):
    permission_classes = (CuratorOrAdminPermission,)

    @swagger_auto_schema(
        operation_summary="Send test VK message",
        operation_description="Sends a VK message via configured community token. Available for curators/admins.",
        request_body=VKSendTestSerializer,
        responses={200: openapi.Response("VK message id"), 400: "Validation error", 503: "VK is not configured"},
    )
    def post(self, request):
        serializer = VKSendTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            message_id = send_vk_message(**serializer.validated_data)
        except VKConfigurationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except VKAPIError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"message_id": message_id})


class VKApplicationMessageView(APIView):
    permission_classes = (CuratorOrAdminPermission,)

    @swagger_auto_schema(
        operation_summary="Send VK message for application",
        operation_description="Sends configured CRM robot VK message to the application owner.",
        request_body=VKApplicationMessageSerializer,
        responses={200: openapi.Response("VK message id"), 400: "Validation or VK API error", 404: "Application not found"},
    )
    def post(self, request, application_id: int):
        application = get_object_or_404(
            Application.objects.select_related("user", "event", "event__leader").prefetch_related("event__organizers"),
            pk=application_id,
        )
        serializer = VKApplicationMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.validated_data["text"]
        if serializer.validated_data.get("include_chat_link") or CHAT_LINK_PLACEHOLDER in message:
            message = inject_application_chat_link(
                message,
                application,
                request,
                chat_url=serializer.validated_data.get("chat_url", ""),
            )

        try:
            message_id = send_application_vk_message(application, message)
        except (VKConfigurationError, VKAPIError, ValueError) as exc:
            notify_organizers_about_vk_error(application, str(exc))
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message_id": message_id}, status=status.HTTP_200_OK)


class VKPlannerInviteView(APIView):
    permission_classes = (CuratorOrAdminPermission,)

    @swagger_auto_schema(
        operation_summary="Send planner invite VK messages",
        operation_description=(
            "Sends planner readiness VK messages with Accept/Decline buttons "
            "to applications in status Добавился в орг. чат for the event."
        ),
        responses={200: openapi.Response("VK planner invite result"), 503: "VK is disabled or not configured"},
    )
    def post(self, request, event_id: int):
        serializer = VKPlannerInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = send_planner_invites_for_event(
                event_id,
                recipient_mode=serializer.validated_data["recipient_mode"],
                message=serializer.validated_data.get("message", ""),
            )
        except VKConfigurationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(result, status=status.HTTP_200_OK)


class VKBotStatusView(APIView):
    def get(self, request):
        profile = Profile.objects.filter(user=request.user).first()
        if profile:
            refresh_profile_vk_user_id(profile)

        return Response(
            {
                "confirmed": bool(profile and profile.vk_confirmed_at),
                "vk": profile.vk if profile else "",
                "vk_user_id": profile.vk_user_id if profile else None,
                "bot_url": get_vk_bot_url(),
            }
        )


class VKStartConfirmationPromptView(APIView):
    @swagger_auto_schema(
        operation_summary="Send VK start-confirmation button to current user",
        operation_description=(
            "Sends the authenticated user a VK message with a «Начать» button so they can "
            "confirm their VK without the native start button. Requires the user to have "
            "opened the dialog with the community first."
        ),
        responses={
            200: openapi.Response("VK message id"),
            400: "VK is not set in profile or cannot be resolved",
            409: "User has not opened the dialog with the community yet",
            503: "VK is disabled or not configured",
        },
    )
    def post(self, request):
        profile = Profile.objects.filter(user=request.user).first()
        if not profile or not (profile.vk or "").strip():
            return Response(
                {"detail": "В вашем профиле не указан VK."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if profile.vk_confirmed_at:
            return Response({"detail": "VK уже подтвержден.", "confirmed": True}, status=status.HTTP_200_OK)

        try:
            message_id = send_vk_start_confirmation(profile)
        except VKConfigurationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except ValueError:
            return Response(
                {"detail": "Не удалось определить ваш VK ID. Проверьте ссылку на VK в профиле."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except VKAPIError as exc:
            if exc.code == 901:
                return Response(
                    {
                        "detail": (
                            "Сначала откройте диалог с ботом в VK и разрешите сообщения, "
                            "затем повторите."
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            return Response({"detail": exc.message, "code": exc.code}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message_id": message_id, "sent": True}, status=status.HTTP_200_OK)


class VKChatLinkRedirectView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    @swagger_auto_schema(
        operation_summary="Open individual VK chat link",
        operation_description=(
            "Marks application as joined to org chat by signed token and redirects projectant to VK chat."
        ),
        responses={302: "Redirect to VK chat", 400: "Invalid or expired token", 503: "VK chat url is not configured"},
    )
    def get(self, request, token: str):
        try:
            _, redirect_url = mark_application_chat_link_opened(token)
        except signing.SignatureExpired:
            return Response({"detail": "VK chat link has expired."}, status=status.HTTP_400_BAD_REQUEST)
        except (signing.BadSignature, KeyError, Application.DoesNotExist):
            return Response({"detail": "Invalid VK chat link."}, status=status.HTTP_400_BAD_REQUEST)

        if not redirect_url:
            return Response(
                {"detail": "VK org chat url is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return redirect(redirect_url)
