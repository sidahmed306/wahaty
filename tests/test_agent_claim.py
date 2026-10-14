"""T06 – Inscription d'un agriculteur par un agent, puis reprise en main du compte."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.claims import CODE_ALPHABET, CODE_LENGTH
from accounts.models import AccountClaim, AccountStatus, Role, User
from farms.models import Farm
from oases.models import Oasis, Region
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

AGENT_FARMERS, CLAIM, LOGIN = "/api/agent/farmers/", "/api/auth/claim/", "/api/auth/login/"
NEW_PASSWORD = "Palmeraie-Terjit-9"


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


@pytest.fixture
def agent():
    return UserFactory(roles=[Role.FIELD_AGENT])


@pytest.fixture
def oasis():
    return Oasis.objects.create(
        region=Region.objects.get(slug="ouadane"), name_ar="وادان", name_fr="Ouadane"
    )


@pytest.fixture
def inscription(agent, oasis):
    response = client_for(agent).post(
        AGENT_FARMERS,
        {"phone": "46 12 34 56", "full_name": "Ely Cheikh", "oasis": oasis.id},
        format="json",
    )
    assert response.status_code == 201, response.data
    return response.data


def claim(phone="46123456", code="", password=NEW_PASSWORD):
    return APIClient().post(
        CLAIM, {"phone": phone, "code": code, "password": password}, format="json"
    )


# --- Inscription par l'agent ---------------------------------------------------


def test_agent_inscrit_un_agriculteur(agent, oasis, inscription):
    farmer = User.objects.get(phone="+22246123456")
    assert farmer.roles == [Role.FARMER]
    assert farmer.registered_by == agent
    assert farmer.status == AccountStatus.PENDING  # validation par la Direction (Q3)
    assert farmer.claimed_at is None
    assert not farmer.has_usable_password()
    assert farmer.profile.oasis == oasis
    assert inscription["can_edit"] is True
    code = inscription["claim_code"]
    assert len(code) == CODE_LENGTH and set(code) <= set(CODE_ALPHABET)
    assert code not in AccountClaim.objects.get(user=farmer).code_hash  # stocké haché


def test_inscription_sans_oasis(agent):
    response = client_for(agent).post(
        AGENT_FARMERS, {"phone": "46000011", "full_name": "Sans Oasis"}, format="json"
    )
    assert response.status_code == 201
    assert User.objects.get(phone="+22246000011").profile.oasis is None


def test_numero_deja_pris(agent):
    UserFactory(phone="+22246123456")
    response = client_for(agent).post(
        AGENT_FARMERS, {"phone": "46123456", "full_name": "X"}, format="json"
    )
    assert response.status_code == 400
    assert "phone" in response.data


@pytest.mark.parametrize("roles", [[Role.FARMER], [Role.SELLER], [Role.DIRECTION]])
def test_seul_un_agent_peut_inscrire(roles):
    response = client_for(UserFactory(roles=roles)).post(
        AGENT_FARMERS, {"phone": "46123456", "full_name": "X"}, format="json"
    )
    assert response.status_code == 403


def test_l_agriculteur_inscrit_ne_peut_pas_se_connecter_sans_reprise(inscription):
    User.objects.filter(phone="+22246123456").update(status=AccountStatus.APPROVED)
    response = APIClient().post(LOGIN, {"phone": "46123456", "password": ""}, format="json")
    assert response.status_code in (400, 401)


# --- Reprise en main -----------------------------------------------------------


def test_reprise_en_main(agent, inscription):
    code = inscription["claim_code"]
    response = claim(phone="+222 46 12 34 56", code=f" {code[:4].lower()}-{code[4:]} ")
    assert response.status_code == 200, response.data
    farmer = User.objects.get(phone="+22246123456")
    assert farmer.claimed_at is not None
    assert farmer.check_password(NEW_PASSWORD)
    assert not AccountClaim.objects.filter(user=farmer).exists()
    # Après validation par la Direction, il se connecte avec SON mot de passe.
    User.objects.filter(pk=farmer.pk).update(status=AccountStatus.APPROVED)
    login = APIClient().post(LOGIN, {"phone": "46123456", "password": NEW_PASSWORD}, format="json")
    assert login.status_code == 200
    # Et l'agent passe en lecture seule sur ses données.
    farm = Farm.objects.create(
        owner=farmer, oasis=Oasis.objects.get(), name="Ferme d'Ely", created_by=agent
    )
    agent_client = client_for(agent)
    assert agent_client.get(f"/api/farms/{farm.id}/").status_code == 200
    assert (
        agent_client.patch(f"/api/farms/{farm.id}/", {"name": "x"}, format="json").status_code
        == 403
    )
    assert agent_client.get(AGENT_FARMERS).data[0]["can_edit"] is False


def test_code_utilisable_une_seule_fois(inscription):
    code = inscription["claim_code"]
    assert claim(code=code).status_code == 200
    assert claim(code=code, password="Autre-Mot-De-Passe-1").status_code == 400


@pytest.mark.parametrize("cas", ["mauvais_code", "numero_inconnu", "expire"])
def test_reprise_refusee(inscription, cas):
    code = inscription["claim_code"]
    if cas == "mauvais_code":
        response = claim(code="AAAAAAAA" if code != "AAAAAAAA" else "BBBBBBBB")
    elif cas == "numero_inconnu":
        response = claim(phone="46999999", code=code)
    else:
        AccountClaim.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
        response = claim(code=code)
    assert response.status_code == 400
    assert User.objects.get(phone="+22246123456").claimed_at is None


def test_reprise_mot_de_passe_faible_refuse(inscription):
    response = claim(code=inscription["claim_code"], password="12345678")
    assert response.status_code == 400
    assert "password" in response.data


def test_reprise_numero_mal_ecrit(inscription):
    assert claim(phone="abc", code=inscription["claim_code"]).status_code == 400


def test_reprise_d_un_compte_sans_code(db):
    UserFactory(phone="+22246000022")
    assert claim(phone="46000022", code="ABCDEFGH").status_code == 400


# --- Nouveau code ----------------------------------------------------------------


def test_nouveau_code_remplace_l_ancien(agent, inscription):
    farmer_id = inscription["id"]
    response = client_for(agent).post(f"{AGENT_FARMERS}{farmer_id}/claim-code/")
    assert response.status_code == 200
    new_code = response.data["claim_code"]
    assert claim(code=inscription["claim_code"]).status_code == 400
    assert claim(code=new_code).status_code == 200


def test_pas_de_nouveau_code_apres_reprise(agent, inscription):
    claim(code=inscription["claim_code"])
    response = client_for(agent).post(f"{AGENT_FARMERS}{inscription['id']}/claim-code/")
    assert response.status_code == 400


def test_un_autre_agent_ne_peut_pas_generer_de_code(inscription):
    other = client_for(UserFactory(roles=[Role.FIELD_AGENT]))
    assert other.post(f"{AGENT_FARMERS}{inscription['id']}/claim-code/").status_code == 404


def test_texte_lisible(inscription):
    assert str(AccountClaim.objects.get()).startswith("Code de reprise de Ely Cheikh")
