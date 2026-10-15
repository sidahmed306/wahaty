from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import AccountStatus

STATUS_ERRORS = {
    AccountStatus.PENDING: (
        _("Votre compte attend la validation de la Direction."),
        "account_pending",
    ),
    AccountStatus.SUSPENDED: (_("Votre compte est suspendu."), "account_suspended"),
}


def check_account_status(user):
    """Refuse l'accès si le compte n'est pas validé (en attente ou suspendu)."""
    if user.status in STATUS_ERRORS:
        message, code = STATUS_ERRORS[user.status]
        raise exceptions.PermissionDenied(message, code=code)


class ApprovedUserJWTAuthentication(JWTAuthentication):
    """JWT + vérification du statut à chaque requête.

    Un compte suspendu perd l'accès immédiatement, même avec un jeton encore valide.
    """

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        check_account_status(user)
        return user
