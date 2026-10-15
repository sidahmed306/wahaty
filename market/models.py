from decimal import Decimal
from urllib.parse import quote

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from core.images import ResizedImageMixin, validate_image_size
from core.models import TimeStampedModel
from core.money import MoneyField

MAX_PHOTOS = 5


class ListingStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    PENDING = "pending", "En attente de validation"
    PUBLISHED = "published", "Publiée"
    REJECTED = "rejected", "Refusée"
    SOLD = "sold", "Vendue"


# Une annonce ne se modifie (texte, prix, photos) qu'en brouillon ou après un refus.
EDITABLE_STATUSES = (ListingStatus.DRAFT, ListingStatus.REJECTED)


class Listing(TimeStampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="vendeur",
        on_delete=models.PROTECT,
        related_name="listings",
    )
    variety = models.ForeignKey(
        "oases.DateVariety",
        verbose_name="variété",
        on_delete=models.PROTECT,
        related_name="listings",
    )
    oasis = models.ForeignKey(
        "oases.Oasis", verbose_name="oasis", on_delete=models.PROTECT, related_name="listings"
    )
    title = models.CharField("titre", max_length=150)
    description = models.TextField("description", blank=True)
    language = models.CharField(
        "langue du texte", max_length=2, choices=[("ar", "العربية"), ("fr", "Français")]
    )
    price_per_kg = MoneyField("prix au kg (MRU)")
    quantity_kg = models.DecimalField(
        "quantité disponible (kg)",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    contact_phone = models.CharField("téléphone de contact", max_length=13)
    whatsapp_phone = models.CharField("WhatsApp", max_length=13, blank=True)
    status = models.CharField(
        "statut", max_length=10, choices=ListingStatus.choices, default=ListingStatus.DRAFT
    )
    rejection_reason = models.TextField("motif du refus", blank=True)
    published_at = models.DateTimeField("publiée le", null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="validée par",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="listings_reviewed",
    )

    class Meta:
        verbose_name = "annonce"
        verbose_name_plural = "annonces"
        ordering = ["-published_at", "-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(price_per_kg__gt=0), name="listing_price_positive"),
            models.CheckConstraint(
                condition=Q(quantity_kg__gt=0), name="listing_quantity_positive"
            ),
        ]
        indexes = [models.Index(fields=["status", "is_active"])]

    def __str__(self):
        return self.title

    @property
    def is_editable(self):
        return self.status in EDITABLE_STATUSES

    @property
    def whatsapp_link(self):
        """Lien wa.me avec un message prêt à envoyer (numéro sans « + »)."""
        phone = self.whatsapp_phone or self.contact_phone
        message = (
            f"السلام عليكم، أنا مهتم بإعلانكم « {self.title} » على واحتي."
            if self.language == "ar"
            else f"Bonjour, je suis intéressé(e) par votre annonce « {self.title} » sur Wahaty."
        )
        return f"https://wa.me/{phone.lstrip('+')}?text={quote(message)}"

    @property
    def phone_link(self):
        return f"tel:{self.contact_phone}"


class ListingPhoto(ResizedImageMixin, TimeStampedModel):
    resized_image_fields = ("image",)

    listing = models.ForeignKey(
        Listing, verbose_name="annonce", on_delete=models.CASCADE, related_name="photos"
    )
    image = models.ImageField("photo", upload_to="listings/", validators=[validate_image_size])
    order = models.PositiveSmallIntegerField("ordre", default=0)

    class Meta:
        verbose_name = "photo d'annonce"
        verbose_name_plural = "photos d'annonces"
        ordering = ["order", "id"]

    def __str__(self):
        return f"Photo {self.order} – {self.listing}"
