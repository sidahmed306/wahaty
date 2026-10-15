from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models import TimeStampedModel
from core.money import MoneyField

ZERO_OK = [MinValueValidator(Decimal("0"))]


class OrderStatus(models.TextChoices):
    RECEIVED = "received", "Reçue"
    CONFIRMED = "confirmed", "Confirmée"
    PREPARED = "prepared", "Préparée"
    OUT_FOR_DELIVERY = "out_for_delivery", "En livraison"
    DELIVERED = "delivered", "Livrée"
    CANCELLED = "cancelled", "Annulée"


# Transitions autorisées (toute autre est refusée). Annulation possible jusqu'à « préparée » (Q9).
TRANSITIONS = {
    OrderStatus.RECEIVED: {OrderStatus.CONFIRMED, OrderStatus.CANCELLED},
    OrderStatus.CONFIRMED: {OrderStatus.PREPARED, OrderStatus.CANCELLED},
    OrderStatus.PREPARED: {OrderStatus.OUT_FOR_DELIVERY, OrderStatus.CANCELLED},
    OrderStatus.OUT_FOR_DELIVERY: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}
CLOSED_STATUSES = (OrderStatus.DELIVERED, OrderStatus.CANCELLED)


class Order(TimeStampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="vendeur",
        on_delete=models.PROTECT,
        related_name="orders",
    )
    customer = models.ForeignKey(
        "customers.Customer", verbose_name="client", on_delete=models.PROTECT, related_name="orders"
    )
    number = models.CharField("numéro", max_length=20)
    status = models.CharField(
        "statut", max_length=20, choices=OrderStatus.choices, default=OrderStatus.RECEIVED
    )
    order_date = models.DateField("date de commande", default=timezone.localdate)
    expected_delivery_date = models.DateField("livraison prévue le")
    delivered_at = models.DateTimeField("livrée le", null=True, blank=True)
    delivery_address = models.TextField("adresse de livraison", blank=True)
    delivery_fee = MoneyField("frais de livraison (MRU)", default=Decimal("0"), validators=ZERO_OK)
    discount = MoneyField("remise (MRU)", default=Decimal("0"), validators=ZERO_OK)
    subtotal = MoneyField("sous-total (MRU)", default=Decimal("0"), validators=ZERO_OK)
    total_amount = MoneyField("total (MRU)", default=Decimal("0"), validators=ZERO_OK)
    cancel_reason = models.TextField("motif d'annulation", blank=True)
    notes = models.TextField("remarques", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="saisie par",
        on_delete=models.PROTECT,
        related_name="orders_created",
    )

    class Meta:
        verbose_name = "commande"
        verbose_name_plural = "commandes"
        ordering = ["-order_date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "number"], name="order_unique_number"),
            models.CheckConstraint(
                condition=Q(delivery_fee__gte=0) & Q(discount__gte=0) & Q(total_amount__gte=0),
                name="order_amounts_positive",
            ),
            models.CheckConstraint(
                condition=~Q(status="cancelled") | ~Q(cancel_reason=""),
                name="order_cancel_has_reason",
            ),
        ]
        indexes = [
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["expected_delivery_date"]),
        ]

    def __str__(self):
        return f"Commande {self.number}"

    @property
    def is_late(self):
        """En retard : date prévue dépassée et commande ni livrée ni annulée."""
        return (
            self.status not in CLOSED_STATUSES
            and self.expected_delivery_date < timezone.localdate()
        )

    @property
    def days_late(self):
        return (timezone.localdate() - self.expected_delivery_date).days if self.is_late else 0


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, verbose_name="commande", on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        "inventory.Product",
        verbose_name="produit",
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    quantity = models.DecimalField(
        "quantité",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    unit_price = MoneyField("prix unitaire (MRU)", validators=ZERO_OK)
    line_total = MoneyField("total de la ligne (MRU)", validators=ZERO_OK)

    class Meta:
        verbose_name = "ligne de commande"
        verbose_name_plural = "lignes de commande"
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="orderitem_quantity_positive"),
        ]

    def __str__(self):
        return f"{self.product} × {self.quantity}"


class OrderStatusHistory(models.Model):
    """Historique des statuts : qui, quand, de quoi à quoi. Jamais modifié."""

    order = models.ForeignKey(
        Order, verbose_name="commande", on_delete=models.CASCADE, related_name="history"
    )
    from_status = models.CharField(
        "ancien statut", max_length=20, choices=OrderStatus.choices, blank=True
    )
    to_status = models.CharField("nouveau statut", max_length=20, choices=OrderStatus.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="par",
        on_delete=models.PROTECT,
        related_name="order_status_changes",
    )
    changed_at = models.DateTimeField("le", default=timezone.now)
    note = models.TextField("remarque", blank=True)

    class Meta:
        verbose_name = "historique de statut"
        verbose_name_plural = "historique des statuts"
        ordering = ["changed_at", "id"]

    def __str__(self):
        return f"{self.order} : {self.from_status or '—'} → {self.to_status}"


class Notification(models.Model):
    """Rappel affiché dans la plateforme (pas de SMS ni WhatsApp automatique : Q10)."""

    class Kind(models.TextChoices):
        DELIVERY_DUE = "delivery_due", "Livraison demain"
        ORDER_LATE = "order_late", "Commande en retard"
        LOW_STOCK = "low_stock", "Stock bas"
        LISTING_PUBLISHED = "listing_published", "Annonce publiée"
        LISTING_REJECTED = "listing_rejected", "Annonce refusée"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="destinataire",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    kind = models.CharField("type", max_length=20, choices=Kind.choices)
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications"
    )
    product = models.ForeignKey(
        "inventory.Product",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    day = models.DateField("jour", default=timezone.localdate)
    message_ar = models.TextField("message (arabe)")
    message_fr = models.TextField("message (français)")
    read_at = models.DateTimeField("lue le", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "notification"
        verbose_name_plural = "notifications"
        ordering = ["-created_at", "-id"]
        constraints = [
            # Pas de doublon : une notification par (commande ou produit, type, jour).
            models.UniqueConstraint(
                fields=["kind", "order", "day"],
                condition=Q(order__isnull=False),
                name="notification_once_per_order_day",
            ),
            models.UniqueConstraint(
                fields=["kind", "product", "day"],
                condition=Q(product__isnull=False),
                name="notification_once_per_product_day",
            ),
        ]

    def __str__(self):
        return self.message_fr
