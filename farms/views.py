from django.db.models import F, Q, Sum
from django.db.models.functions import Coalesce
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from accounts.models import Role
from core.access import can_write_for
from core.mixins import OwnedQuerysetMixin, SoftDeleteMixin
from core.permissions import OwnerPermission, role_permission

from .filters import FarmFilter, HarvestFilter, PalmGroupFilter
from .models import Farm, Harvest, PalmGroup
from .serializers import (
    FarmSerializer,
    HarvestSerializer,
    PalmGroupSerializer,
    PalmTotalsSerializer,
    ProductionLineSerializer,
    SeasonTotalSerializer,
)
from .totals import palm_totals, production_totals

# Espace agriculteur : l'agriculteur, son agent de terrain, et la Direction (lecture).
FarmSpaceAccess = role_permission(Role.FARMER, Role.FIELD_AGENT, Role.DIRECTION)

NOT_YOURS = _("Vous ne pouvez pas saisir de données pour cette ferme.")


def active_sum(field):
    return Coalesce(Sum(f"palm_groups__{field}", filter=Q(palm_groups__is_active=True)), 0)


class FarmViewSet(SoftDeleteMixin, OwnedQuerysetMixin, viewsets.ModelViewSet):
    """Fermes. Un agent de terrain indique `owner` (id de l'agriculteur) à la création.

    Filtres : `?oasis=<slug>`, `?region=<slug>`, `?owner=<id>`.
    """

    queryset = (
        Farm.objects.filter(is_active=True)
        .select_related("oasis", "owner")
        .annotate(
            productive_palms=active_sum("productive_count"),
            young_palms=active_sum("young_count"),
        )
        .annotate(total_palms=F("productive_palms") + F("young_palms"))
        .order_by("name", "id")
    )
    serializer_class = FarmSerializer
    permission_classes = [FarmSpaceAccess, OwnerPermission]
    filter_backends = [DjangoFilterBackend]
    filterset_class = FarmFilter

    @staticmethod
    def check_unique_name(owner, name, exclude_pk=None):
        same = Farm.objects.filter(owner=owner, name__iexact=name, is_active=True)
        if same.exclude(pk=exclude_pk).exists():
            raise ValidationError({"name": _("Cet agriculteur a déjà une ferme avec ce nom.")})

    def perform_create(self, serializer):
        owner = self.get_owner_for_create()
        if not can_write_for(self.request.user, owner) or not owner.has_role(Role.FARMER):
            raise PermissionDenied(_("Agriculteur introuvable ou non géré par vous."))
        self.check_unique_name(owner, serializer.validated_data["name"])
        serializer.save(owner=owner, created_by=self.request.user)

    def perform_update(self, serializer):
        farm = serializer.instance
        if "name" in serializer.validated_data:
            self.check_unique_name(farm.owner, serializer.validated_data["name"], farm.pk)
        serializer.save()

    @action(detail=True)
    def summary(self, request, pk=None):
        """Résumé d'une ferme : palmiers par variété et production par saison."""
        farm = self.get_object()
        palms, palms_total = palm_totals(farm.palm_groups.all())
        lines, by_season = production_totals(farm.harvests.all())
        return Response(
            {
                "farm": farm.id,
                "palms": PalmTotalsSerializer(palms, many=True).data,
                "palms_total": palms_total,
                "production": ProductionLineSerializer(lines, many=True).data,
                "production_by_season": SeasonTotalSerializer(by_season, many=True).data,
            }
        )


class FarmChildViewSet(SoftDeleteMixin, OwnedQuerysetMixin, viewsets.ModelViewSet):
    """Base des palmiers et récoltes : le propriétaire est celui de la ferme."""

    owner_field = "farm__owner"
    permission_classes = [FarmSpaceAccess, OwnerPermission]
    filter_backends = [DjangoFilterBackend]

    def check_farm(self, farm):
        if not can_write_for(self.request.user, farm.owner):
            raise PermissionDenied(NOT_YOURS)

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True, farm__is_active=True)

    def perform_create(self, serializer):
        self.check_farm(serializer.validated_data["farm"])
        serializer.save(**self.extra_save_kwargs())

    def perform_update(self, serializer):
        if "farm" in serializer.validated_data:
            self.check_farm(serializer.validated_data["farm"])
        serializer.save()

    def extra_save_kwargs(self):
        return {}


class PalmGroupViewSet(FarmChildViewSet):
    """Palmiers par variété (productifs / jeunes). Filtres : `?farm=`, `?variety=`."""

    queryset = PalmGroup.objects.select_related("farm", "variety")
    serializer_class = PalmGroupSerializer
    filterset_class = PalmGroupFilter

    @action(detail=False)
    def totals(self, request):
        """Total des palmiers par variété, sur les fermes visibles (filtres possibles)."""
        palms, palms_total = palm_totals(self.filter_queryset(self.get_queryset()))
        return Response(
            {"palms": PalmTotalsSerializer(palms, many=True).data, "palms_total": palms_total}
        )


class HarvestViewSet(FarmChildViewSet):
    """Récoltes. Filtres : `?farm=`, `?variety=`, `?season=`, `?date_from=`, `?date_to=`."""

    queryset = Harvest.objects.select_related("farm", "variety")
    serializer_class = HarvestSerializer
    filterset_class = HarvestFilter

    def extra_save_kwargs(self):
        return {"created_by": self.request.user}

    @action(detail=False)
    def totals(self, request):
        """Production (kg) par saison et variété, sur les récoltes visibles (filtres possibles)."""
        lines, by_season = production_totals(self.filter_queryset(self.get_queryset()))
        return Response(
            {
                "production": ProductionLineSerializer(lines, many=True).data,
                "production_by_season": SeasonTotalSerializer(by_season, many=True).data,
            }
        )
