"""Journal automatique : qui, quand, quoi (anciennes → nouvelles valeurs).

Chaque enregistrement d'une table surveillée (argent, stock, statuts, comptes…) crée une
entrée, que la modification vienne de l'API, de l'administration ou d'une commande.
L'auteur est l'utilisateur de la requête en cours (gardé par AuditMiddleware) ; s'il agit
pour un autre (agent de terrain → agriculteur), `acting_for` l'indique.
"""

from contextvars import ContextVar
from datetime import date, datetime
from decimal import Decimal

from django.apps import apps
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.db.models.signals import post_save, pre_save

from .models import AuditLog

_current_request = ContextVar("audit_request", default=None)

# Tables surveillées → nom du champ « statut » (pour distinguer les changements de statut).
AUDITED = {
    "accounts.User": "status",
    "core.PlatformSettings": None,
    "finance.Sale": None,
    "finance.Expense": None,
    "inventory.Product": None,
    "inventory.Purchase": None,
    "inventory.StockMovement": None,
    "inventory.SupplierPayment": None,
    "customers.Payment": None,
    "orders.Order": "status",
    "invoices.Invoice": "status",
    "market.Listing": "status",
}
IGNORED_FIELDS = {"created_at", "updated_at", "password", "last_login", "code_hash"}


class AuditMiddleware:
    """Garde la requête en cours pour savoir qui fait l'action (et depuis quelle IP)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _current_request.set(request)
        try:
            return self.get_response(request)
        finally:
            _current_request.reset(token)


def _actor_and_ip():
    request = _current_request.get()
    if request is None:
        return None, None
    user = getattr(request, "user", None)
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR")
    return (user if user is not None and user.is_authenticated else None), ip


def _plain(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool, list, dict)):
        return value
    return str(value)


def _value(field, instance):
    value = field.value_from_object(instance)
    if isinstance(value, Decimal) and getattr(field, "decimal_places", None) is not None:
        # « 400 » en mémoire et « 400.00 » en base sont la même valeur.
        value = value.quantize(Decimal(1).scaleb(-field.decimal_places))
    return _plain(value)


def _snapshot(instance):
    return {
        field.attname: _value(field, instance)
        for field in instance._meta.concrete_fields
        if field.attname not in IGNORED_FIELDS
    }


def _owner_of(instance):
    owner = getattr(instance, "owner", None)
    if owner is None and hasattr(instance, "product_id"):
        owner = instance.product.owner
    return owner


def write(action, instance=None, changes=None, user=None, object_type="", object_repr=""):
    actor, ip = _actor_and_ip()
    actor = user or actor
    owner = _owner_of(instance) if instance is not None else None
    acting_for = owner if owner is not None and actor is not None and owner.pk != actor.pk else None
    return AuditLog.objects.create(
        user=actor,
        acting_for=acting_for,
        action=action,
        object_type=object_type or instance._meta.label,
        object_id=str(instance.pk) if instance is not None else "",
        object_repr=(object_repr or str(instance))[:200],
        changes=changes or {},
        ip_address=ip,
    )


def _remember_old_values(sender, instance, raw=False, **kwargs):
    instance._audit_old = None
    if instance.pk and not raw:
        old = sender._default_manager.filter(pk=instance.pk).first()
        instance._audit_old = _snapshot(old) if old else None


def _record_save(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    new = _snapshot(instance)
    old = getattr(instance, "_audit_old", None)
    if created or old is None:
        write(AuditLog.Action.CREATE, instance, {k: [None, v] for k, v in new.items()})
        return
    changes = {k: [old.get(k), v] for k, v in new.items() if old.get(k) != v}
    if not changes:
        return
    status_field = AUDITED[sender._meta.label]
    if status_field and status_field in changes:
        action = AuditLog.Action.STATUS_CHANGE
    elif changes.get("is_active") == [True, False]:
        action = AuditLog.Action.DELETE
    else:
        action = AuditLog.Action.UPDATE
    write(action, instance, changes)


def _record_login(sender, request, user, **kwargs):
    write(AuditLog.Action.LOGIN, user, user=user)


def _record_login_failed(sender, credentials, request=None, **kwargs):
    phone = str(credentials.get("phone") or credentials.get("username") or "")
    write(
        AuditLog.Action.LOGIN_FAILED,
        changes={"phone": phone},
        object_type="accounts.User",
        object_repr=phone or "inconnu",
    )


def connect():
    for label in AUDITED:
        model = apps.get_model(label)
        pre_save.connect(_remember_old_values, sender=model, dispatch_uid=f"audit-pre-{label}")
        post_save.connect(_record_save, sender=model, dispatch_uid=f"audit-post-{label}")
    user_logged_in.connect(_record_login, dispatch_uid="audit-login")
    user_login_failed.connect(_record_login_failed, dispatch_uid="audit-login-failed")
