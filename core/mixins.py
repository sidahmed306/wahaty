from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from accounts.models import User

from .access import can_write_for, filter_readable, is_field_agent
from .permissions import OwnerPermission


class SoftDeleteMixin:
    """DELETE désactive la ligne (is_active=False) au lieu de l'effacer."""

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])


class OwnedQuerysetMixin:
    """À mettre sur chaque vue de données privées.

    - Liste et détail : seulement les lignes que l'utilisateur a le droit de lire
      (les autres répondent 404, comme si elles n'existaient pas).
    - Création : le propriétaire est l'utilisateur connecté ; un agent de terrain
      indique `owner` (l'id de l'agriculteur pour qui il saisit).
    """

    owner_field = "owner"
    permission_classes = [OwnerPermission]

    def get_queryset(self):
        return filter_readable(super().get_queryset(), self.request.user, self.owner_field)

    def get_owner_for_create(self):
        user = self.request.user
        if not is_field_agent(user):
            return user
        owner_id = self.request.data.get("owner")
        if not owner_id:
            raise serializers.ValidationError(
                {"owner": "Indiquez l'agriculteur pour qui vous saisissez."}
            )
        try:
            return User.objects.get(pk=owner_id)
        except (User.DoesNotExist, ValueError, TypeError):
            raise PermissionDenied("Agriculteur introuvable ou non géré par vous.") from None

    def perform_create(self, serializer):
        owner = self.get_owner_for_create()
        if not can_write_for(self.request.user, owner):
            raise PermissionDenied("Agriculteur introuvable ou non géré par vous.")
        serializer.save(**{self.owner_field: owner})
