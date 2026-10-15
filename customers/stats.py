"""Valeurs calculées d'un client : commandes, total acheté, payé, dette, segment."""

from decimal import Decimal

from django.db.models import F, OuterRef, Subquery, Sum
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


def with_balance(customers):
    """Ajoute `delivered_total`, `paid_total` et `balance` (dette) par sous-requêtes :
    pour additionner les dettes de beaucoup de clients sans les charger un par un."""
    from orders.models import Order, OrderStatus

    delivered = (
        Order.objects.filter(customer=OuterRef("pk"), is_active=True, status=OrderStatus.DELIVERED)
        .order_by()
        .values("customer")
        .annotate(total=Sum("total_amount"))
        .values("total")
    )
    return (
        with_paid_total(customers)
        .annotate(delivered_total=Coalesce(Subquery(delivered), ZERO))
        .annotate(balance=F("delivered_total") - F("paid_total"))
    )


def order_stats(customer_ids):
    """Statistiques de commandes par client.

    - Dates : toutes les commandes **non annulées** (pour le classement).
    - Total acheté : commandes **livrées** seulement (Q8), comme la dette.
    """
    from orders.models import Order, OrderStatus

    stats = {pk: CustomerStats() for pk in customer_ids}
    rows = (
        Order.objects.filter(customer_id__in=customer_ids, is_active=True)
        .exclude(status=OrderStatus.CANCELLED)
        .values_list("customer_id", "order_date", "status", "total_amount")
    )
    for customer_id, order_date, status, total in rows:
        stats[customer_id].order_dates.append(order_date)
        if status == OrderStatus.DELIVERED:
            stats[customer_id].total_purchased += total
    return stats


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
