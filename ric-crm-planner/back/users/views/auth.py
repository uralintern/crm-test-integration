"""Регистрация, вход, выход, обновление токена, сброс пароля, подтверждение email."""

from django.conf import settings
import secrets
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.decorators import method_decorator
from rest_framework import status
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from users.serializers import (
    EmailConfirmationSerializer,
    LoginUserSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterUserSerializer,
    UserSerializer,
)
from .schema import (
    ERROR_RESPONSE_SCHEMA,
    LOGIN_RESPONSE_SCHEMA,
    MESSAGE_RESPONSE_SCHEMA,
    REFRESH_RESPONSE_SCHEMA,
    TAG_AUTH,
)


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
