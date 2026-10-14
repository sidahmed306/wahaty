"""Qui peut lire / modifier les données de qui (règles de la section 4 du cahier).

- Chaque utilisateur lit et modifie ses propres données.
- La Direction lit tout, mais ne modifie pas les données privées des utilisateurs.
- Un agent de terrain lit les données des agriculteurs qu'il a inscrits, et les
  modifie tant que l'agriculteur n'a pas repris la main sur son compte (claimed_at).
"""

from django.db.models import Q

from accounts.models import Role, User


def is_direction(user):
    return user.is_authenticated and user.has_role(Role.DIRECTION)


def is_field_agent(user):
    return user.is_authenticated and user.has_role(Role.FIELD_AGENT)


def managed_farmers(agent):
    """Agriculteurs inscrits par cet agent (repris en main ou non)."""
    return User.objects.filter(registered_by=agent, roles__contains=[Role.FARMER])


def readable_filter(user, owner_field="owner"):
    """Filtre des lignes lisibles par `user` ; None signifie « tout » (Direction)."""
    if is_direction(user):
        return None
    condition = Q(**{owner_field: user})
    if is_field_agent(user):
        condition |= Q(**{f"{owner_field}__in": managed_farmers(user)})
    return condition


def filter_readable(queryset, user, owner_field="owner"):
    condition = readable_filter(user, owner_field)
    return queryset if condition is None else queryset.filter(condition)


def can_write_for(user, owner):
    """`user` peut-il créer ou modifier des données appartenant à `owner` ?"""
    if not user.is_authenticated or owner is None:
        return False
    if is_direction(user):
        return False
    if owner.pk == user.pk:
        return True
    return (
        is_field_agent(user)
        and owner.registered_by_id == user.pk
        and owner.has_role(Role.FARMER)
        and owner.claimed_at is None
    )


def get_owner(obj, owner_field="owner"):
    """Suit un chemin comme « farm__owner » pour trouver le propriétaire d'un objet."""
    for part in owner_field.split("__"):
        obj = getattr(obj, part)
    return obj
