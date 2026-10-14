from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image


def make_image(width=800, height=600, fmt="PNG", name=None, mode="RGB"):
    buffer = BytesIO()
    Image.new(mode, (width, height), color=(200, 150, 50) if mode == "RGB" else None).save(
        buffer, format=fmt
    )
    name = name or f"photo.{fmt.lower()}"
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=f"image/{fmt.lower()}")
