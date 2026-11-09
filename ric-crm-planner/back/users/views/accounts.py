"""Текущий пользователь, список пользователей и профиль."""

from django.contrib.auth import get_user_model
from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema
from rest_framework.generics import ListAPIView, RetrieveAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from users.serializers import ProfileSerializer, UserSerializer
from users.models import Profile
from .schema import ERROR_RESPONSE_SCHEMA, TAG_PROFILE, TAG_USERS


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
