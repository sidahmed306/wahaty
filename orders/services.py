"""Commandes : création, modification, changement de statut — toujours dans une transaction.

- Numéro unique et sans trou par vendeur (CMD-0001, CMD-0002…).
- Totaux calculés par le serveur : sous-total = Σ lignes ; total = sous-total + livraison − remise.
- Confirmation : on vérifie que le stock suffit (sans le retirer).
- Livraison : le stock est retiré (un mouvement « sale » par produit) ; s'il manque, rien
  n'est enregistré et la commande garde son statut.
"""

from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from accounts.models import User
from core.money import round_money
from inventory import services as stock
from inventory.models import StockMovement
from invoices.services import cancel_invoices_of_order

from .models import TRANSITIONS, Order, OrderItem, OrderStatus, OrderStatusHistory

ZERO = Decimal("0.00")
EDITABLE_ONLY_WHEN_RECEIVED = ("items", "customer", "delivery_fee", "discount")


class OrderError(Exception):
    pass


def _set_items(order, items):
    order.items.all().delete()
    OrderItem.objects.bulk_create(
        OrderItem(
            order=order,
            product=item["product"],
            quantity=item["quantity"],
            unit_price=item["unit_price"],
            line_total=round_money(item["quantity"] * item["unit_price"]),
        )
        for item in items
    )


def _recompute_totals(order, items=None):
    """Totaux à partir des lignes en base, ou des lignes `items` pas encore enregistrées."""
    if items is None:
        order.subtotal = sum((i.line_total for i in order.items.all()), ZERO)
    else:
        order.subtotal = sum((round_money(i["quantity"] * i["unit_price"]) for i in items), ZERO)
    total = order.subtotal + order.delivery_fee - order.discount
    if total < 0:
        raise OrderError(_("La remise est plus grande que le montant de la commande."))
    order.total_amount = total


def _history(order, from_status, to_status, user, note=""):
    OrderStatusHistory.objects.create(
        order=order, from_status=from_status, to_status=to_status, changed_by=user, note=note
    )


@transaction.atomic
def create_order(owner, customer, items, user, **fields):
    # Verrou sur le vendeur : deux commandes simultanées n'auront pas le même numéro.
    User.objects.select_for_update().get(pk=owner.pk)
    number = f"CMD-{Order.objects.filter(owner=owner).count() + 1:04d}"
    order = Order(owner=owner, customer=customer, number=number, created_by=user, **fields)
    # Totaux calculés avant d'enregistrer : une seule écriture (et une seule ligne au journal).
    _recompute_totals(order, items)
    order.save()
    _set_items(order, items)
    _history(order, "", OrderStatus.RECEIVED, user)
    return order


@transaction.atomic
def update_order(order, user, items=None, **fields):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status in (OrderStatus.DELIVERED, OrderStatus.CANCELLED):
        raise OrderError(_("Une commande livrée ou annulée ne se modifie plus."))
    touched = set(fields) | ({"items"} if items is not None else set())
    if order.status != OrderStatus.RECEIVED and touched & set(EDITABLE_ONLY_WHEN_RECEIVED):
        raise OrderError(
            _(
                "Les lignes, le client, les frais et la remise ne se modifient "
                "qu'en statut « Reçue »."
            )
        )
    for name, value in fields.items():
        setattr(order, name, value)
    if items is not None:
        _set_items(order, items)
    _recompute_totals(order)
    order.save()
    return order


def required_quantities(order):
    needed = defaultdict(lambda: ZERO)
    products = {}
    for item in order.items.select_related("product"):
        needed[item.product_id] += item.quantity
        products[item.product_id] = item.product
    return [(products[pk], qty) for pk, qty in needed.items()]


@transaction.atomic
def change_status(order, new_status, user, note="", cancel_reason=""):
    order = Order.objects.select_for_update().get(pk=order.pk)
    old_status = order.status
    if new_status not in TRANSITIONS[OrderStatus(old_status)]:
        raise OrderError(
            _("Passage interdit : « {old} » → « {new} ».").format(
                old=OrderStatus(old_status).label, new=OrderStatus(new_status).label
            )
        )

    if new_status == OrderStatus.CONFIRMED:
        for product, quantity in required_quantities(order):
            available = stock.current_stock(product)
            if quantity > available:
                raise OrderError(
                    _(
                        "Stock insuffisant pour « {product} » : "
                        "{available} disponible(s), {quantity} commandé(s)."
                    ).format(product=product.name, available=available, quantity=quantity)
                )

    if new_status == OrderStatus.DELIVERED:
        for product, quantity in required_quantities(order):
            try:
                stock.record_movement(
                    product,
                    StockMovement.Kind.SALE,
                    quantity,
                    user,
                    order=order,
                    note=f"Livraison de la commande {order.number}",
                )
            except stock.StockError as exc:
                raise OrderError(str(exc)) from exc
        order.delivered_at = timezone.now()

    if new_status == OrderStatus.CANCELLED:
        if not cancel_reason.strip():
            raise OrderError(_("Indiquez le motif de l'annulation."))
        order.cancel_reason = cancel_reason
        cancel_invoices_of_order(order)

    order.status = new_status
    order.save()
    _history(order, old_status, new_status, user, note)
    return order
