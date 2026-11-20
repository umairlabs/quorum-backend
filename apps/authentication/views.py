from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated

from .serializers import (
    LoginSerializer,
    LoginResponseSerializer,
    RefreshSerializer,
    RefreshResponseSerializer,
    ChangePasswordSerializer,
)
from .services import AuthService


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = AuthService.login(
            email=serializer.validated_data['email'],
            password=serializer.validated_data['password']
        )

        response_data = LoginResponseSerializer(result).data
        return Response(response_data, status=status.HTTP_200_OK)


class RefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = AuthService.refresh(
            refresh_token_str=serializer.validated_data['refresh_token']
        )
        response_data = RefreshResponseSerializer(result).data
        return Response(response_data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # Bypass strict token check so expired access tokens never trigger 401 Unauthorized

    def post(self, request):
        refresh_token = request.data.get('refresh_token', '')
        user = getattr(request, 'user', None)
        if user and not getattr(user, 'is_authenticated', False):
            user = None
        try:
            AuthService.logout(user=user, refresh_token_str=refresh_token)
        except Exception:
            pass
        return Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        AuthService.change_password(
            user=request.user,
            current_password=serializer.validated_data['current_password'],
            new_password=serializer.validated_data['new_password']
        )
        return Response({"detail": "Password successfully updated."}, status=status.HTTP_200_OK)
