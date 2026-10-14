from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify

from core.images import ResizedImageMixin, validate_image_size
from core.models import TimeStampedModel

MONTH_VALIDATORS = [MinValueValidator(1), MaxValueValidator(12)]


class SlugFromNameMixin(models.Model):
    """Identifiant d'adresse web (ex. « chinguetti ») créé à partir du nom français."""

    slug = models.SlugField("identifiant web", max_length=160, unique=True, blank=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name_fr) or "element"
            slug, n = base, 2
            while type(self).objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)


class Region(SlugFromNameMixin, TimeStampedModel):
    name_ar = models.CharField("nom (arabe)", max_length=100, unique=True)
    name_fr = models.CharField("nom (français)", max_length=100, unique=True)
    order = models.PositiveSmallIntegerField("ordre d'affichage", default=0)

    class Meta:
        verbose_name = "région"
        verbose_name_plural = "régions"
        ordering = ["order", "name_fr"]

    def __str__(self):
        return self.name_fr


class DateVariety(ResizedImageMixin, SlugFromNameMixin, TimeStampedModel):
    class Texture(models.TextChoices):
        SOFT = "soft", "Molle"
        SEMI_DRY = "semi_dry", "Demi-sèche"
        DRY = "dry", "Sèche"

    resized_image_fields = ("photo",)

    name_ar = models.CharField("nom (arabe)", max_length=100, unique=True)
    name_fr = models.CharField("nom (français)", max_length=100, unique=True)
    description_ar = models.TextField("caractéristiques (arabe)", blank=True)
    description_fr = models.TextField("caractéristiques (français)", blank=True)
    texture = models.CharField("texture", max_length=10, choices=Texture.choices, blank=True)
    ripening_start_month = models.PositiveSmallIntegerField(
        "maturité : mois de début", validators=MONTH_VALIDATORS
    )
    ripening_end_month = models.PositiveSmallIntegerField(
        "maturité : mois de fin", validators=MONTH_VALIDATORS
    )
    photo = models.ImageField(
        "photo", upload_to="varieties/", blank=True, validators=[validate_image_size]
    )

    class Meta:
        verbose_name = "variété de dattes"
        verbose_name_plural = "variétés de dattes"
        ordering = ["name_fr"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ripening_start_month__range=(1, 12))
                & models.Q(ripening_end_month__range=(1, 12)),
                name="variety_months_1_12",
            ),
        ]

    def __str__(self):
        return self.name_fr

    def is_in_season(self, month):
        """Vrai si `month` est dans la saison (gère novembre → février)."""
        start, end = self.ripening_start_month, self.ripening_end_month
        return start <= month <= end if start <= end else month >= start or month <= end


class Oasis(SlugFromNameMixin, TimeStampedModel):
    region = models.ForeignKey(
        Region, verbose_name="région", on_delete=models.PROTECT, related_name="oases"
    )
    name_ar = models.CharField("nom (arabe)", max_length=150)
    name_fr = models.CharField("nom (français)", max_length=150)
    description_ar = models.TextField("description (arabe)", blank=True)
    description_fr = models.TextField("description (français)", blank=True)
    latitude = models.DecimalField(
        "latitude",
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        "longitude",
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    varieties = models.ManyToManyField(
        DateVariety, verbose_name="variétés cultivées", blank=True, related_name="oases"
    )

    class Meta:
        verbose_name = "oasis"
        verbose_name_plural = "oasis"
        ordering = ["name_fr"]
        constraints = [
            models.UniqueConstraint(fields=["region", "name_ar"], name="oasis_unique_name_ar"),
            models.UniqueConstraint(fields=["region", "name_fr"], name="oasis_unique_name_fr"),
            models.CheckConstraint(
                condition=models.Q(latitude__isnull=True) | models.Q(latitude__range=(-90, 90)),
                name="oasis_latitude_range",
            ),
            models.CheckConstraint(
                condition=models.Q(longitude__isnull=True) | models.Q(longitude__range=(-180, 180)),
                name="oasis_longitude_range",
            ),
        ]

    def __str__(self):
        return self.name_fr


class OasisPhoto(ResizedImageMixin, TimeStampedModel):
    resized_image_fields = ("image",)

    oasis = models.ForeignKey(
        Oasis, verbose_name="oasis", on_delete=models.CASCADE, related_name="photos"
    )
    image = models.ImageField("photo", upload_to="oases/", validators=[validate_image_size])
    caption_ar = models.CharField("légende (arabe)", max_length=200, blank=True)
    caption_fr = models.CharField("légende (français)", max_length=200, blank=True)
    order = models.PositiveSmallIntegerField("ordre", default=0)

    class Meta:
        verbose_name = "photo d'oasis"
        verbose_name_plural = "photos d'oasis"
        ordering = ["order", "id"]

    def __str__(self):
        return f"Photo {self.order} – {self.oasis}"
