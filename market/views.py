from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from accounts.models import Role
from core.access import can_write_for
from core.mixins import OwnedQuerysetMixin, SoftDeleteMixin
from core.permissions import IsDirection, OwnerPermission, role_permission

from . import services
from .filters import ListingFilter
from .models import Listing, ListingStatus
from .serializers import (
    ListingPhotoSerializer,
    MyListingSerializer,
    PhotoUploadSerializer,
    PublicListingSerializer,
    RejectSerializer,
)

MarketAccess = role_permission(Role.FARMER, Role.SELLER, Role.FIELD_AGENT, Role.DIRECTION)
LISTING_QS = Listing.objects.filter(is_active=True).select_related(
    "owner__profile", "variety", "oasis__region"
)


def listing_error(exc):
    return ValidationError({"detail": str(exc)})


class MarketPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class PublicListingViewSet(viewsets.ReadOnlyModelViewSet):
    """Marché des dattes (public, sans compte) : seulement les annonces **publiées**.

    Filtres : `?variety=amhat`, `?oasis=`, `?region=atar`, `?min_price=`, `?max_price=`,
    `?min_quantity=`, `?search=`. Tri : `?ordering=price_per_kg` (ou `-price_per_kg`,
    `-published_at`, `quantity_kg`). Pages de 20 (`?page=2`).
    """

    queryset = LISTING_QS.filter(status=ListingStatus.PUBLISHED).prefetch_related("photos")
    serializer_class = PublicListingSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ListingFilter
    ordering_fields = ["price_per_kg", "published_at", "quantity_kg"]
    ordering = ["-published_at"]
    pagination_class = MarketPagination


class MyListingViewSet(SoftDeleteMixin, OwnedQuerysetMixin, viewsets.ModelViewSet):
    """Mes annonces (agriculteur, vendeur ; un agent indique `owner` pour son agriculteur).

    Actions : `submit` (envoyer en validation), `unpublish` (retirer), `sold` (vendue),
    `photos` (ajouter, multipart `image`), `photos/{id}` (DELETE). Filtre : `?status=`.
    """

    queryset = LISTING_QS.prefetch_related("photos")
    serializer_class = MyListingSerializer
    permission_classes = [MarketAccess, OwnerPermission]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status"]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def perform_create(self, serializer):
        # MarketAccess + can_write_for : le propriétaire est forcément agriculteur ou vendeur.
        owner = self.get_owner_for_create()
        if not can_write_for(self.request.user, owner):
            raise PermissionDenied(_("Agriculteur introuvable ou non géré par vous."))
        data = serializer.validated_data
        serializer.save(
            owner=owner,
            language=data.get("language", owner.preferred_language),
            contact_phone=data.get("contact_phone", owner.phone),
            whatsapp_phone=data.get("whatsapp_phone", owner.profile.whatsapp),
        )

    def perform_update(self, serializer):
        if not serializer.instance.is_editable:
            raise ValidationError(
                {"detail": _("Retirez d'abord l'annonce (retour en brouillon) pour la modifier.")}
            )
        serializer.save()

    def _run(self, func, *args):
        listing = self.get_object()
        try:
            listing = func(listing, *args)
        except services.ListingError as exc:
            raise listing_error(exc) from exc
        return Response(self.get_serializer(self.get_queryset().get(pk=listing.pk)).data)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """Envoyer l'annonce à la Direction pour validation."""
        return self._run(services.submit)

    @action(detail=True, methods=["post"])
    def unpublish(self, request, pk=None):
        """Retirer l'annonce du marché (retour en brouillon)."""
        return self._run(services.unpublish)

    @action(detail=True, methods=["post"])
    def sold(self, request, pk=None):
        """Marquer l'annonce comme vendue (elle quitte le marché)."""
        return self._run(services.mark_sold)

    @action(detail=True, methods=["post"])
    def photos(self, request, pk=None):
        """Ajouter une photo (5 maximum, redimensionnée automatiquement)."""
        listing = self.get_object()
        body = PhotoUploadSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            photo = services.add_photo(listing, **body.validated_data)
        except services.ListingError as exc:
            raise listing_error(exc) from exc
        return Response(ListingPhotoSerializer(photo).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"photos/(?P<photo_id>\d+)")
    def delete_photo(self, request, pk=None, photo_id=None):
        """Supprimer une photo (le fichier est effacé)."""
        listing = self.get_object()
        photo = listing.photos.filter(pk=photo_id).first()
        if photo is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            services.remove_photo(photo)
        except services.ListingError as exc:
            raise listing_error(exc) from exc
        return Response(status=status.HTTP_204_NO_CONTENT)


class ListingReviewViewSet(viewsets.ReadOnlyModelViewSet):
    """Direction : annonces à valider (par défaut `?status=pending`), publier ou refuser."""

    serializer_class = MyListingSerializer
    permission_classes = [IsDirection]

    def get_queryset(self):
        wanted = self.request.query_params.get("status", ListingStatus.PENDING)
        return LISTING_QS.prefetch_related("photos").filter(status=wanted).order_by("created_at")

    def get_object(self):
        # Toute annonce active, quel que soit son statut (le filtre ne vaut que pour la liste).
        return get_object_or_404(LISTING_QS, pk=self.kwargs["pk"])

    def _run(self, func, *args):
        try:
            listing = func(self.get_object(), self.request.user, *args)
        except services.ListingError as exc:
            raise listing_error(exc) from exc
        return Response(self.get_serializer(LISTING_QS.get(pk=listing.pk)).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Publier l'annonce sur le marché (le vendeur est notifié)."""
        return self._run(services.approve)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """Refuser l'annonce avec un motif (le vendeur est notifié)."""
        body = RejectSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return self._run(services.reject, body.validated_data["reason"])
