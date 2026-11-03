from rest_framework import generics, permissions, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import User
from .serializers import (
    AdminUserSerializer,
    EmailTokenObtainPairSerializer,
    RegisterSerializer,
    UserSerializer,
)


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.none()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'register'


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'


class LogoutView(APIView):
    """Revoca el refresh token enviado (lo agrega a la blacklist).

    El access token que autentica la petición NO queda invalidado: sigue
    siendo válido hasta su expiración (1 hora por defecto).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get('refresh')
        if not refresh or not isinstance(refresh, str):
            return Response(
                {'detail': 'Se requiere el refresh token en el campo "refresh".'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh)
            # Solo el dueño del refresh puede revocarlo: evita que cualquier
            # usuario autenticado invalide tokens ajenos si los obtiene.
            if str(token.payload.get(jwt_settings.USER_ID_CLAIM)) != str(
                request.user.pk
            ):
                return Response(
                    {'detail': 'Token inválido o revocado.'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            token.blacklist()
        except (TokenError, InvalidToken):
            return Response(
                {'detail': 'Token inválido o revocado.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [permissions.IsAdminUser]
