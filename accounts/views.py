from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from core.access import managed_farmers
from core.permissions import IsDirection, IsFieldAgent

from .claims import ClaimError, claim_account, new_claim_code
from .models import AccountStatus, User
from .serializers import (
    AgentFarmerCreateSerializer,
    ApprovedTokenRefreshSerializer,
    ClaimAccountSerializer,
    ClaimCodeSerializer,
    LogoutSerializer,
    ManagedFarmerSerializer,
    MeSerializer,
    PhoneTokenObtainPairSerializer,
    ProfilePhotoSerializer,
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

    @extend_schema(
        request=LogoutSerializer, responses={205: OpenApiResponse(description="Déconnecté")}
    )
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = RefreshToken(serializer.validated_data["refresh"])
        except TokenError:
            return Response({"detail": _("Jeton invalide.")}, status=status.HTTP_400_BAD_REQUEST)
        if str(token["user_id"]) != str(request.user.pk):
            return Response({"detail": _("Jeton invalide.")}, status=status.HTTP_400_BAD_REQUEST)
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
            raise PermissionDenied(_("Vous ne pouvez pas modifier votre propre compte ici."))
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


class ManagedFarmerViewSet(mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    """Agent de terrain : inscrire un agriculteur et lister ceux qu'il a inscrits.

    À l'inscription, la réponse contient un **code de reprise** (affiché une seule fois)
    que l'agent remet à l'agriculteur pour qu'il prenne la main sur son compte.
    """

    permission_classes = [IsFieldAgent]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # génération de la documentation
            return User.objects.none()
        return managed_farmers(self.request.user).order_by("full_name")

    def get_serializer_class(self):
        return AgentFarmerCreateSerializer if self.action == "create" else ManagedFarmerSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            farmer = serializer.save()
            code, expires_at = new_claim_code(farmer, request.user)
        data = {
            **ManagedFarmerSerializer(farmer).data,
            **ClaimCodeSerializer({"claim_code": code, "claim_code_expires_at": expires_at}).data,
        }
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="claim-code")
    def claim_code(self, request, pk=None):
        """Nouveau code de reprise (l'ancien ne marche plus). Impossible après la reprise."""
        farmer = self.get_object()
        try:
            code, expires_at = new_claim_code(farmer, request.user)
        except ClaimError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            ClaimCodeSerializer({"claim_code": code, "claim_code_expires_at": expires_at}).data
        )


class ClaimAccountView(APIView):
    """L'agriculteur reprend la main : téléphone + code de reprise + nouveau mot de passe."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_scope = "login"

    @extend_schema(request=ClaimAccountSerializer, responses={200: OpenApiResponse()})
    def post(self, request):
        serializer = ClaimAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            claim_account(**serializer.validated_data)
        except ClaimError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"detail": _("Compte repris. Vous pouvez vous connecter avec votre mot de passe.")}
        )


class MePhotoView(APIView):
    """Ma photo de profil : PUT (multipart, champ « photo ») pour la changer, DELETE l'efface."""

    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(request=ProfilePhotoSerializer, responses=ProfilePhotoSerializer)
    def put(self, request):
        profile = request.user.profile
        serializer = ProfilePhotoSerializer(profile, data=request.data)
        serializer.is_valid(raise_exception=True)
        if profile.photo:
            profile.photo.delete(save=False)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(responses={204: None})
    def delete(self, request):
        request.user.profile.photo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(generics.RetrieveUpdateAPIView):
    """Mon compte : lecture et modification de mes informations."""

    serializer_class = MeSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user
