"""Factures : numérotation séquentielle **sans trou** par vendeur et par année.

Le compteur (InvoiceSequence) est verrouillé (SELECT … FOR UPDATE) pendant la création :
deux factures simultanées ne peuvent pas avoir le même numéro. Si la création échoue,
la transaction annule aussi l'incrément du compteur : aucun numéro n'est perdu.
"""

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from orders.models import Order, OrderStatus

from .models import Invoice, InvoiceSequence

INVOICEABLE = (
    OrderStatus.CONFIRMED,
    OrderStatus.PREPARED,
    OrderStatus.OUT_FOR_DELIVERY,
    OrderStatus.DELIVERED,
)


class InvoiceError(Exception):
    pass


def _money(value):
    return f"{value:.2f}"


def _seller_snapshot(user):
    profile = user.profile
    return {
        "name": profile.business_name or user.full_name,
        "phone": user.phone,
        "whatsapp": profile.whatsapp,
        "address": profile.address,
    }


def _customer_snapshot(order):
    customer = order.customer
    return {
        "name": customer.name,
        "phone": customer.phone,
        "address": order.delivery_address or customer.address,
        "city": customer.city,
    }


def _lines_snapshot(order):
    return [
        {
            "product": item.product.name,
            "unit": item.product.get_unit_display(),
            "quantity": _money(item.quantity),
            "unit_price": _money(item.unit_price),
            "line_total": _money(item.line_total),
        }
        for item in order.items.select_related("product")
    ]


def next_number(owner, year):
    sequence, _created = InvoiceSequence.objects.get_or_create(owner=owner, year=year)
    sequence = InvoiceSequence.objects.select_for_update().get(pk=sequence.pk)
    sequence.last_number += 1
    sequence.save(update_fields=["last_number"])
    return sequence.last_number


@transaction.atomic
def create_invoice(order, user, issue_date=None):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status not in INVOICEABLE:
        raise InvoiceError(_("On ne facture qu'une commande confirmée (ou plus avancée)."))
    if order.invoices.filter(status=Invoice.Status.ISSUED).exists():
        raise InvoiceError(_("Cette commande a déjà une facture valide."))
    issue_date = issue_date or timezone.localdate()
    sequence = next_number(order.owner, issue_date.year)
    return Invoice.objects.create(
        owner=order.owner,
        order=order,
        number=f"FAC-{issue_date.year}-{sequence:04d}",
        year=issue_date.year,
        sequence=sequence,
        issue_date=issue_date,
        seller_snapshot=_seller_snapshot(order.owner),
        customer_snapshot=_customer_snapshot(order),
        lines_snapshot=_lines_snapshot(order),
        subtotal=order.subtotal,
        delivery_fee=order.delivery_fee,
        discount=order.discount,
        total_amount=order.total_amount,
        created_by=user,
    )


@transaction.atomic
def cancel_invoice(invoice, reason):
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.status == Invoice.Status.CANCELLED:
        raise InvoiceError(_("Cette facture est déjà annulée."))
    if not reason.strip():
        raise InvoiceError(_("Indiquez le motif de l'annulation."))
    invoice.status = Invoice.Status.CANCELLED
    invoice.cancelled_at = timezone.now()
    invoice.cancel_reason = reason
    invoice.save(update_fields=["status", "cancelled_at", "cancel_reason", "updated_at"])
    return invoice


def cancel_invoices_of_order(order):
    """Appelé quand une commande est annulée : sa facture valide est annulée aussi."""
    for invoice in order.invoices.filter(status=Invoice.Status.ISSUED):
        cancel_invoice(invoice, f"Commande {order.number} annulée")
