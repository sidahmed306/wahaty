from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models import TimeStampedModel
from core.money import MoneyField, PaymentMethod

QUANTITY = {"max_digits": 10, "decimal_places": 2}


class Supplier(TimeStampedModel):
    """Fournisseur d'un vendeur. Reste à payer = achats − paiements (calculé)."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="vendeur",
        on_delete=models.PROTECT,
        related_name="suppliers",
    )
    name = models.CharField("nom", max_length=150)
    phone = models.CharField("téléphone", max_length=13, blank=True)
    oasis = models.ForeignKey(
        "oases.Oasis",
        verbose_name="oasis",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="suppliers",
    )
    notes = models.TextField("remarques", blank=True)

    class Meta:
        verbose_name = "fournisseur"
        verbose_name_plural = "fournisseurs"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(TimeStampedModel):
    """Produit du vendeur. Pas de champ « stock » : il est calculé à partir des mouvements."""

    class Unit(models.TextChoices):
        KG = "kg", "kg"
        BOX = "box", "carton"
        BAG = "bag", "sac"
        PIECE = "piece", "pièce"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="vendeur",
        on_delete=models.PROTECT,
        related_name="products",
    )
    name = models.CharField("nom", max_length=150)
    variety = models.ForeignKey(
        "oases.DateVariety",
        verbose_name="variété",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="products",
    )
    unit = models.CharField("unité", max_length=10, choices=Unit.choices, default=Unit.KG)
    sale_price = MoneyField(
        "prix de vente conseillé (MRU)",
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    low_stock_threshold = models.DecimalField(
        "alerte stock bas",
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        **QUANTITY,
    )

    class Meta:
        verbose_name = "produit"
        verbose_name_plural = "produits"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"],
                condition=Q(is_active=True),
                name="product_unique_name_per_owner",
            ),
        ]

    def __str__(self):
        return self.name


class Purchase(TimeStampedModel):
    """Achat chez un fournisseur ; ses lignes sont des mouvements de stock « purchase »."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="vendeur",
        on_delete=models.PROTECT,
        related_name="purchases",
    )
    supplier = models.ForeignKey(
        Supplier, verbose_name="fournisseur", on_delete=models.PROTECT, related_name="purchases"
    )
    purchase_date = models.DateField("date d'achat")
    reference = models.CharField("référence du bon", max_length=50, blank=True)
    total_amount = MoneyField("montant total (MRU)", editable=False)
    cancelled_at = models.DateTimeField("annulé le", null=True, blank=True)
    cancel_reason = models.TextField("motif d'annulation", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="saisi par",
        on_delete=models.PROTECT,
        related_name="purchases_created",
    )

    class Meta:
        verbose_name = "achat"
        verbose_name_plural = "achats"
        ordering = ["-purchase_date", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(total_amount__gt=0), name="purchase_total_positive"),
        ]

    def __str__(self):
        return f"Achat {self.reference or self.pk} – {self.supplier} – {self.total_amount} MRU"

    @property
    def is_cancelled(self):
        return self.cancelled_at is not None


class StockMovement(models.Model):
    """Entrée ou sortie de stock. Jamais modifiée ni supprimée : on corrige par un ajustement."""

    class Kind(models.TextChoices):
        PURCHASE = "purchase", "Achat (entrée)"
        RETURN = "return", "Retour client (entrée)"
        ADJUST_IN = "adjust_in", "Correction + (entrée)"
        SALE = "sale", "Livraison d'une commande (sortie)"
        LOSS = "loss", "Perte / abîmé (sortie)"
        ADJUST_OUT = "adjust_out", "Correction − (sortie)"

    IN_KINDS = (Kind.PURCHASE, Kind.RETURN, Kind.ADJUST_IN)
    OUT_KINDS = (Kind.SALE, Kind.LOSS, Kind.ADJUST_OUT)
    # Mouvements saisis à la main (les autres viennent d'un achat ou d'une commande).
    MANUAL_KINDS = (Kind.ADJUST_IN, Kind.LOSS, Kind.ADJUST_OUT)

    product = models.ForeignKey(
        Product, verbose_name="produit", on_delete=models.PROTECT, related_name="movements"
    )
    kind = models.CharField("type", max_length=12, choices=Kind.choices)
    quantity = models.DecimalField(
        "quantité", validators=[MinValueValidator(Decimal("0.01"))], **QUANTITY
    )
    unit_cost = MoneyField("coût unitaire (MRU)", null=True, blank=True)
    purchase = models.ForeignKey(
        Purchase,
        verbose_name="achat",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lines",
    )
    movement_date = models.DateTimeField("date", default=timezone.now)
    note = models.TextField("justification", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="saisi par",
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    created_at = models.DateTimeField("créé le", auto_now_add=True)

    class Meta:
        verbose_name = "mouvement de stock"
        verbose_name_plural = "mouvements de stock"
        ordering = ["-movement_date", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="movement_quantity_positive"),
            models.CheckConstraint(
                condition=~Q(kind="purchase")
                | (Q(purchase__isnull=False) & Q(unit_cost__isnull=False)),
                name="movement_purchase_has_cost",
            ),
        ]
        indexes = [models.Index(fields=["product", "kind"])]

    def __str__(self):
        sign = "+" if self.is_in else "−"
        return f"{self.product} {sign}{self.quantity} ({self.get_kind_display()})"

    @property
    def is_in(self):
        return self.kind in self.IN_KINDS

    @property
    def signed_quantity(self):
        return self.quantity if self.is_in else -self.quantity


class SupplierPayment(TimeStampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="vendeur",
        on_delete=models.PROTECT,
        related_name="supplier_payments",
    )
    supplier = models.ForeignKey(
        Supplier, verbose_name="fournisseur", on_delete=models.PROTECT, related_name="payments"
    )
    purchase = models.ForeignKey(
        Purchase,
        verbose_name="achat concerné",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payments",
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
        related_name="supplier_payments_created",
    )

    class Meta:
        verbose_name = "paiement fournisseur"
        verbose_name_plural = "paiements fournisseurs"
        ordering = ["-payment_date", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="supplier_payment_amount_positive"
            ),
        ]

    def __str__(self):
        return f"Paiement {self.amount} MRU à {self.supplier} ({self.payment_date})"
