"""Données de démonstration : variétés du flyer + une oasis par région de l'Adrar.

    python manage.py seed_demo

Relançable sans doublon. Aucun compte n'est créé ici : le compte Direction se crée avec
« python manage.py createsuperuser » (mot de passe choisi par la Direction, jamais dans Git).
Les positions GPS sont approximatives (centre de la ville) et se corrigent dans l'administration.
"""

from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from oases.models import DateVariety, Oasis, Region

DATES = ["salmedina", "hmar", "sekani", "bjeira", "sembekhra", "anzar-kizkar"]

OASES = [
    {
        "region": "atar",
        "name_ar": "واحة أطار",
        "name_fr": "Oasis d'Atar",
        "gps": ("20.5170", "-13.0500"),
        "description_ar": "عاصمة آدرار، تحيط بها بساتين النخيل على ضفاف الوادي.",
        "description_fr": "Capitale de l'Adrar, entourée de palmeraies le long de l'oued.",
    },
    {
        "region": "chinguetti",
        "name_ar": "واحة شنقيط",
        "name_fr": "Oasis de Chinguetti",
        "gps": ("20.4630", "-12.3640"),
        "description_ar": "مدينة تاريخية ومكتباتها العريقة، ونخيلها من أشهر نخيل آدرار.",
        "description_fr": (
            "Ville historique aux bibliothèques anciennes ; sa palmeraie est l'une des plus "
            "célèbres de l'Adrar."
        ),
    },
    {
        "region": "ouadane",
        "name_ar": "واحة وادان",
        "name_fr": "Oasis de Ouadane",
        "gps": ("20.9280", "-11.6230"),
        "description_ar": "مدينة قديمة على حافة الصحراء، تحرسها بساتين النخيل.",
        "description_fr": "Cité ancienne au bord du désert, gardée par ses palmeraies.",
    },
    {
        "region": "aoujeft",
        "name_ar": "واحة أوجفت",
        "name_fr": "Oasis d'Aoujeft",
        "gps": ("20.0330", "-13.0500"),
        "description_ar": "واحات أوجفت ونخيلها في جنوب آدرار.",
        "description_fr": "Les palmeraies d'Aoujeft, au sud de l'Adrar.",
    },
]


class Command(BaseCommand):
    help = "Crée les données de démonstration TRC (variétés, oasis de l'Adrar)."

    @transaction.atomic
    def handle(self, *args, **options):
        call_command("seed_varieties", stdout=self.stdout)
        varieties = list(DateVariety.objects.filter(slug__in=DATES))
        for data in OASES:
            region = Region.objects.get(slug=data["region"])
            latitude, longitude = (Decimal(v) for v in data["gps"])
            oasis, created = Oasis.objects.get_or_create(
                region=region,
                name_fr=data["name_fr"],
                defaults={
                    "name_ar": data["name_ar"],
                    "description_ar": data["description_ar"],
                    "description_fr": data["description_fr"],
                    "latitude": latitude,
                    "longitude": longitude,
                },
            )
            if created:
                oasis.varieties.set(varieties)
            self.stdout.write(f"{'+' if created else '='} {data['name_fr']}")
        self.stdout.write(self.style.SUCCESS("Démonstration prête."))
