import django_filters
from django.db.models import Q
from django.utils import timezone

from .models import CLOSED_STATUSES, Order


class OrderFilter(django_filters.FilterSet):
    late = django_filters.BooleanFilter(
        method="filter_late", help_text="true : commandes en retard"
    )
    date_from = django_filters.DateFilter(field_name="order_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="order_date", lookup_expr="lte")
    expected_from = django_filters.DateFilter(
        field_name="expected_delivery_date", lookup_expr="gte"
    )
    expected_to = django_filters.DateFilter(field_name="expected_delivery_date", lookup_expr="lte")

    class Meta:
        model = Order
        fields = [
            "status",
            "customer",
            "late",
            "date_from",
            "date_to",
            "expected_from",
            "expected_to",
        ]

    def filter_late(self, queryset, name, value):
        late = Q(expected_delivery_date__lt=timezone.localdate()) & ~Q(status__in=CLOSED_STATUSES)
        return queryset.filter(late) if value else queryset.exclude(late)
