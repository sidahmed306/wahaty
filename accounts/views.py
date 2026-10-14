from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import (
    ApprovedTokenRefreshSerializer,
    LogoutSerializer,
    MeSerializer,
    PhoneTokenObtainPairSerializer,
    RegisterSerializer,
)


class RegisterView(generics.CreateAPIView):
    """Inscription agriculteur et/ou vendeur. Le compte attend la validation de la Direction."""

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_scope = "register"


class LoginView(TokenObtainPairView):
    """Connexion : téléphone + mot de passe → jetons « access » et « refresh »."""

    serializer_class = PhoneTokenObtainPairSerializer
    throttle_scope = "login"


class RefreshView(TokenRefreshView):
    """Nouveau jeton « access » à partir du jeton « refresh »."""

    serializer_class = ApprovedTokenRefreshSerializer
    throttle_scope = "login"


class LogoutView(APIView):
    """Déconnexion : le jeton « refresh » est mis sur liste noire."""

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = RefreshToken(serializer.validated_data["refresh"])
        except TokenError:
            return Response({"detail": "Jeton invalide."}, status=status.HTTP_400_BAD_REQUEST)
        if str(token["user_id"]) != str(request.user.pk):
            return Response({"detail": "Jeton invalide."}, status=status.HTTP_400_BAD_REQUEST)
        token.blacklist()
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(generics.RetrieveUpdateAPIView):
    """Mon compte : lecture et modification de mes informations."""

    serializer_class = MeSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user
