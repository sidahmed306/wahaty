import django_filters
from django.db.models import F, Q

from .models import DateVariety, Oasis


def search_names(queryset, name, value):
    return queryset.filter(Q(name_ar__icontains=value) | Q(name_fr__icontains=value))


class OasisFilter(django_filters.FilterSet):
    region = django_filters.CharFilter(field_name="region__slug", help_text="ex. atar")
    variety = django_filters.CharFilter(
        field_name="varieties__slug", distinct=True, help_text="ex. amhat"
    )
    search = django_filters.CharFilter(method=search_names, help_text="nom en arabe ou français")

    class Meta:
        model = Oasis
        fields = ["region", "variety", "search"]


class DateVarietyFilter(django_filters.FilterSet):
    oasis = django_filters.CharFilter(field_name="oases__slug", distinct=True)
    texture = django_filters.ChoiceFilter(choices=DateVariety.Texture.choices)
    in_season = django_filters.NumberFilter(
        method="filter_in_season", help_text="numéro du mois (1–12) : variétés mûres ce mois-là"
    )
    search = django_filters.CharFilter(method=search_names)

    class Meta:
        model = DateVariety
        fields = ["oasis", "texture", "in_season", "search"]

    def filter_in_season(self, queryset, name, value):
        month = int(value)
        # Saison dans la même année (ex. juin → août)
        same_year = Q(ripening_start_month__lte=F("ripening_end_month")) & Q(
            ripening_start_month__lte=month, ripening_end_month__gte=month
        )
        # Saison à cheval sur deux années (ex. novembre → février)
        across_year = Q(ripening_start_month__gt=F("ripening_end_month")) & (
            Q(ripening_start_month__lte=month) | Q(ripening_end_month__gte=month)
        )
        return queryset.filter(same_year | across_year)
