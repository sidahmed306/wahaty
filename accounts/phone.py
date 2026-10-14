"""Numéros de téléphone mauritaniens : +222 suivi de 8 chiffres (commençant par 2, 3 ou 4)."""

import re

from django.core.exceptions import ValidationError

PHONE_RE = re.compile(r"^\+222[234]\d{7}$")


def normalize_phone(value: str) -> str:
    """Met un numéro au format +222XXXXXXXX.

    Accepte « 22 12 34 56 », « +222 22123456 », « 0022222123456 »…
    Lève ValidationError si le numéro n'est pas mauritanien valide.
    """
    digits = re.sub(r"[\s.\-()]", "", value or "")
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if not digits.startswith("+"):
        digits = "+222" + digits
    if not PHONE_RE.match(digits):
        raise ValidationError(
            "Numéro invalide : 8 chiffres commençant par 2, 3 ou 4 (ex. 22 12 34 56).",
            code="invalid_phone",
        )
    return digits
