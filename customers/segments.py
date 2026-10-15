"""Classement automatique des clients (règles validées à T02, seuils dans PlatformSettings).

Ordre de priorité :
1. Inactif     : a déjà commandé, mais aucune commande depuis `inactive_days` jours (≥).
2. Premium     : fidèle ET total acheté ≥ `premium_threshold`.
3. Fidèle      : au moins `loyal_min_orders` commandes sur les `loyal_period_days` derniers jours.
4. Nouveau     : aucune commande encore, ou première commande il y a moins de
                 `new_customer_days` jours.
5. Occasionnel : tous les autres.

Les commandes annulées ne comptent jamais (elles sont exclues avant d'arriver ici).
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.db import models


class Segment(models.TextChoices):
    INACTIVE = "inactive", "Inactif"
    PREMIUM = "premium", "Premium"
    LOYAL = "loyal", "Fidèle"
    NEW = "new", "Nouveau"
    OCCASIONAL = "occasional", "Occasionnel"


@dataclass
class CustomerStats:
    """Chiffres d'un client, calculés à partir de ses commandes non annulées."""

    order_dates: list[date] = field(default_factory=list)
    total_purchased: Decimal = Decimal("0.00")

    @property
    def first_order(self):
        return min(self.order_dates, default=None)

    @property
    def last_order(self):
        return max(self.order_dates, default=None)


def classify(stats, settings, today):
    if not stats.order_dates:
        return Segment.NEW
    if (today - stats.last_order).days >= settings.inactive_days:
        return Segment.INACTIVE
    recent = sum(1 for d in stats.order_dates if (today - d).days <= settings.loyal_period_days)
    loyal = recent >= settings.loyal_min_orders
    if loyal and stats.total_purchased >= settings.premium_threshold:
        return Segment.PREMIUM
    if loyal:
        return Segment.LOYAL
    if (today - stats.first_order).days < settings.new_customer_days:
        return Segment.NEW
    return Segment.OCCASIONAL
