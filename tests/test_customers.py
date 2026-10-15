"""T09 – Clients, dettes et classement automatique (segments testés avec des dates simulées)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import Role, User
from core.models import PlatformSettings
from customers import stats as customer_stats
from customers.models import Customer, Payment
from customers.segments import CustomerStats, Segment, classify
from tests.factories import UserFactory

CUSTOMERS, PAYMENTS, SETTINGS = "/api/customers/", "/api/customer-payments/", "/api/settings/"
TODAY = date(2026, 10, 14)


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


def ago(*days):
    return [TODAY - timedelta(days=d) for d in days]


def seg(days, total="0", **settings):
    config = PlatformSettings(**settings)  # valeurs par défaut : 100 000 / 30 / 3 / 180 / 90
    return classify(CustomerStats(ago(*days), Decimal(total)), config, TODAY)


# --- Règles de classement (dates simulées) ---------------------------------------


def test_sans_commande_nouveau():
    assert seg([]) == Segment.NEW


@pytest.mark.parametrize(("days", "expected"), [(0, "new"), (29, "new"), (30, "occasional")])
def test_nouveau_moins_de_30_jours(days, expected):
    assert seg([days]) == expected


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        ([10, 50, 100], "loyal"),
        ([1, 2, 180], "loyal"),  # 180 jours : encore dans les 6 derniers mois
        # 181 jours : seulement 2 commandes récentes (pas fidèle), première trop ancienne
        # (pas nouveau), dernière hier (pas inactif) → occasionnel.
        ([1, 2, 181], "occasional"),
    ],
)
def test_fidele_3_commandes_sur_6_mois(days, expected):
    assert seg(days) == expected


@pytest.mark.parametrize(
    ("days", "expected"), [(89, "occasional"), (90, "inactive"), (400, "inactive")]
)
def test_inactif_apres_90_jours(days, expected):
    assert seg([days, 200]) == expected


@pytest.mark.parametrize(("total", "expected"), [("100000.00", "premium"), ("99999.99", "loyal")])
def test_premium_fidele_au_dessus_du_seuil(total, expected):
    assert seg([5, 20, 60], total) == expected


def test_premium_exige_d_etre_fidele():
    assert seg([5, 200], "500000") == Segment.OCCASIONAL


def test_inactif_prioritaire_sur_premium():
    assert seg([95, 100, 120], "500000") == Segment.INACTIVE


def test_fidele_prioritaire_sur_nouveau():
    assert seg([1, 3, 10]) == Segment.LOYAL


def test_seuils_reglables():
    assert seg([5, 20, 60], "5000", premium_threshold=Decimal("1000")) == Segment.PREMIUM
    assert seg([40], inactive_days=30) == Segment.INACTIVE
    assert seg([40], new_customer_days=60) == Segment.NEW
    assert seg([5, 20], loyal_min_orders=2) == Segment.LOYAL
    assert seg([5, 20, 200], loyal_period_days=365) == Segment.LOYAL


def test_dates_de_premiere_et_derniere_commande():
    stats = CustomerStats(ago(5, 50, 20))
    assert stats.first_order == TODAY - timedelta(days=50)
    assert stats.last_order == TODAY - timedelta(days=5)
    assert CustomerStats().first_order is None


# --- API clients ---------------------------------------------------------------------


@pytest.fixture
def seller(db):
    return UserFactory(roles=[Role.SELLER])


@pytest.fixture
def client(seller):
    return client_for(seller)


@pytest.fixture
def khadija(seller):
    return Customer.objects.create(owner=seller, name="Khadija", phone="+22236112233")


@pytest.mark.django_db
def test_creer_un_client(client):
    response = client.post(
        CUSTOMERS,
        {"name": "Moussa", "phone": "22 44 55 66", "whatsapp": "46 44 55 66", "city": "Atar"},
        format="json",
    )
    assert response.status_code == 201, response.data
    assert response.data["phone"] == "+22222445566"
    assert response.data["whatsapp"] == "+22246445566"
    assert response.data["segment"] == "new"
    assert (response.data["balance"], response.data["orders_count"]) == ("0.00", 0)


@pytest.mark.django_db
def test_meme_numero_refuse_chez_le_meme_vendeur(client, khadija):
    response = client.post(CUSTOMERS, {"name": "X", "phone": "36112233"}, format="json")
    assert response.status_code == 400
    assert (
        client.patch(f"{CUSTOMERS}{khadija.id}/", {"phone": "36112233"}, format="json").status_code
        == 200
    )
    other = client_for(UserFactory(roles=[Role.SELLER]))
    assert (
        other.post(CUSTOMERS, {"name": "X", "phone": "36112233"}, format="json").status_code == 201
    )


@pytest.mark.django_db
def test_recherche(client, khadija):
    Customer.objects.create(owner=khadija.owner, name="Brahim")
    assert [c["name"] for c in client.get(CUSTOMERS, {"search": "khad"}).data] == ["Khadija"]
    assert [c["name"] for c in client.get(CUSTOMERS, {"search": "3611"}).data] == ["Khadija"]


@pytest.mark.django_db
def test_segment_et_filtre_branches_sur_les_commandes(client, seller, monkeypatch):
    """Simule les commandes (T10) pour vérifier le branchement : segment, filtre, réglages."""
    loyal = Customer.objects.create(owner=seller, name="Fidèle")
    old = Customer.objects.create(owner=seller, name="Ancien")
    fake = {
        loyal.pk: CustomerStats(ago(1, 5, 9), Decimal("60000")),
        old.pk: CustomerStats(ago(120), Decimal("2000")),
    }
    monkeypatch.setattr(customer_stats.timezone, "localdate", lambda: TODAY)
    monkeypatch.setattr(
        customer_stats, "order_stats", lambda ids: {pk: fake.get(pk, CustomerStats()) for pk in ids}
    )
    data = {c["name"]: c for c in client.get(CUSTOMERS).data}
    assert data["Fidèle"]["segment"] == "loyal"
    assert data["Fidèle"]["orders_count"] == 3
    assert data["Fidèle"]["total_purchased"] == "60000.00"
    assert data["Fidèle"]["balance"] == "60000.00"
    assert data["Ancien"]["segment"] == "inactive"
    assert [c["name"] for c in client.get(CUSTOMERS, {"segment": "inactive"}).data] == ["Ancien"]
    # La Direction baisse le seuil Premium : le classement change sans toucher au code.
    direction = client_for(UserFactory(roles=[Role.DIRECTION]))
    assert (
        direction.patch(SETTINGS, {"premium_threshold": "50000"}, format="json").status_code == 200
    )
    assert client.get(f"{CUSTOMERS}{loyal.id}/").data["segment"] == "premium"


@pytest.mark.django_db
def test_segment_inconnu_refuse(client):
    assert client.get(CUSTOMERS, {"segment": "vip"}).status_code == 400


# --- Paiements et dette ----------------------------------------------------------


@pytest.mark.django_db
def test_paiement_et_avance(client, khadija):
    response = client.post(
        PAYMENTS,
        {
            "customer": khadija.id,
            "payment_date": "2026-10-01",
            "amount": "1500.50",
            "method": "masrvi",
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    data = client.get(f"{CUSTOMERS}{khadija.id}/").data
    assert (data["paid_total"], data["balance"]) == ("1500.50", "-1500.50")  # avance
    payment = Payment.objects.get()
    assert payment.owner == khadija.owner and payment.created_by == khadija.owner


@pytest.mark.django_db
def test_annuler_un_paiement(client, khadija):
    payment = Payment.objects.create(
        owner=khadija.owner,
        customer=khadija,
        payment_date=date(2026, 10, 1),
        amount=Decimal("300"),
        created_by=khadija.owner,
    )
    assert client.delete(f"{PAYMENTS}{payment.id}/").status_code == 204
    assert Payment.objects.filter(pk=payment.pk).exists()
    assert client.get(f"{CUSTOMERS}{khadija.id}/").data["balance"] == "0.00"
    assert client.patch(f"{PAYMENTS}{payment.id}/", {"amount": "1"}, format="json").status_code in (
        404,
        405,
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"amount": "0"}, "amount"),
        ({"amount": "-50"}, "amount"),
        ({"amount": "1.005"}, "amount"),
        ({"payment_date": str(timezone.localdate() + timedelta(days=1))}, "payment_date"),
        ({"method": "carte"}, "method"),
    ],
)
def test_paiement_invalide(client, khadija, changes, field):
    payload = {"customer": khadija.id, "payment_date": "2026-10-01", "amount": "100", **changes}
    response = client.post(PAYMENTS, payload, format="json")
    assert response.status_code == 400
    assert field in response.data


@pytest.mark.django_db
def test_client_avec_dette_ou_avance_non_supprimable(client, khadija):
    Payment.objects.create(
        owner=khadija.owner,
        customer=khadija,
        payment_date=date(2026, 10, 1),
        amount=Decimal("10"),
        created_by=khadija.owner,
    )
    assert client.delete(f"{CUSTOMERS}{khadija.id}/").status_code == 400
    empty = Customer.objects.create(owner=khadija.owner, name="Sans dette")
    assert client.delete(f"{CUSTOMERS}{empty.id}/").status_code == 204
    assert client.get(f"{CUSTOMERS}{empty.id}/").status_code == 404


# --- Isolation et rôles ----------------------------------------------------------


@pytest.mark.django_db
def test_un_autre_vendeur_ne_voit_rien(khadija):
    other = client_for(UserFactory(roles=[Role.SELLER]))
    assert other.get(CUSTOMERS).data == []
    assert other.get(f"{CUSTOMERS}{khadija.id}/").status_code == 404
    assert other.patch(f"{CUSTOMERS}{khadija.id}/", {"name": "x"}, format="json").status_code == 404
    response = other.post(
        PAYMENTS,
        {"customer": khadija.id, "payment_date": "2026-10-01", "amount": "5"},
        format="json",
    )
    assert response.status_code == 400 and "customer" in response.data
    assert not Payment.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("roles", [[Role.FARMER], [Role.FIELD_AGENT]])
def test_clients_reserves_aux_vendeurs(roles):
    client = client_for(UserFactory(roles=roles))
    assert client.get(CUSTOMERS).status_code == 403
    assert client.get(PAYMENTS).status_code == 403


@pytest.mark.django_db
def test_direction_lit_mais_n_ecrit_pas(khadija):
    direction = client_for(UserFactory(roles=[Role.DIRECTION]))
    assert [c["name"] for c in direction.get(CUSTOMERS).data] == ["Khadija"]
    assert direction.post(CUSTOMERS, {"name": "x"}, format="json").status_code == 403


# --- Réglages de la Direction ----------------------------------------------------


@pytest.mark.django_db
def test_reglages_lisibles_par_tout_compte(client):
    data = client.get(SETTINGS).data
    assert data["premium_threshold"] == "100000.00"
    assert (
        data["new_customer_days"],
        data["loyal_min_orders"],
        data["loyal_period_days"],
        data["inactive_days"],
    ) == (
        30,
        3,
        180,
        90,
    )
    assert APIClient().get(SETTINGS).status_code == 401


@pytest.mark.django_db
def test_seule_la_direction_modifie_les_reglages(client):
    assert client.patch(SETTINGS, {"inactive_days": 60}, format="json").status_code == 403
    direction = client_for(UserFactory(roles=[Role.DIRECTION]))
    assert direction.patch(SETTINGS, {"inactive_days": 60}, format="json").status_code == 200
    assert PlatformSettings.load().inactive_days == 60
    assert direction.put(SETTINGS, {}, format="json").status_code == 405


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload", [{"inactive_days": 0}, {"loyal_min_orders": -1}, {"premium_threshold": "-5"}]
)
def test_reglages_invalides(payload):
    direction = client_for(UserFactory(roles=[Role.DIRECTION]))
    assert direction.patch(SETTINGS, payload, format="json").status_code == 400


@pytest.mark.django_db
def test_une_seule_ligne_de_reglages():
    first = PlatformSettings.load()
    PlatformSettings(inactive_days=10).save()  # remplace la ligne 1, n'en crée pas une 2e
    assert PlatformSettings.objects.count() == 1
    assert PlatformSettings.load().inactive_days == 10
    assert first.pk == 1 and str(first) == "Réglages de la plateforme"


@pytest.mark.django_db
def test_textes_lisibles(khadija):
    payment = Payment.objects.create(
        owner=khadija.owner,
        customer=khadija,
        payment_date=date(2026, 10, 1),
        amount=Decimal("10.00"),
        created_by=khadija.owner,
    )
    assert str(khadija) == "Khadija"
    assert str(payment) == "Paiement 10.00 MRU de Khadija (2026-10-01)"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url",
    ["/admin/customers/customer/", "/admin/customers/payment/", "/admin/core/platformsettings/"],
)
def test_pages_d_administration(url):
    from django.test import Client

    browser = Client()
    browser.force_login(User.objects.create_superuser("46000005", "Oasis-Adrar-2026"))
    assert browser.get(url).status_code == 200
    if "platformsettings" in url:
        assert browser.get(f"{url}add/").status_code == 200  # pas encore de ligne
        PlatformSettings.load()
        assert browser.get(f"{url}add/").status_code == 403
        assert browser.post(f"{url}1/delete/").status_code == 403
