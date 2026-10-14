from django.db.models import Q
from rest_framework import generics, mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from core.access import managed_farmers
from core.permissions import IsDirection, IsFieldAgent

from .models import AccountStatus, User
from .serializers import (
    ApprovedTokenRefreshSerializer,
    LogoutSerializer,
    ManagedFarmerSerializer,
    MeSerializer,
    PhoneTokenObtainPairSerializer,
    RegisterSerializer,
    UserManageSerializer,
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


class UserManageViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Direction : liste des comptes, validation, suspension, désactivation.

    Filtres : `?status=pending`, `?role=seller`, `?search=texte` (nom ou téléphone).
    """

    serializer_class = UserManageSerializer
    permission_classes = [IsDirection]
    http_method_names = ["get", "patch", "post", "head", "options"]

    def get_queryset(self):
        qs = User.objects.order_by("-date_joined")
        params = self.request.query_params
        if status_ := params.get("status"):
            qs = qs.filter(status=status_)
        if role := params.get("role"):
            qs = qs.filter(roles__contains=[role])
        if search := params.get("search"):
            qs = qs.filter(Q(full_name__icontains=search) | Q(phone__icontains=search))
        return qs

    def perform_update(self, serializer):
        if serializer.instance.pk == self.request.user.pk:
            raise PermissionDenied("Vous ne pouvez pas modifier votre propre compte ici.")
        serializer.save()

    def _set_status(self, request, new_status):
        user = self.get_object()
        serializer = self.get_serializer(user, data={"status": new_status}, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Valider un compte en attente."""
        return self._set_status(request, AccountStatus.APPROVED)

    @action(detail=True, methods=["post"])
    def suspend(self, request, pk=None):
        """Suspendre un compte (il perd l'accès immédiatement)."""
        return self._set_status(request, AccountStatus.SUSPENDED)


class ManagedFarmerViewSet(viewsets.ReadOnlyModelViewSet):
    """Agent de terrain : les agriculteurs qu'il a inscrits."""

    serializer_class = ManagedFarmerSerializer
    permission_classes = [IsFieldAgent]

    def get_queryset(self):
        return managed_farmers(self.request.user).order_by("full_name")


class MeView(generics.RetrieveUpdateAPIView):
    """Mon compte : lecture et modification de mes informations."""

    serializer_class = MeSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user
