"""Champs d'API communs : montants MRU, quantités, dates, liens vers ses propres données."""

from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import serializers

from .money import CENT, MONEY_DIGITS


def money_field(**kwargs):
    kwargs.setdefault("min_value", CENT)
    return serializers.DecimalField(max_digits=MONEY_DIGITS, decimal_places=2, **kwargs)


def quantity_field(**kwargs):
    kwargs.setdefault("min_value", CENT)
    return serializers.DecimalField(max_digits=10, decimal_places=2, **kwargs)


def not_in_future(value):
    if value > timezone.localdate():
        raise serializers.ValidationError(_("La date ne peut pas être dans le futur."))
    return value


class OwnRelatedField(serializers.PrimaryKeyRelatedField):
    """Lien vers une ligne active appartenant à l'utilisateur connecté.

    Une ligne d'un autre utilisateur répond « introuvable » (on ne révèle pas qu'elle existe).
    """

    def __init__(self, model, **kwargs):
        self.model = model
        super().__init__(**kwargs)

    def get_queryset(self):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return (
            self.model.objects.filter(owner=user, is_active=True)
            if user
            else self.model.objects.none()
        )
