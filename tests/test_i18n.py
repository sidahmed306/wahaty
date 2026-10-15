"""T14 – Messages de l'API dans la langue choisie (arabe par défaut) ; connexion de 30 jours."""

import re
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import AccountStatus, Role
from customers.models import Customer
from orders import services as order_services
from tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db

PO_FILE = Path(settings.BASE_DIR) / "locale" / "ar" / "LC_MESSAGES" / "django.po"
ARABIC = re.compile("[؀-ۿ]")


def register(phone, password, roles, lang):
    return (
        APIClient()
        .post(
            "/api/auth/register/",
            {"phone": phone, "full_name": "Test", "password": password, "roles": roles},
            format="json",
            HTTP_ACCEPT_LANGUAGE=lang,
        )
        .data
    )


def test_message_en_arabe_ou_en_francais_selon_la_langue():
    UserFactory(phone="+22247000001")
    assert register("47000001", "Palmier-2026", ["farmer"], "ar")["phone"] == [
        "هذا الرقم مستخدم من قبل."
    ]
    assert register("47000001", "Palmier-2026", ["farmer"], "fr")["phone"] == [
        "Ce numéro est déjà utilisé."
    ]


def test_messages_de_django_et_drf_aussi_en_arabe():
    assert ARABIC.search(register("47000002", "x", [], "ar")["roles"][0])  # DRF : liste vide
    weak = register("47000002", "123", ["farmer"], "ar")["password"]  # Django : mot de passe
    assert weak and all(ARABIC.search(m) for m in weak)


def test_arabe_par_defaut_sans_langue_demandee(settings):
    settings.LANGUAGE_CODE = "ar"
    user = UserFactory(status=AccountStatus.PENDING)
    response = APIClient().post(
        "/api/auth/login/", {"phone": user.phone, "password": DEFAULT_PASSWORD}, format="json"
    )
    assert response.status_code == 403
    assert response.data["detail"] == "حسابك في انتظار مصادقة الإدارة."


def test_message_avec_valeurs_et_statut_traduit():
    seller = UserFactory(roles=[Role.SELLER])
    customer = Customer.objects.create(owner=seller, name="Khadija")
    order = order_services.create_order(
        seller, customer, [], seller, expected_delivery_date=timezone.localdate()
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(seller)}")
    data = client.post(
        f"/api/orders/{order.id}/status/",
        {"status": "delivered"},
        format="json",
        HTTP_ACCEPT_LANGUAGE="ar",
    ).data
    assert "«مستلمة» ← «مسلّمة»" in str(data)


def test_toutes_les_phrases_sont_traduites_en_arabe():
    po = PO_FILE.read_text(encoding="utf-8")
    entries = re.findall(r'\nmsgid "(.+)"\nmsgstr "(.*)"\n', po)
    assert len(entries) > 60
    assert [msgid for msgid, msgstr in entries if not msgstr] == []
    assert "#, fuzzy" not in po
    assert PO_FILE.with_suffix(".mo").exists()


def test_connexion_valable_30_jours():
    assert settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"] == timedelta(days=30)
    assert settings.LANGUAGES[0][0] == "ar"
