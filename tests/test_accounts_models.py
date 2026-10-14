import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from accounts.models import AccountStatus, Profile, Role, User, validate_roles
from accounts.phone import normalize_phone
from tests.factories import UserFactory


@pytest.mark.parametrize(
    "saisie",
    ["22123456", "22 12 34 56", "+222 22 12 34 56", "0022222123456", "22-12-34-56"],
)
def test_numero_normalise(saisie):
    assert normalize_phone(saisie) == "+22222123456"


@pytest.mark.parametrize(
    "saisie",
    ["", "1234567", "123456789", "52123456", "+33612345678", "2212345a", "+222 9123 4567"],
)
def test_numero_invalide_refuse(saisie):
    with pytest.raises(ValidationError):
        normalize_phone(saisie)


@pytest.mark.django_db
def test_create_user_normalise_et_hache():
    user = User.objects.create_user(
        "36 11 22 33", "Oasis-Adrar-2026", full_name="Ahmed", roles=["farmer"]
    )
    assert user.phone == "+22236112233"
    assert user.password != "Oasis-Adrar-2026"
    assert user.check_password("Oasis-Adrar-2026")
    assert user.status == AccountStatus.PENDING
    assert user.preferred_language == "ar"


@pytest.mark.django_db
def test_create_user_sans_telephone_refuse():
    with pytest.raises(ValueError):
        User.objects.create_user("", "x")


@pytest.mark.django_db
def test_profil_cree_automatiquement():
    user = UserFactory()
    assert Profile.objects.filter(user=user).count() == 1
    assert str(user.profile).startswith("Profil de")


@pytest.mark.django_db
def test_superuser_est_direction_valide():
    admin = User.objects.create_superuser("46000000", "Oasis-Adrar-2026")
    assert admin.roles == [Role.DIRECTION]
    assert admin.status == AccountStatus.APPROVED
    assert admin.is_staff and admin.is_superuser
    assert admin.is_approved
    assert admin.has_role(Role.DIRECTION)


@pytest.mark.django_db
def test_agriculteur_et_vendeur_possible():
    user = UserFactory(roles=[Role.FARMER, Role.SELLER])
    assert user.has_role(Role.FARMER) and user.has_role(Role.SELLER)
    assert "+222" in str(user)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "roles",
    [[], [Role.DIRECTION, Role.FARMER], [Role.FIELD_AGENT, Role.SELLER]],
)
def test_base_refuse_roles_interdits(roles):
    with pytest.raises(IntegrityError), transaction.atomic():
        UserFactory(roles=roles)


@pytest.mark.parametrize(
    ("roles", "code"),
    [
        ([], "no_role"),
        (["pirate"], "bad_role"),
        (["farmer", "farmer"], "duplicate_role"),
        (["direction", "seller"], "exclusive_role"),
        (["field_agent", "farmer"], "exclusive_role"),
    ],
)
def test_validation_des_roles(roles, code):
    with pytest.raises(ValidationError) as exc:
        validate_roles(roles)
    assert exc.value.code == code


@pytest.mark.django_db
def test_clean_normalise_le_telephone():
    user = UserFactory.build(phone="22 33 44 55")
    user.clean()
    assert user.phone == "+22222334455"
