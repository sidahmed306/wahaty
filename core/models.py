from django.db import models


class TimeStampedModel(models.Model):
    """Base commune : dates de création / modification et suppression douce."""

    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)
    is_active = models.BooleanField("actif", default=True)

    class Meta:
        abstract = True
