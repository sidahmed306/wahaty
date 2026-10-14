import django_filters
from django.db.models import F

from .models import Product, Purchase, StockMovement, SupplierPayment


class ProductFilter(django_filters.FilterSet):
    low_stock = django_filters.BooleanFilter(
        method="filter_low_stock", help_text="true : produits sous le seuil d'alerte"
    )

    class Meta:
        model = Product
        fields = ["variety", "unit", "low_stock"]

    def filter_low_stock(self, queryset, name, value):
        low = queryset.filter(
            low_stock_threshold__isnull=False, stock__lte=F("low_stock_threshold")
        )
        return low if value else queryset.exclude(pk__in=low.values("pk"))


class PurchaseFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="purchase_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="purchase_date", lookup_expr="lte")
    cancelled = django_filters.BooleanFilter(
        field_name="cancelled_at", lookup_expr="isnull", exclude=True
    )

    class Meta:
        model = Purchase
        fields = ["supplier", "date_from", "date_to", "cancelled"]


class StockMovementFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="movement_date", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="movement_date", lookup_expr="date__lte")

    class Meta:
        model = StockMovement
        fields = ["product", "kind", "purchase", "date_from", "date_to"]


class SupplierPaymentFilter(django_filters.FilterSet):
    class Meta:
        model = SupplierPayment
        fields = ["supplier", "purchase", "method"]
