from django.conf import settings
from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel
from core.money import MoneyField
from orders.models import ZERO_OK


class InvoiceSequence(models.Model):
    """Compteur de factures d'un vendeur pour une année (verrouillé pendant la création)."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="vendeur",
        on_delete=models.PROTECT,
        related_name="invoice_sequences",
    )
    year = models.PositiveSmallIntegerField("année")
    last_number = models.PositiveIntegerField("dernier numéro utilisé", default=0)

    class Meta:
        verbose_name = "compteur de factures"
        verbose_name_plural = "compteurs de factures"
        constraints = [
            models.UniqueConstraint(fields=["owner", "year"], name="invoice_sequence_unique"),
        ]

    def __str__(self):
        return f"{self.owner} – {self.year} : {self.last_number}"


class Invoice(TimeStampedModel):
    """Facture d'une commande. Les informations sont copiées au moment de la facture :
    elle ne change pas si le client ou les produits changent ensuite."""

    class Status(models.TextChoices):
        ISSUED = "issued", "Émise"
        CANCELLED = "cancelled", "Annulée"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="vendeur",
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    order = models.ForeignKey(
        "orders.Order", verbose_name="commande", on_delete=models.PROTECT, related_name="invoices"
    )
    number = models.CharField("numéro", max_length=30)
    year = models.PositiveSmallIntegerField("année")
    sequence = models.PositiveIntegerField("numéro d'ordre")
    issue_date = models.DateField("date d'émission")
    seller_snapshot = models.JSONField("vendeur (copie)")
    customer_snapshot = models.JSONField("client (copie)")
    lines_snapshot = models.JSONField("lignes (copie)")
    subtotal = MoneyField("sous-total (MRU)", validators=ZERO_OK)
    delivery_fee = MoneyField("frais de livraison (MRU)", validators=ZERO_OK)
    discount = MoneyField("remise (MRU)", validators=ZERO_OK)
    total_amount = MoneyField("total (MRU)", validators=ZERO_OK)
    status = models.CharField(
        "statut", max_length=10, choices=Status.choices, default=Status.ISSUED
    )
    cancelled_at = models.DateTimeField("annulée le", null=True, blank=True)
    cancel_reason = models.TextField("motif d'annulation", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="émise par",
        on_delete=models.PROTECT,
        related_name="invoices_created",
    )

    class Meta:
        verbose_name = "facture"
        verbose_name_plural = "factures"
        ordering = ["-year", "-sequence"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "number"], name="invoice_unique_number"),
            models.UniqueConstraint(
                fields=["owner", "year", "sequence"], name="invoice_unique_sequence"
            ),
            # Une seule facture valide par commande (une facture annulée garde son numéro).
            models.UniqueConstraint(
                fields=["order"], condition=Q(status="issued"), name="invoice_one_issued_per_order"
            ),
        ]

    def __str__(self):
        return self.number
