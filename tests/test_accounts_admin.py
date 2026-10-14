import pytest
from django.test import Client

from accounts.models import AccountStatus, User
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

CHANGELIST = "/admin/accounts/user/"


@pytest.fixture
def admin_client():
    admin = User.objects.create_superuser("46000000", "Oasis-Adrar-2026")
    client = Client()
    client.force_login(admin)
    client.admin = admin
    return client


def test_liste_des_comptes(admin_client):
    UserFactory(full_name="Fatimetou")
    response = admin_client.get(CHANGELIST)
    assert response.status_code == 200
    assert "Fatimetou" in response.content.decode()


def test_valider_des_comptes(admin_client):
    users = UserFactory.create_batch(2, status=AccountStatus.PENDING)
    admin_client.post(
        CHANGELIST, {"action": "approve_accounts", "_selected_action": [u.pk for u in users]}
    )
    assert set(
        User.objects.filter(pk__in=[u.pk for u in users]).values_list("status", flat=True)
    ) == {AccountStatus.APPROVED}


def test_suspendre_sans_se_suspendre_soi_meme(admin_client):
    user = UserFactory()
    admin_client.post(
        CHANGELIST,
        {"action": "suspend_accounts", "_selected_action": [user.pk, admin_client.admin.pk]},
    )
    user.refresh_from_db()
    admin_client.admin.refresh_from_db()
    assert user.status == AccountStatus.SUSPENDED
    assert admin_client.admin.status == AccountStatus.APPROVED


def test_creer_un_compte_depuis_l_admin(admin_client):
    response = admin_client.post(
        f"{CHANGELIST}add/",
        {
            "phone": "+22233000000",
            "full_name": "Agent Brahim",
            "roles": ["field_agent"],
            "password1": "Oasis-Adrar-2026",
            "password2": "Oasis-Adrar-2026",
        },
    )
    assert response.status_code == 302, response.content.decode()[:2000]
    agent = User.objects.get(phone="+22233000000")
    assert agent.roles == ["field_agent"]
    assert agent.profile is not None


def test_fiche_d_un_compte(admin_client):
    user = UserFactory()
    assert admin_client.get(f"{CHANGELIST}{user.pk}/change/").status_code == 200
