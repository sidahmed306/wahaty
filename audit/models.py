from django.conf import settings
from django.db import models


class AuditLogQuerySet(models.QuerySet):
    """Le journal ne se modifie ni ne s'efface, même en masse."""

    def update(self, **kwargs):
        raise PermissionError("Le journal d'audit ne peut pas être modifié.")

    def delete(self):
        raise PermissionError("Le journal d'audit ne peut pas être effacé.")


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE = "create", "Création"
        UPDATE = "update", "Modification"
        DELETE = "delete", "Suppression / désactivation"
        STATUS_CHANGE = "status_change", "Changement de statut"
        LOGIN = "login", "Connexion"
        LOGIN_FAILED = "login_failed", "Connexion refusée"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="qui",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="audit_entries",
        help_text="Vide si l'action est automatique (commande planifiée).",
    )
    acting_for = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="pour le compte de",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="audit_entries_on_behalf",
    )
    action = models.CharField("action", max_length=20, choices=Action.choices)
    object_type = models.CharField("type d'objet", max_length=60)
    object_id = models.CharField("identifiant", max_length=40, blank=True)
    object_repr = models.CharField("objet", max_length=200, blank=True)
    changes = models.JSONField("anciennes → nouvelles valeurs", default=dict, blank=True)
    ip_address = models.GenericIPAddressField("adresse IP", null=True, blank=True)
    created_at = models.DateTimeField("quand", auto_now_add=True, db_index=True)

    objects = AuditLogQuerySet.as_manager()

    class Meta:
        verbose_name = "entrée du journal"
        verbose_name_plural = "journal d'audit"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["object_type", "object_id"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return (
            f"{self.created_at:%d/%m/%Y %H:%M} – {self.get_action_display()} – {self.object_repr}"
        )

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise PermissionError("Le journal d'audit ne peut pas être modifié.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Le journal d'audit ne peut pas être effacé.")
