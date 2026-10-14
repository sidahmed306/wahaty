from django.db.models import Count, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from core.access import is_direction
from core.permissions import IsDirectionOrReadOnly

from .filters import DateVarietyFilter, OasisFilter
from .models import DateVariety, Oasis, OasisPhoto, Region
from .serializers import (
    DateVarietySerializer,
    OasisPhotoSerializer,
    OasisSerializer,
    RegionSerializer,
)


class PublicCatalogViewSet(viewsets.ModelViewSet):
    """Lecture publique (sans compte) ; écriture réservée à la Direction.

    - Le public ne voit que les éléments actifs ; la Direction voit aussi les désactivés.
    - Supprimer = désactiver (suppression douce) : rien n'est effacé de la base.
    """

    permission_classes = [IsDirectionOrReadOnly]
    lookup_field = "slug"
    filter_backends = [DjangoFilterBackend]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        qs = super().get_queryset()
        return qs if is_direction(self.request.user) else qs.filter(is_active=True)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])


class RegionViewSet(PublicCatalogViewSet):
    """Régions (moughataas)."""

    # order_by explicite : Django n'applique pas Meta.ordering quand on compte (GROUP BY).
    queryset = Region.objects.annotate(
        oases_count=Count("oases", filter=Q(oases__is_active=True))
    ).order_by("order", "name_fr")
    serializer_class = RegionSerializer


class OasisViewSet(PublicCatalogViewSet):
    """Oasis. Filtres : `?region=atar`, `?variety=amhat`, `?search=…`."""

    queryset = Oasis.objects.select_related("region").prefetch_related("varieties", "photos")
    serializer_class = OasisSerializer
    filterset_class = OasisFilter


class DateVarietyViewSet(PublicCatalogViewSet):
    """Variétés de dattes. Filtres : `?oasis=…`, `?texture=soft`, `?in_season=7`, `?search=…`."""

    queryset = DateVariety.objects.prefetch_related("oases")
    serializer_class = DateVarietySerializer
    filterset_class = DateVarietyFilter


class OasisPhotoViewSet(viewsets.ModelViewSet):
    """Photos d'oasis (envoi en multipart). Filtre : `?oasis=<slug>`."""

    serializer_class = OasisPhotoSerializer
    permission_classes = [IsDirectionOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = OasisPhoto.objects.select_related("oasis")
        if not is_direction(self.request.user):
            qs = qs.filter(oasis__is_active=True)
        if oasis := self.request.query_params.get("oasis"):
            qs = qs.filter(oasis__slug=oasis)
        return qs

    def perform_destroy(self, instance):
        # Une photo n'a pas d'historique d'argent : on l'efface vraiment, fichier compris.
        instance.image.delete(save=False)
        instance.delete()
