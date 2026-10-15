"""Valeurs calculées d'un client : commandes, total acheté, payé, dette, segment."""

from decimal import Decimal

from django.db.models import OuterRef, Subquery, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.models import PlatformSettings

from .models import Payment
from .segments import CustomerStats, classify

ZERO = Decimal("0.00")


def with_paid_total(customers):
    """Ajoute `paid_total` (somme des paiements actifs) par sous-requête."""
    paid = (
        Payment.objects.filter(customer=OuterRef("pk"), is_active=True)
        .order_by()
        .values("customer")
        .annotate(total=Sum("amount"))
        .values("total")
    )
    return customers.annotate(paid_total=Coalesce(Subquery(paid), ZERO))


def order_stats(customer_ids):
    """Statistiques de commandes par client (commandes non annulées).

    Les commandes arrivent à T10 : en attendant, aucun client n'a de commande.
    """
    return {pk: CustomerStats() for pk in customer_ids}


def enrich(customers, today=None):
    """Ajoute à chaque client (annoté par `with_paid_total`) ses chiffres et son segment."""
    customers = list(customers)
    today = today or timezone.localdate()
    settings = PlatformSettings.load()
    stats = order_stats([c.pk for c in customers])
    for customer in customers:
        s = stats[customer.pk]
        customer.orders_count = len(s.order_dates)
        customer.first_order_date = s.first_order
        customer.last_order_date = s.last_order
        customer.total_purchased = s.total_purchased
        customer.balance = s.total_purchased - customer.paid_total
        customer.segment = classify(s, settings, today)
    return customers
