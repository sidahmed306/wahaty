"""Montants en MRU : toujours en Decimal (jamais float), 2 décimales, arrondi commercial."""

from decimal import ROUND_HALF_UP, Decimal

from django.core.validators import MinValueValidator
from django.db import models

CENT = Decimal("0.01")
MONEY_DIGITS = 12  # jusqu'à 9 999 999 999,99 MRU
MAX_MONEY = Decimal(10 ** (MONEY_DIGITS - 2)) - CENT


class PaymentMethod(models.TextChoices):
    CASH = "cash", "Espèces"
    BANKILY = "bankily", "Bankily"
    MASRVI = "masrvi", "Masrvi"
    SEDAD = "sedad", "Sedad"
    BANK_TRANSFER = "bank_transfer", "Virement bancaire"
    OTHER = "other", "Autre"


def round_money(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def MoneyField(verbose_name, **kwargs):  # noqa: N802 – se lit comme un type de champ
    kwargs.setdefault("validators", [MinValueValidator(CENT)])
    return models.DecimalField(verbose_name, max_digits=MONEY_DIGITS, decimal_places=2, **kwargs)
