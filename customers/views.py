from django.db.models import Q
from django.utils.translation import gettext as _
from rest_framework import generics, mixins, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response

from core.mixins import SellerMixin, SoftDeleteMixin
from core.models import PlatformSettings
from core.permissions import IsDirection

from .models import Customer, Payment
from .segments import Segment
from .serializers import CustomerSerializer, PaymentSerializer, PlatformSettingsSerializer
from .stats import enrich, with_paid_total


class CustomerViewSet(
    SoftDeleteMixin,
    SellerMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Clients du vendeur, avec dette et **segment calculé** (nouveau, fidèle, premium,
    inactif, occasionnel). Filtres : `?segment=loyal`, `?search=nom ou téléphone`."""

    queryset = with_paid_total(Customer.objects.filter(is_active=True)).order_by("name", "id")
    serializer_class = CustomerSerializer

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        if search := self.request.query_params.get("search"):
            queryset = queryset.filter(Q(name__icontains=search) | Q(phone__icontains=search))
        return queryset

    def list(self, request, *args, **kwargs):
        customers = enrich(self.filter_queryset(self.get_queryset()))
        segment = request.query_params.get("segment")
        if segment:
            if segment not in Segment.values:
                raise ValidationError(
                    {
                        "segment": _("Valeurs possibles : {values}.").format(
                            values=", ".join(Segment.values)
                        )
                    }
                )
            customers = [c for c in customers if c.segment == segment]
        return Response(self.get_serializer(customers, many=True).data)

    def get_object(self):
        customer = super().get_object()
        return enrich([customer])[0]

    def reload(self, serializer):
        super().reload(serializer)
        serializer.instance = enrich([serializer.instance])[0]

    def perform_destroy(self, instance):
        if instance.balance != 0:
            raise ValidationError({"detail": _("Ce client a encore une dette ou une avance.")})
        super().perform_destroy(instance)


class PaymentViewSet(
    SoftDeleteMixin,
    SellerMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Paiements reçus des clients. Un paiement ne se modifie pas ; DELETE l'annule.
    Un paiement supérieur à la dette est accepté : c'est une avance. Filtre : `?customer=`."""

    queryset = Payment.objects.filter(is_active=True).select_related("customer")
    serializer_class = PaymentSerializer
    filterset_fields = ["customer", "method"]

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user, created_by=self.request.user)


class PlatformSettingsPermission(IsAuthenticated):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return super().has_permission(request, view)
        return IsDirection().has_permission(request, view)


class PlatformSettingsView(generics.RetrieveUpdateAPIView):
    """Réglages du classement des clients : lecture pour tout compte, modification par la
    Direction (sans toucher au code)."""

    serializer_class = PlatformSettingsSerializer
    permission_classes = [PlatformSettingsPermission]
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return PlatformSettings.load()
