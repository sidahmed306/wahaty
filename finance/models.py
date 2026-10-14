from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel
from core.money import MoneyField, round_money


class ExpenseCategory(TimeStampedModel):
    """Catégories de dépenses bilingues, gérées par la Direction."""

    class AppliesTo(models.TextChoices):
        FARMER = "farmer", "Agriculteur"
        SELLER = "seller", "Vendeur"
        BOTH = "both", "Les deux"

    name_ar = models.CharField("nom (arabe)", max_length=100, unique=True)
    name_fr = models.CharField("nom (français)", max_length=100, unique=True)
    applies_to = models.CharField(
        "pour qui", max_length=10, choices=AppliesTo.choices, default=AppliesTo.BOTH
    )
    order = models.PositiveSmallIntegerField("ordre d'affichage", default=0)

    class Meta:
        verbose_name = "catégorie de dépense"
        verbose_name_plural = "catégories de dépenses"
        ordering = ["order", "name_fr"]

    def __str__(self):
        return self.name_fr

    def usable_by(self, user):
        return self.applies_to == self.AppliesTo.BOTH or user.has_role(self.applies_to)


class Sale(TimeStampedModel):
    """Vente directe d'un agriculteur (hors commande). Total = quantité × prix au kg."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="agriculteur",
        on_delete=models.PROTECT,
        related_name="sales",
    )
    farm = models.ForeignKey(
        "farms.Farm",
        verbose_name="ferme",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sales",
    )
    variety = models.ForeignKey(
        "oases.DateVariety",
        verbose_name="variété",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sales",
    )
    sale_date = models.DateField("date de vente")
    quantity_kg = models.DecimalField(
        "quantité (kg)",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    unit_price = MoneyField("prix au kg (MRU)")
    total_amount = MoneyField("montant total (MRU)", editable=False)
    buyer_name = models.CharField("acheteur", max_length=150, blank=True)
    notes = models.TextField("remarques", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="saisi par",
        on_delete=models.PROTECT,
        related_name="sales_created",
    )

    class Meta:
        verbose_name = "vente"
        verbose_name_plural = "ventes"
        ordering = ["-sale_date", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity_kg__gt=0), name="sale_quantity_positive"),
            models.CheckConstraint(condition=Q(unit_price__gt=0), name="sale_price_positive"),
            models.CheckConstraint(condition=Q(total_amount__gt=0), name="sale_total_positive"),
        ]
        indexes = [models.Index(fields=["owner", "sale_date"])]

    def __str__(self):
        return f"Vente du {self.sale_date} – {self.total_amount} MRU"

    def save(self, *args, **kwargs):
        # Le total est toujours calculé par le serveur, jamais saisi.
        self.total_amount = round_money(self.quantity_kg * self.unit_price)
        super().save(*args, **kwargs)


class Expense(TimeStampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="propriétaire",
        on_delete=models.PROTECT,
        related_name="expenses",
    )
    category = models.ForeignKey(
        ExpenseCategory,
        verbose_name="catégorie",
        on_delete=models.PROTECT,
        related_name="expenses",
    )
    farm = models.ForeignKey(
        "farms.Farm",
        verbose_name="ferme",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="expenses",
    )
    expense_date = models.DateField("date")
    amount = MoneyField("montant (MRU)")
    description = models.TextField("description", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="saisi par",
        on_delete=models.PROTECT,
        related_name="expenses_created",
    )

    class Meta:
        verbose_name = "dépense"
        verbose_name_plural = "dépenses"
        ordering = ["-expense_date", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="expense_amount_positive"),
        ]
        indexes = [models.Index(fields=["owner", "expense_date"])]

    def __str__(self):
        return f"{self.category} – {self.amount} MRU ({self.expense_date})"
