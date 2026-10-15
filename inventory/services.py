"""Opérations de stock et d'argent, toujours dans une transaction.

- Stock = somme des entrées − somme des sorties (jamais un chiffre modifié à la main).
- Une sortie qui rendrait le stock négatif est refusée. Le produit est verrouillé
  (SELECT … FOR UPDATE) pendant le contrôle : deux sorties simultanées ne passent pas toutes
  les deux.
- Reste à payer d'un fournisseur = achats (non annulés) − paiements ; jamais négatif.
- En cas d'erreur, la transaction est annulée : rien n'est enregistré à moitié.
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Case, DecimalField, F, OuterRef, Subquery, Sum, When
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.translation import gettext as _

from core.money import round_money

from .models import Product, Purchase, StockMovement, Supplier, SupplierPayment

ZERO = Decimal("0.00")
AMOUNT = DecimalField(max_digits=16, decimal_places=2)


class StockError(Exception):
    """Opération refusée (stock insuffisant, achat déjà annulé, trop payé…)."""


# --- Calculs ---------------------------------------------------------------------


def signed_quantity():
    return Case(
        When(kind__in=StockMovement.IN_KINDS, then=F("quantity")),
        default=-F("quantity"),
        output_field=AMOUNT,
    )


def _sum_subquery(queryset, outer_field, expression):
    rows = (
        queryset.filter(**{outer_field: OuterRef("pk")})
        .order_by()
        .values(outer_field)
        .annotate(total=Sum(expression))
        .values("total")
    )
    return Coalesce(Subquery(rows, output_field=AMOUNT), ZERO, output_field=AMOUNT)


def with_stock(products):
    """Ajoute `stock` à chaque produit (sous-requête : pas de double comptage)."""
    return products.annotate(
        stock=_sum_subquery(StockMovement.objects.all(), "product", signed_quantity())
    )


def with_balance(suppliers):
    """Ajoute `purchases_total`, `paid_total` et `balance` (reste à payer)."""
    purchases = Purchase.objects.filter(is_active=True, cancelled_at__isnull=True)
    payments = SupplierPayment.objects.filter(is_active=True)
    return suppliers.annotate(
        purchases_total=_sum_subquery(purchases, "supplier", F("total_amount")),
        paid_total=_sum_subquery(payments, "supplier", F("amount")),
    ).annotate(balance=F("purchases_total") - F("paid_total"))


def current_stock(product):
    return with_stock(Product.objects.filter(pk=product.pk)).get().stock


def supplier_balance(supplier):
    return with_balance(Supplier.objects.filter(pk=supplier.pk)).get().balance


# --- Mouvements ------------------------------------------------------------------


@transaction.atomic
def record_movement(product, kind, quantity, user, **extra):
    """Enregistre un mouvement ; refuse toute sortie supérieure au stock disponible."""
    product = Product.objects.select_for_update().get(pk=product.pk)
    if kind in StockMovement.OUT_KINDS:
        available = current_stock(product)
        if quantity > available:
            raise StockError(
                _(
                    "Stock insuffisant pour « {product} » : "
                    "{available} disponible(s), {quantity} demandé(s)."
                ).format(product=product.name, available=available, quantity=quantity)
            )
    return StockMovement.objects.create(
        product=product, kind=kind, quantity=quantity, created_by=user, **extra
    )


@transaction.atomic
def create_purchase(owner, supplier, purchase_date, lines, user, reference=""):
    """Crée l'achat et ses lignes d'entrée en stock, tout ou rien."""
    total = sum((round_money(line["quantity"] * line["unit_cost"]) for line in lines), ZERO)
    purchase = Purchase.objects.create(
        owner=owner,
        supplier=supplier,
        purchase_date=purchase_date,
        reference=reference,
        total_amount=total,
        created_by=user,
    )
    for line in lines:
        record_movement(
            line["product"],
            StockMovement.Kind.PURCHASE,
            line["quantity"],
            user,
            unit_cost=line["unit_cost"],
            purchase=purchase,
        )
    return purchase


@transaction.atomic
def cancel_purchase(purchase, reason, user):
    """Annule un achat : sortie de stock de chaque ligne ; refusé si la marchandise
    est déjà partie ou si l'achat a déjà été payé au-delà de ce qui resterait dû."""
    purchase = Purchase.objects.select_for_update().get(pk=purchase.pk)
    if purchase.is_cancelled:
        raise StockError(_("Cet achat est déjà annulé."))
    Supplier.objects.select_for_update().get(pk=purchase.supplier_id)
    if supplier_balance(purchase.supplier) < purchase.total_amount:
        raise StockError(
            _(
                "Annulation impossible : cet achat est déjà (en partie) payé. "
                "Le reste à payer deviendrait négatif."
            )
        )
    for line in purchase.lines.select_related("product"):
        record_movement(
            line.product,
            StockMovement.Kind.ADJUST_OUT,
            line.quantity,
            user,
            note=f"Annulation de l'achat n° {purchase.pk}",
        )
    purchase.cancelled_at = timezone.now()
    purchase.cancel_reason = reason
    purchase.save(update_fields=["cancelled_at", "cancel_reason", "updated_at"])
    return purchase


@transaction.atomic
def record_supplier_payment(owner, supplier, amount, user, **fields):
    """Enregistre un paiement ; refuse de payer plus que le reste à payer."""
    supplier = Supplier.objects.select_for_update().get(pk=supplier.pk)
    balance = supplier_balance(supplier)
    if amount > balance:
        raise StockError(
            _("Paiement supérieur au reste à payer ({balance} MRU).").format(balance=balance)
        )
    return SupplierPayment.objects.create(
        owner=owner, supplier=supplier, amount=amount, created_by=user, **fields
    )
