"""Rappels quotidiens (commande `python manage.py send_order_reminders`).

Crée des notifications dans la plateforme — sans doublon si on relance le même jour :
- commandes à livrer demain ;
- commandes en retard (date prévue dépassée, ni livrée ni annulée) ;
- produits en stock bas.
"""

from datetime import timedelta

from django.db.models import F

from inventory.models import Product
from inventory.services import with_stock

from .models import CLOSED_STATUSES, Notification, Order


def _notify(day, **fields):
    lookup = {k: fields.pop(k) for k in ("kind", "order", "product") if k in fields}
    _, created = Notification.objects.get_or_create(day=day, **lookup, defaults=fields)
    return created


def generate_reminders(today):
    counts = {"delivery_due": 0, "order_late": 0, "low_stock": 0}
    open_orders = (
        Order.objects.filter(is_active=True)
        .exclude(status__in=CLOSED_STATUSES)
        .select_related("customer", "owner")
    )

    for order in open_orders.filter(expected_delivery_date=today + timedelta(days=1)):
        counts["delivery_due"] += _notify(
            today,
            kind=Notification.Kind.DELIVERY_DUE,
            order=order,
            user=order.owner,
            message_fr=(
                f"La commande {order.number} pour {order.customer} doit être livrée demain "
                f"({order.expected_delivery_date:%d/%m/%Y})."
            ),
            message_ar=(
                f"الطلب {order.number} للزبون {order.customer} يجب تسليمه غدًا "
                f"({order.expected_delivery_date:%d/%m/%Y})."
            ),
        )

    for order in open_orders.filter(expected_delivery_date__lt=today):
        days = (today - order.expected_delivery_date).days
        counts["order_late"] += _notify(
            today,
            kind=Notification.Kind.ORDER_LATE,
            order=order,
            user=order.owner,
            message_fr=(
                f"La commande {order.number} pour {order.customer} est en retard de {days} jour(s)."
            ),
            message_ar=f"الطلب {order.number} للزبون {order.customer} متأخر بـ {days} يوم.",
        )

    low = with_stock(Product.objects.filter(is_active=True, low_stock_threshold__isnull=False))
    for product in low.filter(stock__lte=F("low_stock_threshold")).select_related("owner"):
        counts["low_stock"] += _notify(
            today,
            kind=Notification.Kind.LOW_STOCK,
            product=product,
            user=product.owner,
            message_fr=f"Stock bas : {product.name} ({product.stock} restant(s)).",
            message_ar=f"مخزون منخفض: {product.name} (المتبقي {product.stock}).",
        )
    return counts
