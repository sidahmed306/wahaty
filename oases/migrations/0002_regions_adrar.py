"""Régions de départ : les 4 moughataas de la wilaya de l'Adrar.

La Direction peut en ajouter d'autres ensuite (administration ou API), sans changer le code.
"""

from django.db import migrations

REGIONS_ADRAR = [
    # (slug, nom arabe, nom français, ordre)
    ("atar", "أطار", "Atar", 1),
    ("chinguetti", "شنقيط", "Chinguetti", 2),
    ("ouadane", "وادان", "Ouadane", 3),
    ("aoujeft", "أوجفت", "Aoujeft", 4),
]


def create_regions(apps, schema_editor):
    Region = apps.get_model("oases", "Region")
    for slug, name_ar, name_fr, order in REGIONS_ADRAR:
        Region.objects.get_or_create(
            slug=slug, defaults={"name_ar": name_ar, "name_fr": name_fr, "order": order}
        )


def remove_regions(apps, schema_editor):
    Region = apps.get_model("oases", "Region")
    Region.objects.filter(slug__in=[r[0] for r in REGIONS_ADRAR], oases__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("oases", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_regions, remove_regions),
    ]
