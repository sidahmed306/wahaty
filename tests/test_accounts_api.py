from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from accounts.models import AccountStatus, Role, User
from tests.factories import DEFAULT_PASSWORD, UserFactory

REGISTER = "/api/auth/register/"
LOGIN = "/api/auth/login/"
REFRESH = "/api/auth/refresh/"
LOGOUT = "/api/auth/logout/"
ME = "/api/auth/me/"

pytestmark = pytest.mark.django_db


def bearer(client, token):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def login(client, phone, password=DEFAULT_PASSWORD):
    return client.post(LOGIN, {"phone": phone, "password": password}, format="json")


# --- Inscription -------------------------------------------------------------


def register_payload(**overrides):
    data = {
        "phone": "22 12 34 56",
        "full_name": "Mohamed Lemine",
        "password": "Palmier-Atar-77",
        "roles": ["farmer"],
    }
    data.update(overrides)
    return data


def test_inscription_ok_compte_en_attente(api_client):
    response = api_client.post(REGISTER, register_payload(), format="json")
    assert response.status_code == 201, response.data
    assert response.data["status"] == "pending"
    assert "password" not in response.data
    user = User.objects.get(phone="+22222123456")
    assert user.check_password("Palmier-Atar-77")
    assert user.roles == ["farmer"]


def test_inscription_agriculteur_et_vendeur(api_client):
    response = api_client.post(
        REGISTER, register_payload(roles=["farmer", "seller"]), format="json"
    )
    assert response.status_code == 201
    assert response.data["roles"] == ["farmer", "seller"]


@pytest.mark.parametrize(
    "mot_de_passe",
    ["Ab1-x", "12345678", "password123", "azertyuiop", "Mohamed Lemine"],
    ids=["trop-court", "que-des-chiffres", "trop-courant", "trop-courant-fr", "comme-le-nom"],
)
def test_mot_de_passe_faible_refuse(api_client, mot_de_passe):
    response = api_client.post(REGISTER, register_payload(password=mot_de_passe), format="json")
    assert response.status_code == 400
    assert "password" in response.data
    assert not User.objects.exists()


@pytest.mark.parametrize("roles", [["direction"], ["field_agent"], [], ["farmer", "farmer"]])
def test_inscription_roles_interdits(api_client, roles):
    response = api_client.post(REGISTER, register_payload(roles=roles), format="json")
    assert response.status_code == 400
    assert "roles" in response.data


def test_inscription_numero_deja_pris_meme_ecrit_autrement(api_client):
    UserFactory(phone="+22222123456")
    response = api_client.post(REGISTER, register_payload(phone="0022222123456"), format="json")
    assert response.status_code == 400
    assert "phone" in response.data


def test_inscription_numero_invalide(api_client):
    response = api_client.post(REGISTER, register_payload(phone="0612345678"), format="json")
    assert response.status_code == 400
    assert "phone" in response.data


# --- Connexion ---------------------------------------------------------------


def test_connexion_ok(api_client, user):
    response = login(api_client, user.phone)
    assert response.status_code == 200
    assert {"access", "refresh"} <= response.data.keys()
    user.refresh_from_db()
    assert user.last_login is not None


def test_connexion_ok_numero_ecrit_autrement(api_client):
    UserFactory(phone="+22233445566")
    assert login(api_client, "33 44 55 66").status_code == 200


def test_connexion_mauvais_mot_de_passe(api_client, user):
    response = login(api_client, user.phone, "Mauvais-mot-2026")
    assert response.status_code == 401
    assert "access" not in response.data


def test_connexion_numero_inconnu(api_client, db):
    assert login(api_client, "22999999").status_code == 401


def test_connexion_numero_mal_ecrit(api_client, db):
    assert login(api_client, "abc").status_code == 401


def test_connexion_compte_desactive(api_client):
    user = UserFactory(is_active=False)
    assert login(api_client, user.phone).status_code == 401


@pytest.mark.parametrize(
    ("statut", "code"),
    [(AccountStatus.PENDING, "account_pending"), (AccountStatus.SUSPENDED, "account_suspended")],
)
def test_connexion_compte_non_valide(api_client, statut, code):
    user = UserFactory(status=statut)
    response = login(api_client, user.phone)
    assert response.status_code == 403
    assert response.data["detail"].code == code
    assert "access" not in response.data


def test_trop_de_tentatives_bloquees(api_client, user):
    for _ in range(5):
        assert login(api_client, user.phone, "Mauvais-mot-2026").status_code == 401
    response = login(api_client, user.phone)
    assert response.status_code == 429


# --- Jetons ------------------------------------------------------------------


def test_sans_jeton_refuse(api_client, db):
    assert api_client.get(ME).status_code == 401


def test_jeton_access_valide(api_client, user):
    bearer(api_client, login(api_client, user.phone).data["access"])
    response = api_client.get(ME)
    assert response.status_code == 200
    assert response.data["phone"] == user.phone


def test_jeton_access_expire_refuse(api_client, user):
    token = AccessToken.for_user(user)
    token.set_exp(from_time=timezone.now() - timedelta(hours=1))
    bearer(api_client, token)
    response = api_client.get(ME)
    assert response.status_code == 401
    assert response.data["code"] == "token_not_valid"


def test_jeton_falsifie_refuse(api_client, user):
    token = str(AccessToken.for_user(user))
    bearer(api_client, token[:-3] + ("aaa" if not token.endswith("aaa") else "bbb"))
    assert api_client.get(ME).status_code == 401


def test_compte_suspendu_perd_acces_immediatement(api_client, user):
    bearer(api_client, AccessToken.for_user(user))
    assert api_client.get(ME).status_code == 200
    User.objects.filter(pk=user.pk).update(status=AccountStatus.SUSPENDED)
    response = api_client.get(ME)
    assert response.status_code == 403
    assert response.data["detail"].code == "account_suspended"


def test_rafraichissement_ok_et_rotation(api_client, user):
    refresh = login(api_client, user.phone).data["refresh"]
    response = api_client.post(REFRESH, {"refresh": refresh}, format="json")
    assert response.status_code == 200
    assert {"access", "refresh"} <= response.data.keys()
    # L'ancien jeton « refresh » ne sert plus (liste noire après rotation).
    assert api_client.post(REFRESH, {"refresh": refresh}, format="json").status_code == 401


def test_rafraichissement_jeton_expire_refuse(api_client, user):
    refresh = RefreshToken.for_user(user)
    refresh.set_exp(from_time=timezone.now() - timedelta(days=30))
    assert api_client.post(REFRESH, {"refresh": str(refresh)}, format="json").status_code == 401


def test_rafraichissement_jeton_invalide_refuse(api_client, db):
    assert api_client.post(REFRESH, {"refresh": "n-importe-quoi"}, format="json").status_code == 401


def test_rafraichissement_refuse_si_compte_suspendu(api_client, user):
    refresh = str(RefreshToken.for_user(user))
    User.objects.filter(pk=user.pk).update(status=AccountStatus.SUSPENDED)
    assert api_client.post(REFRESH, {"refresh": refresh}, format="json").status_code == 403


# --- Déconnexion -------------------------------------------------------------


def test_deconnexion_invalide_le_refresh(api_client, user):
    tokens = login(api_client, user.phone).data
    bearer(api_client, tokens["access"])
    assert api_client.post(LOGOUT, {"refresh": tokens["refresh"]}, format="json").status_code == 205
    response = api_client.post(REFRESH, {"refresh": tokens["refresh"]}, format="json")
    assert response.status_code == 401


def test_deconnexion_avec_le_jeton_d_un_autre_refusee(auth_client):
    other = UserFactory()
    other_refresh = str(RefreshToken.for_user(other))
    response = auth_client.post(LOGOUT, {"refresh": other_refresh}, format="json")
    assert response.status_code == 400


def test_deconnexion_jeton_invalide(auth_client):
    assert auth_client.post(LOGOUT, {"refresh": "abc"}, format="json").status_code == 400


def test_deconnexion_sans_connexion_refusee(api_client, db):
    assert api_client.post(LOGOUT, {"refresh": "abc"}, format="json").status_code == 401


# --- Mon compte --------------------------------------------------------------


def test_mon_compte_modifiable(auth_client, user):
    response = auth_client.patch(
        ME,
        {
            "full_name": "Sidi Ahmed",
            "preferred_language": "fr",
            "profile": {"whatsapp": "36 00 11 22", "business_name": "Dattes de Tidjikja"},
        },
        format="json",
    )
    assert response.status_code == 200, response.data
    user.refresh_from_db()
    assert user.full_name == "Sidi Ahmed"
    assert user.preferred_language == "fr"
    assert user.profile.whatsapp == "+22236001122"
    assert user.profile.business_name == "Dattes de Tidjikja"


def test_mon_compte_roles_et_statut_non_modifiables(auth_client, user):
    response = auth_client.patch(
        ME, {"roles": ["direction"], "status": "approved", "phone": "+22244444444"}, format="json"
    )
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.roles == [Role.FARMER]
    assert user.phone != "+22244444444"


def test_mon_compte_whatsapp_invalide(auth_client):
    response = auth_client.patch(ME, {"profile": {"whatsapp": "999"}}, format="json")
    assert response.status_code == 400


def test_mon_compte_put_interdit(auth_client):
    assert auth_client.put(ME, {}, format="json").status_code == 405
