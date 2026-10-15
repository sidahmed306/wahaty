from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from orders.reminders import generate_reminders


class Command(BaseCommand):
    help = "Crée les notifications du jour : livraisons de demain, retards, stocks bas."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=date.fromisoformat,
            help="Jour à traiter (AAAA-MM-JJ). Défaut : aujourd'hui.",
        )

    def handle(self, *args, **options):
        today = options["date"] or timezone.localdate()
        counts = generate_reminders(today)
        self.stdout.write(
            self.style.SUCCESS(
                f"{today} : {counts['delivery_due']} livraison(s) demain, "
                f"{counts['order_late']} retard(s), {counts['low_stock']} stock(s) bas."
            )
        )
