"""T04 – Isolation des données : un utilisateur A ne peut ni lire ni modifier les données de B."""

from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import AccountStatus, Role
from core.access import can_write_for, get_owner, managed_farmers
from core.permissions import IsDirection, role_permission
from tests.factories import UserFactory
from tests.testapp.models import Note

pytestmark = [pytest.mark.django_db, pytest.mark.urls("tests.testapp.urls")]

NOTES = "/api/notes/"


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


@pytest.fixture
def alice():
    return UserFactory(full_name="Alice", roles=[Role.FARMER])


@pytest.fixture
def bob():
    return UserFactory(full_name="Bob", roles=[Role.FARMER, Role.SELLER])


@pytest.fixture
def direction():
    return UserFactory(roles=[Role.DIRECTION])


@pytest.fixture
def agent():
    return UserFactory(roles=[Role.FIELD_AGENT])


@pytest.fixture
def managed(agent):
    """Agriculteur inscrit par l'agent, qui n'a pas encore repris la main."""
    return UserFactory(registered_by=agent, roles=[Role.FARMER])


@pytest.fixture
def claimed(agent):
    """Agriculteur inscrit par l'agent, qui a repris la main sur son compte."""
    return UserFactory(registered_by=agent, roles=[Role.FARMER], claimed_at=timezone.now())


@pytest.fixture
def notes(alice, bob, managed, claimed):
    return SimpleNamespace(
        alice=Note.objects.create(owner=alice, text="note d'Alice"),
        bob=Note.objects.create(owner=bob, text="note de Bob"),
        managed=Note.objects.create(owner=managed, text="note gérée par l'agent"),
        claimed=Note.objects.create(owner=claimed, text="note reprise en main"),
    )


def ids(response):
    return {row["id"] for row in response.data}


# --- A et B ------------------------------------------------------------------


def test_a_ne_voit_que_ses_donnees(alice, notes):
    response = client_for(alice).get(NOTES)
    assert response.status_code == 200
    assert ids(response) == {notes.alice.id}


def test_a_ne_peut_pas_lire_la_donnee_de_b(alice, notes):
    assert client_for(alice).get(f"{NOTES}{notes.bob.id}/").status_code == 404


@pytest.mark.parametrize("method", ["patch", "put", "delete"])
def test_a_ne_peut_pas_modifier_ni_supprimer_la_donnee_de_b(alice, notes, method):
    response = getattr(client_for(alice), method)(
        f"{NOTES}{notes.bob.id}/", {"text": "piraté"}, format="json"
    )
    assert response.status_code == 404
    notes.bob.refresh_from_db()
    assert notes.bob.text == "note de Bob"


def test_a_ne_peut_pas_creer_au_nom_de_b(alice, bob):
    response = client_for(alice).post(NOTES, {"text": "x", "owner": bob.id}, format="json")
    assert response.status_code == 201
    assert Note.objects.get(pk=response.data["id"]).owner == alice


def test_a_modifie_sa_propre_donnee(alice, notes):
    response = client_for(alice).patch(f"{NOTES}{notes.alice.id}/", {"text": "ok"}, format="json")
    assert response.status_code == 200


def test_sans_connexion_refuse(notes):
    assert APIClient().get(NOTES).status_code == 401


@pytest.mark.parametrize("statut", [AccountStatus.PENDING, AccountStatus.SUSPENDED])
def test_compte_non_valide_refuse(statut, notes):
    user = UserFactory(status=statut)
    Note.objects.create(owner=user, text="à moi")
    assert client_for(user).get(NOTES).status_code == 403


# --- Direction ---------------------------------------------------------------


def test_direction_lit_tout(direction, notes):
    client = client_for(direction)
    assert ids(client.get(NOTES)) == {n.id for n in vars(notes).values()}
    assert client.get(f"{NOTES}{notes.bob.id}/").status_code == 200


@pytest.mark.parametrize("method", ["patch", "delete"])
def test_direction_ne_modifie_pas_les_donnees_privees(direction, notes, method):
    response = getattr(client_for(direction), method)(
        f"{NOTES}{notes.bob.id}/", {"text": "x"}, format="json"
    )
    assert response.status_code == 403


def test_direction_ne_cree_pas_de_donnees_privees(direction):
    assert client_for(direction).post(NOTES, {"text": "x"}, format="json").status_code == 403


# --- Agent de terrain --------------------------------------------------------


def test_agent_voit_ses_inscrits_seulement(agent, notes):
    assert ids(client_for(agent).get(NOTES)) == {notes.managed.id, notes.claimed.id}


def test_agent_ne_voit_pas_les_inscrits_d_un_autre_agent(notes, managed):
    other_agent = UserFactory(roles=[Role.FIELD_AGENT])
    client = client_for(other_agent)
    assert ids(client.get(NOTES)) == set()
    assert client.get(f"{NOTES}{notes.managed.id}/").status_code == 404


def test_agent_saisit_pour_son_agriculteur(agent, managed):
    response = client_for(agent).post(
        NOTES, {"text": "récolte", "owner": managed.id}, format="json"
    )
    assert response.status_code == 201
    assert Note.objects.get(pk=response.data["id"]).owner == managed


def test_agent_doit_indiquer_l_agriculteur(agent):
    response = client_for(agent).post(NOTES, {"text": "x"}, format="json")
    assert response.status_code == 400
    assert "owner" in response.data


@pytest.mark.parametrize("cible", ["alice", "claimed", "inconnu", "texte"])
def test_agent_ne_saisit_pas_pour_un_autre(agent, alice, claimed, cible):
    owner = {"alice": alice.id, "claimed": claimed.id, "inconnu": 999999, "texte": "abc"}[cible]
    response = client_for(agent).post(NOTES, {"text": "x", "owner": owner}, format="json")
    assert response.status_code == 403
    assert not Note.objects.filter(text="x").exists()


def test_agent_modifie_tant_que_non_repris(agent, notes):
    url = f"{NOTES}{notes.managed.id}/"
    assert client_for(agent).patch(url, {"text": "corrigé"}, format="json").status_code == 200


def test_agent_en_lecture_seule_apres_reprise(agent, notes):
    url = f"{NOTES}{notes.claimed.id}/"
    client = client_for(agent)
    assert client.get(url).status_code == 200
    assert client.patch(url, {"text": "x"}, format="json").status_code == 403
    assert client.delete(url).status_code == 403


def test_agriculteur_repris_modifie_ses_donnees(claimed, notes):
    url = f"{NOTES}{notes.claimed.id}/"
    assert client_for(claimed).patch(url, {"text": "à moi"}, format="json").status_code == 200


def test_agriculteur_gere_ne_voit_que_ses_donnees(managed, notes):
    assert ids(client_for(managed).get(NOTES)) == {notes.managed.id}


# --- Règles de base ----------------------------------------------------------


def test_agents_geres_sont_seulement_des_agriculteurs(agent, managed):
    UserFactory(registered_by=agent, roles=[Role.SELLER])
    assert list(managed_farmers(agent)) == [managed]


def test_can_write_for_cas_limites(alice, direction):
    assert can_write_for(AnonymousUser(), alice) is False
    assert can_write_for(alice, None) is False
    assert can_write_for(direction, alice) is False
    assert can_write_for(direction, direction) is False


def test_get_owner_suit_un_chemin():
    obj = SimpleNamespace(farm=SimpleNamespace(owner="Alice"))
    assert get_owner(obj, "farm__owner") == "Alice"


def test_permission_par_role():
    assert IsDirection.roles == (Role.DIRECTION,)
    assert role_permission(Role.FARMER, Role.SELLER).__name__ == "HasFarmerOrSeller"
