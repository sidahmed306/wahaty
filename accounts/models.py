from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models import TimeStampedModel

from .phone import normalize_phone


class Role(models.TextChoices):
    DIRECTION = "direction", "Direction"
    FARMER = "farmer", "Agriculteur"
    SELLER = "seller", "Vendeur"
    FIELD_AGENT = "field_agent", "Agent de terrain"


# Rôles qui ne se combinent avec aucun autre (décision Q2 du schéma T02).
EXCLUSIVE_ROLES = (Role.DIRECTION, Role.FIELD_AGENT)
# Rôles qu'on peut choisir soi-même à l'inscription.
SELF_SIGNUP_ROLES = (Role.FARMER, Role.SELLER)


class AccountStatus(models.TextChoices):
    PENDING = "pending", "En attente de validation"
    APPROVED = "approved", "Validé"
    SUSPENDED = "suspended", "Suspendu"


class Language(models.TextChoices):
    AR = "ar", "العربية"
    FR = "fr", "Français"


def validate_roles(roles):
    if not roles:
        raise ValidationError("Au moins un rôle est obligatoire.", code="no_role")
    unknown = set(roles) - set(Role.values)
    if unknown:
        raise ValidationError(f"Rôle inconnu : {', '.join(sorted(unknown))}.", code="bad_role")
    if len(set(roles)) != len(roles):
        raise ValidationError("Un rôle est répété.", code="duplicate_role")
    for role in EXCLUSIVE_ROLES:
        if role in roles and len(roles) > 1:
            raise ValidationError(
                f"Le rôle « {Role(role).label} » ne se combine avec aucun autre.",
                code="exclusive_role",
            )


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone, password=None, **extra):
        if not phone:
            raise ValueError("Le numéro de téléphone est obligatoire.")
        user = self.model(phone=normalize_phone(phone), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra):
        extra.setdefault("full_name", "Direction")
        extra.update(
            roles=[Role.DIRECTION],
            status=AccountStatus.APPROVED,
            is_staff=True,
            is_superuser=True,
        )
        return self.create_user(phone, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    phone = models.CharField("téléphone", max_length=13, unique=True)
    full_name = models.CharField("nom complet", max_length=150)
    roles = ArrayField(
        models.CharField(max_length=20, choices=Role.choices),
        verbose_name="rôles",
        validators=[validate_roles],
    )
    preferred_language = models.CharField(
        "langue préférée", max_length=2, choices=Language.choices, default=Language.AR
    )
    status = models.CharField(
        "statut du compte",
        max_length=10,
        choices=AccountStatus.choices,
        default=AccountStatus.PENDING,
    )
    registered_by = models.ForeignKey(
        "self",
        verbose_name="inscrit par (agent)",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="registered_farmers",
    )
    claimed_at = models.DateTimeField("repris en main le", null=True, blank=True)
    is_active = models.BooleanField("actif", default=True)
    is_staff = models.BooleanField("accès administration", default=False)
    date_joined = models.DateTimeField("inscrit le", default=timezone.now)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"
        constraints = [
            models.CheckConstraint(condition=Q(roles__len__gte=1), name="user_has_role"),
            *(
                models.CheckConstraint(
                    condition=~Q(roles__contains=[role]) | Q(roles__len=1),
                    name=f"user_{role}_role_exclusive",
                )
                for role in EXCLUSIVE_ROLES
            ),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.phone})"

    def clean(self):
        super().clean()
        if self.phone:
            self.phone = normalize_phone(self.phone)

    def has_role(self, role):
        return role in self.roles

    @property
    def is_approved(self):
        return self.status == AccountStatus.APPROVED


class Profile(TimeStampedModel):
    """Informations complémentaires. Le lien vers l'oasis et la photo arrivent à T05."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    whatsapp = models.CharField("WhatsApp", max_length=13, blank=True)
    address = models.TextField("adresse", blank=True)
    business_name = models.CharField("nom de la boutique", max_length=150, blank=True)

    class Meta:
        verbose_name = "profil"
        verbose_name_plural = "profils"

    def __str__(self):
        return f"Profil de {self.user}"
