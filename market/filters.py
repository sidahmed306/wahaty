import django_filters
from django.db.models import Q

from .models import Listing


class ListingFilter(django_filters.FilterSet):
    variety = django_filters.CharFilter(field_name="variety__slug", help_text="ex. amhat")
    oasis = django_filters.CharFilter(field_name="oasis__slug")
    region = django_filters.CharFilter(field_name="oasis__region__slug", help_text="ex. atar")
    min_price = django_filters.NumberFilter(field_name="price_per_kg", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price_per_kg", lookup_expr="lte")
    min_quantity = django_filters.NumberFilter(field_name="quantity_kg", lookup_expr="gte")
    search = django_filters.CharFilter(method="filter_search", help_text="titre ou description")

    class Meta:
        model = Listing
        fields = [
            "variety",
            "oasis",
            "region",
            "min_price",
            "max_price",
            "min_quantity",
            "search",
        ]

    def filter_search(self, queryset, name, value):
        return queryset.filter(Q(title__icontains=value) | Q(description__icontains=value))
