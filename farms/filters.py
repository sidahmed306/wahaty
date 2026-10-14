import django_filters

from .models import Farm, Harvest, PalmGroup


class FarmFilter(django_filters.FilterSet):
    oasis = django_filters.CharFilter(field_name="oasis__slug")
    region = django_filters.CharFilter(field_name="oasis__region__slug")

    class Meta:
        model = Farm
        fields = ["owner", "oasis", "region"]


class PalmGroupFilter(django_filters.FilterSet):
    class Meta:
        model = PalmGroup
        fields = ["farm", "variety"]


class HarvestFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="harvest_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="harvest_date", lookup_expr="lte")

    class Meta:
        model = Harvest
        fields = ["farm", "variety", "season", "date_from", "date_to"]
