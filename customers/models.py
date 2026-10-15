from django.conf import settings
from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel
from core.money import MoneyField, PaymentMethod


class Customer(TimeStampedModel):
    """Client d'un vendeur. Dette, total acheté et segment sont calculés (jamais stockés)."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="vendeur",
        on_delete=models.PROTECT,
        related_name="customers",
    )
    name = models.CharField("nom", max_length=150)
    phone = models.CharField("téléphone", max_length=13, blank=True)
    whatsapp = models.CharField("WhatsApp", max_length=13, blank=True)
    address = models.TextField("adresse", blank=True)
    city = models.CharField("ville", max_length=100, blank=True)
    notes = models.TextField("remarques", blank=True)

    class Meta:
        verbose_name = "client"
        verbose_name_plural = "clients"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "phone"],
                condition=Q(is_active=True) & ~Q(phone=""),
                name="customer_unique_phone_per_seller",
            ),
        ]

    def __str__(self):
        return self.name


class Payment(TimeStampedModel):
    """Paiement reçu d'un client (dette = commandes livrées − paiements)."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="vendeur",
        on_delete=models.PROTECT,
        related_name="customer_payments",
    )
    customer = models.ForeignKey(
        Customer, verbose_name="client", on_delete=models.PROTECT, related_name="payments"
    )
    payment_date = models.DateField("date de paiement")
    amount = MoneyField("montant (MRU)")
    method = models.CharField(
        "moyen de paiement",
        max_length=15,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )
    reference = models.CharField("référence", max_length=100, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="saisi par",
        on_delete=models.PROTECT,
        related_name="customer_payments_created",
    )

    class Meta:
        verbose_name = "paiement client"
        verbose_name_plural = "paiements clients"
        ordering = ["-payment_date", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="payment_amount_positive"),
        ]

    def __str__(self):
        return f"Paiement {self.amount} MRU de {self.customer} ({self.payment_date})"
