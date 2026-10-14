from django.conf import settings
from django.db import models


class Note(models.Model):
    """Donnée privée factice pour tester l'isolation, comme le seront fermes, ventes, stock…"""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    text = models.CharField(max_length=100)

    def __str__(self):
        return self.text
