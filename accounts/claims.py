"""Reprise en main d'un compte agriculteur créé par un agent de terrain (sans SMS : gratuit).

1. L'agent crée le compte : un code de 8 caractères s'affiche une seule fois.
2. L'agent remet ce code à l'agriculteur (en main propre ou par téléphone).
3. L'agriculteur saisit son numéro + le code + son nouveau mot de passe.
"""

import secrets
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from .models import AccountClaim, User

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sans 0/O, 1/I/L : pas de confusion
CODE_LENGTH = 8
CODE_VALIDITY = timedelta(days=7)


class ClaimError(Exception):
    pass


def new_claim_code(farmer, agent):
    """Crée (ou remplace) le code de reprise ; retourne le code en clair et sa date d'expiration."""
    if farmer.claimed_at is not None:
        raise ClaimError("Ce compte a déjà été repris par l'agriculteur.")
    code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
    expires_at = timezone.now() + CODE_VALIDITY
    AccountClaim.objects.update_or_create(
        user=farmer,
        defaults={"code_hash": make_password(code), "expires_at": expires_at, "created_by": agent},
    )
    return code, expires_at


def normalize_code(code):
    return "".join(code.split()).replace("-", "").upper()


@transaction.atomic
def claim_account(phone, code, password):
    """Vérifie le code et donne le compte à l'agriculteur. Lève ClaimError sinon."""
    error = ClaimError("Numéro ou code de reprise incorrect, ou code expiré.")
    user = User.objects.select_for_update().filter(phone=phone).first()
    claim = getattr(user, "claim", None) if user else None
    if (
        claim is None
        or user.claimed_at is not None
        or claim.expires_at < timezone.now()
        or not check_password(normalize_code(code), claim.code_hash)
    ):
        raise error
    user.set_password(password)
    user.claimed_at = timezone.now()
    user.save(update_fields=["password", "claimed_at", "updated_at"])
    claim.delete()
    return user
