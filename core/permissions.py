from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.models import Role

from .access import can_write_for, get_owner, is_direction


class HasRole(BasePermission):
    """Accès réservé à certains rôles. Utiliser `role_permission(...)` pour en créer une."""

    roles: tuple = ()
    message = "Votre rôle ne permet pas cette action."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and any(user.has_role(r) for r in self.roles))


def role_permission(*roles):
    name = "Has" + "Or".join(r.capitalize().replace("_", "") for r in roles)
    return type(name, (HasRole,), {"roles": roles})


IsDirection = role_permission(Role.DIRECTION)
IsFarmer = role_permission(Role.FARMER)
IsSeller = role_permission(Role.SELLER)
IsFieldAgent = role_permission(Role.FIELD_AGENT)
# Espace vendeur : le vendeur, et la Direction en lecture.
SellerSpaceAccess = role_permission(Role.SELLER, Role.DIRECTION)


class IsDirectionOrReadOnly(BasePermission):
    """Données publiques (oasis, variétés…) : lecture pour tous, même sans compte ;
    création et modification réservées à la Direction."""

    message = "Seule la Direction peut modifier ces informations."

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or is_direction(request.user)


class OwnerPermission(BasePermission):
    """Données privées : lecture filtrée par `OwnedQuerysetMixin`, écriture par le propriétaire
    (ou son agent tant que le compte n'est pas repris). La Direction est en lecture seule."""

    message = "Vous ne pouvez pas modifier ces données."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.method in SAFE_METHODS or not is_direction(request.user)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        owner_field = getattr(view, "owner_field", "owner")
        return can_write_for(request.user, get_owner(obj, owner_field))
