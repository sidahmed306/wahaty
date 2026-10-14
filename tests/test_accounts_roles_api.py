"""T04 – Accès par rôle : gestion des comptes (Direction) et agriculteurs d'un agent."""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import AccountStatus, Role, User
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

USERS = "/api/users/"
FARMERS = "/api/agent/farmers/"


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


@pytest.fixture
def direction():
    return UserFactory(roles=[Role.DIRECTION])


@pytest.fixture
def direction_client(direction):
    return client_for(direction)


# --- Gestion des comptes par la Direction ------------------------------------


def test_direction_liste_les_comptes(direction_client):
    UserFactory.create_batch(3)
    response = direction_client.get(USERS)
    assert response.status_code == 200
    assert len(response.data) == 4


def test_filtres_de_la_liste(direction_client):
    UserFactory(status=AccountStatus.PENDING, roles=[Role.SELLER], full_name="Mariem Vall")
    UserFactory(roles=[Role.FARMER], full_name="Cheikh Sidi")
    assert len(direction_client.get(USERS, {"status": "pending"}).data) == 1
    assert len(direction_client.get(USERS, {"role": "seller"}).data) == 1
    assert direction_client.get(USERS, {"search": "mariem"}).data[0]["full_name"] == "Mariem Vall"


def test_valider_un_compte(direction_client):
    user = UserFactory(status=AccountStatus.PENDING)
    response = direction_client.post(f"{USERS}{user.id}/approve/")
    assert response.status_code == 200
    assert response.data["status"] == "approved"


def test_suspendre_un_compte(direction_client):
    user = UserFactory()
    assert direction_client.post(f"{USERS}{user.id}/suspend/").status_code == 200
    user.refresh_from_db()
    assert user.status == AccountStatus.SUSPENDED


def test_desactiver_un_compte_mais_pas_changer_ses_roles(direction_client):
    user = UserFactory(roles=[Role.FARMER])
    response = direction_client.patch(
        f"{USERS}{user.id}/", {"is_active": False, "roles": ["direction"]}, format="json"
    )
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.is_active is False
    assert user.roles == [Role.FARMER]


def test_direction_ne_se_suspend_pas_elle_meme(direction, direction_client):
    assert direction_client.post(f"{USERS}{direction.id}/suspend/").status_code == 403
    direction.refresh_from_db()
    assert direction.status == AccountStatus.APPROVED


@pytest.mark.parametrize("method", ["put", "delete"])
def test_pas_de_remplacement_ni_suppression(direction_client, method):
    user = UserFactory()
    assert getattr(direction_client, method)(f"{USERS}{user.id}/").status_code == 405
    assert User.objects.filter(pk=user.pk).exists()


@pytest.mark.parametrize(
    "roles", [[Role.FARMER], [Role.SELLER], [Role.FIELD_AGENT], [Role.FARMER, Role.SELLER]]
)
def test_autres_roles_interdits_sur_la_gestion_des_comptes(roles):
    user = UserFactory(roles=roles)
    victim = UserFactory(status=AccountStatus.PENDING)
    client = client_for(user)
    assert client.get(USERS).status_code == 403
    assert client.post(f"{USERS}{victim.id}/approve/").status_code == 403
    victim.refresh_from_db()
    assert victim.status == AccountStatus.PENDING


def test_gestion_des_comptes_sans_connexion(db):
    assert APIClient().get(USERS).status_code == 401


# --- Agriculteurs d'un agent -------------------------------------------------


def test_agent_liste_ses_agriculteurs():
    agent = UserFactory(roles=[Role.FIELD_AGENT])
    managed = UserFactory(registered_by=agent, full_name="Ahmed")
    claimed = UserFactory(registered_by=agent, full_name="Brahim", claimed_at=timezone.now())
    UserFactory(registered_by=UserFactory(roles=[Role.FIELD_AGENT]))  # inscrit par un autre agent
    response = client_for(agent).get(FARMERS)
    assert response.status_code == 200
    assert [(r["id"], r["can_edit"]) for r in response.data] == [
        (managed.id, True),
        (claimed.id, False),
    ]


def test_agent_ne_voit_pas_l_agriculteur_d_un_autre():
    agent = UserFactory(roles=[Role.FIELD_AGENT])
    other = UserFactory(registered_by=UserFactory(roles=[Role.FIELD_AGENT]))
    assert client_for(agent).get(f"{FARMERS}{other.id}/").status_code == 404


@pytest.mark.parametrize("roles", [[Role.FARMER], [Role.SELLER], [Role.DIRECTION]])
def test_liste_agent_reservee_aux_agents(roles):
    assert client_for(UserFactory(roles=roles)).get(FARMERS).status_code == 403
