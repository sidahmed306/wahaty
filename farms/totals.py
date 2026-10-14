"""Calcul des totaux : palmiers par variété et production par saison."""

from collections import OrderedDict

from django.db.models import Count, Sum

from oases.models import DateVariety


def _varieties(ids):
    return DateVariety.objects.in_bulk(ids)


def palm_totals(palm_groups):
    """Palmiers par variété + total général, à partir d'un ensemble de lignes PalmGroup."""
    rows = (
        palm_groups.filter(is_active=True)
        .values("variety")
        .annotate(productive=Sum("productive_count"), young=Sum("young_count"))
        .order_by("variety__name_fr")
    )
    varieties = _varieties([r["variety"] for r in rows])
    by_variety = [
        {
            "variety": varieties[r["variety"]],
            "productive": r["productive"],
            "young": r["young"],
            "total": r["productive"] + r["young"],
        }
        for r in rows
    ]
    productive = sum(r["productive"] for r in by_variety)
    young = sum(r["young"] for r in by_variety)
    return by_variety, {"productive": productive, "young": young, "total": productive + young}


def production_totals(harvests):
    """Production (kg) par saison et variété, et par saison seule."""
    rows = (
        harvests.filter(is_active=True)
        .values("season", "variety")
        .annotate(total_kg=Sum("quantity_kg"), harvests_count=Count("id"))
        .order_by("-season", "variety__name_fr")
    )
    varieties = _varieties([r["variety"] for r in rows])
    lines = [{**r, "variety": varieties[r["variety"]]} for r in rows]
    seasons = OrderedDict()
    for line in lines:
        seasons[line["season"]] = seasons.get(line["season"], 0) + line["total_kg"]
    by_season = [{"season": s, "total_kg": kg} for s, kg in seasons.items()]
    return lines, by_season
