from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from core.mixins import SellerMixin, SoftDeleteMixin

from . import services
from .filters import ProductFilter, PurchaseFilter, StockMovementFilter, SupplierPaymentFilter
from .models import Product, Purchase, StockMovement, Supplier, SupplierPayment
from .serializers import (
    CancelPurchaseSerializer,
    ProductSerializer,
    PurchaseSerializer,
    StockMovementSerializer,
    SupplierPaymentSerializer,
    SupplierSerializer,
)


def stock_error(exc):
    return ValidationError({"detail": str(exc)})


class SupplierViewSet(
    SoftDeleteMixin,
    SellerMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Fournisseurs, avec achats, payé et **reste à payer** (calculés)."""

    queryset = services.with_balance(Supplier.objects.filter(is_active=True)).order_by("name")
    serializer_class = SupplierSerializer

    def perform_destroy(self, instance):
        if services.supplier_balance(instance) != 0:
            raise ValidationError({"detail": "Ce fournisseur a encore un reste à payer."})
        super().perform_destroy(instance)


class ProductViewSet(
    SoftDeleteMixin,
    SellerMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Produits avec leur **stock** (somme des mouvements). Filtre : `?low_stock=true`."""

    queryset = services.with_stock(Product.objects.filter(is_active=True)).order_by("name")
    serializer_class = ProductSerializer
    filterset_class = ProductFilter

    def check_unique_name(self, owner, name, exclude_pk=None):
        same = Product.objects.filter(owner=owner, name__iexact=name, is_active=True)
        if same.exclude(pk=exclude_pk).exists():
            raise ValidationError({"name": "Vous avez déjà un produit avec ce nom."})

    def perform_create(self, serializer):
        self.check_unique_name(self.request.user, serializer.validated_data["name"])
        super().perform_create(serializer)

    def perform_update(self, serializer):
        if "name" in serializer.validated_data:
            self.check_unique_name(
                serializer.instance.owner, serializer.validated_data["name"], serializer.instance.pk
            )
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        if services.current_stock(instance) != 0:
            raise ValidationError({"detail": "Videz d'abord le stock de ce produit."})
        super().perform_destroy(instance)


class StockMovementViewSet(
    SellerMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Historique du stock. Création : corrections et pertes seulement (justification
    obligatoire). Un mouvement n'est jamais modifié ni supprimé."""

    queryset = StockMovement.objects.select_related("product")
    serializer_class = StockMovementSerializer
    filterset_class = StockMovementFilter
    owner_field = "product__owner"

    def perform_create(self, serializer):
        data = serializer.validated_data
        try:
            serializer.instance = services.record_movement(
                data["product"],
                data["kind"],
                data["quantity"],
                self.request.user,
                note=data["note"],
            )
        except services.StockError as exc:
            raise stock_error(exc) from exc


class PurchaseViewSet(
    SellerMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Achats chez un fournisseur (avec leurs lignes). Un achat ne se modifie pas :
    en cas d'erreur, on l'**annule** (`POST /purchases/{id}/cancel/`)."""

    queryset = Purchase.objects.filter(is_active=True).select_related("supplier")
    serializer_class = PurchaseSerializer
    filterset_class = PurchaseFilter

    def perform_create(self, serializer):
        data = serializer.validated_data
        serializer.instance = services.create_purchase(
            owner=self.request.user,
            supplier=data["supplier"],
            purchase_date=data["purchase_date"],
            reference=data.get("reference", ""),
            lines=data["lines"],
            user=self.request.user,
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Annuler un achat : le stock et le reste à payer sont corrigés automatiquement."""
        purchase = self.get_object()
        body = CancelPurchaseSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            purchase = services.cancel_purchase(
                purchase, body.validated_data["reason"], request.user
            )
        except services.StockError as exc:
            raise stock_error(exc) from exc
        return Response(self.get_serializer(purchase).data)


class SupplierPaymentViewSet(
    SoftDeleteMixin,
    SellerMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Paiements aux fournisseurs. Impossible de payer plus que le reste à payer.
    Un paiement ne se modifie pas ; DELETE l'annule (il ne compte plus)."""

    queryset = SupplierPayment.objects.filter(is_active=True).select_related("supplier")
    serializer_class = SupplierPaymentSerializer
    filterset_class = SupplierPaymentFilter

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        try:
            serializer.instance = services.record_supplier_payment(
                owner=self.request.user,
                supplier=data.pop("supplier"),
                amount=data.pop("amount"),
                user=self.request.user,
                **data,
            )
        except services.StockError as exc:
            raise stock_error(exc) from exc
