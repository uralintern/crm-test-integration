"""Уведомления."""

from django.utils.decorators import method_decorator
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from users.serializers import NotificationCreateSerializer, NotificationSerializer
from users.models import Notification
from .schema import ERROR_RESPONSE_SCHEMA, MESSAGE_RESPONSE_SCHEMA, TAG_NOTIFICATIONS


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
