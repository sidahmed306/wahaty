from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class TimeStampedModel(models.Model):
    """Base commune : dates de création / modification et suppression douce."""

    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)
    is_active = models.BooleanField("actif", default=True)

    class Meta:
        abstract = True


class PlatformSettings(models.Model):
    """Réglages modifiables par la Direction, sans toucher au code (une seule ligne)."""

    premium_threshold = models.DecimalField(
        "seuil Premium (MRU)",
        max_digits=12,
        decimal_places=2,
        default=Decimal("100000.00"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    new_customer_days = models.PositiveSmallIntegerField(
        "« nouveau » pendant (jours)", default=30, validators=[MinValueValidator(1)]
    )
    loyal_min_orders = models.PositiveSmallIntegerField(
        "« fidèle » : commandes minimum", default=3, validators=[MinValueValidator(1)]
    )
    loyal_period_days = models.PositiveSmallIntegerField(
        "« fidèle » : période observée (jours)", default=180, validators=[MinValueValidator(1)]
    )
    inactive_days = models.PositiveSmallIntegerField(
        "« inactif » sans commande depuis (jours)", default=90, validators=[MinValueValidator(1)]
    )
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "réglages de la plateforme"
        verbose_name_plural = "réglages de la plateforme"
        constraints = [
            models.CheckConstraint(condition=models.Q(pk=1), name="platform_settings_single_row"),
        ]

    def __str__(self):
        return "Réglages de la plateforme"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings
