"""Préparation des photos avant stockage : taille limitée, redimensionnement, format JPEG."""

from io import BytesIO
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 Mo
MAX_SIDE_PX = 1600  # assez pour un téléphone, léger sur les connexions lentes
JPEG_QUALITY = 82


def validate_image_size(file):
    if file.size > MAX_UPLOAD_BYTES:
        raise ValidationError("Image trop lourde : 5 Mo maximum.", code="image_too_large")


def resize_image(file, max_side=MAX_SIDE_PX):
    """Retourne une copie JPEG redimensionnée (côté le plus long ≤ max_side)."""
    file.seek(0)
    with Image.open(file) as img:
        img = ImageOps.exif_transpose(img)  # photos de téléphone : bonne orientation
        img.thumbnail((max_side, max_side))
        if img.mode != "RGB":
            img = img.convert("RGB")
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    name = Path(getattr(file, "name", "photo")).stem + ".jpg"
    return ContentFile(buffer.getvalue(), name=name)


class ResizedImageMixin:
    """Modèle : redimensionne les champs de `resized_image_fields` avant l'enregistrement."""

    resized_image_fields: tuple = ()

    def save(self, *args, **kwargs):
        for field in self.resized_image_fields:
            image = getattr(self, field)
            if image and not image._committed:
                setattr(self, field, resize_image(image))
        super().save(*args, **kwargs)
