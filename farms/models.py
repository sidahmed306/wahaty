from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel
from oases.models import DateVariety, Oasis

GPS = {"max_digits": 9, "decimal_places": 6, "null": True, "blank": True}


class Farm(TimeStampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="agriculteur",
        on_delete=models.PROTECT,
        related_name="farms",
    )
    oasis = models.ForeignKey(
        Oasis, verbose_name="oasis", on_delete=models.PROTECT, related_name="farms"
    )
    name = models.CharField("nom de la ferme", max_length=150)
    area_hectares = models.DecimalField(
        "surface (hectares)",
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    latitude = models.DecimalField(
        "latitude", validators=[MinValueValidator(-90), MaxValueValidator(90)], **GPS
    )
    longitude = models.DecimalField(
        "longitude", validators=[MinValueValidator(-180), MaxValueValidator(180)], **GPS
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="saisi par",
        on_delete=models.PROTECT,
        related_name="farms_created",
    )

    class Meta:
        verbose_name = "ferme"
        verbose_name_plural = "fermes"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"],
                condition=Q(is_active=True),
                name="farm_unique_name_per_owner",
            ),
            models.CheckConstraint(
                condition=Q(area_hectares__isnull=True) | Q(area_hectares__gte=0),
                name="farm_area_positive",
            ),
        ]

    def __str__(self):
        return self.name


class PalmGroup(TimeStampedModel):
    """Nombre de palmiers d'une variété dans une ferme (une ligne par couple ferme–variété)."""

    farm = models.ForeignKey(
        Farm, verbose_name="ferme", on_delete=models.PROTECT, related_name="palm_groups"
    )
    variety = models.ForeignKey(
        DateVariety, verbose_name="variété", on_delete=models.PROTECT, related_name="palm_groups"
    )
    productive_count = models.PositiveIntegerField("palmiers productifs", default=0)
    young_count = models.PositiveIntegerField("jeunes palmiers", default=0)

    class Meta:
        verbose_name = "palmiers d'une variété"
        verbose_name_plural = "palmiers par variété"
        ordering = ["farm", "variety__name_fr"]
        constraints = [
            models.UniqueConstraint(
                fields=["farm", "variety"],
                condition=Q(is_active=True),
                name="palmgroup_unique_variety_per_farm",
            ),
        ]

    def __str__(self):
        return f"{self.farm} – {self.variety} ({self.total_count})"

    @property
    def total_count(self):
        return self.productive_count + self.young_count


class Harvest(TimeStampedModel):
    """Une cueillette. La production d'une saison = somme de ses cueillettes."""

    farm = models.ForeignKey(
        Farm, verbose_name="ferme", on_delete=models.PROTECT, related_name="harvests"
    )
    variety = models.ForeignKey(
        DateVariety, verbose_name="variété", on_delete=models.PROTECT, related_name="harvests"
    )
    season = models.PositiveSmallIntegerField(
        "saison (année)", validators=[MinValueValidator(2000), MaxValueValidator(2100)]
    )
    harvest_date = models.DateField("date de récolte")
    quantity_kg = models.DecimalField(
        "quantité (kg)",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    notes = models.TextField("remarques", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="saisi par",
        on_delete=models.PROTECT,
        related_name="harvests_created",
    )

    class Meta:
        verbose_name = "récolte"
        verbose_name_plural = "récoltes"
        ordering = ["-harvest_date", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity_kg__gt=0), name="harvest_quantity_positive"
            ),
        ]
        indexes = [models.Index(fields=["farm", "season"])]

    def __str__(self):
        return f"{self.farm} – {self.variety} – {self.quantity_kg} kg ({self.harvest_date})"
