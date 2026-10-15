"""T13 – Tableau de bord : chiffres vérifiés sur un jeu de données connu.

Jeu de données (montants en MRU) :
- Comptes : Alice (agricultrice), Bob (agriculteur + vendeur), Vera (vendeuse), un agent,
  Mohamed (agriculteur inscrit par l'agent, en attente), Salem (agriculteur suspendu).
- Palmiers : ferme d'Alice 100+20 Amhat et 30+10 Tijib ; ferme de Mohamed 50 Amhat
  → 180 productifs + 30 jeunes = 210. Une ferme supprimée ne compte pas.
- Récoltes : 2026 = 900 + 300 = 1 200 kg ; 2025 = 120 kg.
- Alice : vente directe 100 kg × 350 = 35 000 ; dépense 2 000.
- Vera : achat 50 × 300 = 15 000, payé 5 000 → doit 10 000 au fournisseur.
  Commande livrée 10 × 400 = 4 000 (payée 1 000 → le client doit 3 000) ; un autre client
  a donné une avance de 500 ; une commande reçue en retard ; une annulée ; dépense 700.
  Stock : Amhat 40 restants × 400 = 16 000 (seuil 60 → stock bas) ; produit sans prix.
- Marché : 1 annonce publiée, 1 en attente.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import AccountStatus, Role
from customers.models import Customer, Payment
from farms.models import Farm, Harvest, PalmGroup
from finance.models import Expense, ExpenseCategory, Sale
from inventory import services as stock
from inventory.models import Product, Supplier
from market.models import Listing
from oases.models import DateVariety, Oasis, Region
from orders import services as order_services
from orders.models import Notification
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

D = Decimal
DIRECTION_URL, ME_URL = "/api/dashboard/direction/", "/api/dashboard/me/"


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


@pytest.fixture
def world():
    today = timezone.localdate()
    oasis = Oasis.objects.create(
        region=Region.objects.get(slug="atar"), name_ar="آزوكي", name_fr="Azougui"
    )
    amhat = DateVariety.objects.create(
        name_ar="أمهات", name_fr="Amhat", ripening_start_month=7, ripening_end_month=8
    )
    tijib = DateVariety.objects.create(
        name_ar="تيجب", name_fr="Tijib", ripening_start_month=11, ripening_end_month=2
    )
    direction = UserFactory(roles=[Role.DIRECTION])
    alice = UserFactory(full_name="Alice", roles=[Role.FARMER])
    bob = UserFactory(full_name="Bob", roles=[Role.FARMER, Role.SELLER])
    vera = UserFactory(full_name="Vera", roles=[Role.SELLER])
    agent = UserFactory(roles=[Role.FIELD_AGENT])
    mohamed = UserFactory(registered_by=agent, status=AccountStatus.PENDING)
    UserFactory(full_name="Salem", status=AccountStatus.SUSPENDED)

    # Fermes, palmiers, récoltes
    alice_farm = Farm.objects.create(owner=alice, oasis=oasis, name="A", created_by=alice)
    mohamed_farm = Farm.objects.create(owner=mohamed, oasis=oasis, name="M", created_by=agent)
    deleted = Farm.objects.create(
        owner=alice, oasis=oasis, name="X", created_by=alice, is_active=False
    )
    PalmGroup.objects.create(farm=deleted, variety=amhat, productive_count=999)
    PalmGroup.objects.create(farm=alice_farm, variety=amhat, productive_count=100, young_count=20)
    PalmGroup.objects.create(farm=alice_farm, variety=tijib, productive_count=30, young_count=10)
    PalmGroup.objects.create(farm=mohamed_farm, variety=amhat, productive_count=50)
    for farm, variety, season, day, kg in [
        (alice_farm, amhat, 2026, date(2026, 7, 25), "900"),
        (alice_farm, tijib, 2025, date(2025, 12, 1), "120"),
        (mohamed_farm, amhat, 2026, date(2026, 7, 26), "300"),
    ]:
        Harvest.objects.create(
            farm=farm,
            variety=variety,
            season=season,
            harvest_date=day,
            quantity_kg=D(kg),
            created_by=farm.owner,
        )

    # Finances d'Alice
    Sale.objects.create(
        owner=alice, sale_date=today, quantity_kg=D("100"), unit_price=D("350"), created_by=alice
    )
    Expense.objects.create(
        owner=alice,
        category=ExpenseCategory.objects.get(name_fr="Engrais"),
        expense_date=today,
        amount=D("2000"),
        created_by=alice,
    )

    # Vendeuse Vera
    supplier = Supplier.objects.create(owner=vera, name="Coopérative")
    dates = Product.objects.create(
        owner=vera, name="Amhat", sale_price=D("400"), low_stock_threshold=D("60")
    )
    unpriced = Product.objects.create(owner=vera, name="Sans prix")
    stock.create_purchase(
        vera,
        supplier,
        today,
        [{"product": dates, "quantity": D("50"), "unit_cost": D("300")}],
        vera,
    )
    stock.record_supplier_payment(vera, supplier, D("5000"), vera, payment_date=today)
    stock.record_movement(unpriced, "adjust_in", D("10"), vera, note="stock")
    khadija = Customer.objects.create(owner=vera, name="Khadija")
    moussa = Customer.objects.create(owner=vera, name="Moussa")

    def order(customer, **fields):
        return order_services.create_order(
            vera,
            customer,
            [{"product": dates, "quantity": D("10"), "unit_price": D("400")}],
            vera,
            **fields,
        )

    delivered = order(khadija, expected_delivery_date=today)
    for status in ("confirmed", "prepared", "out_for_delivery", "delivered"):
        order_services.change_status(delivered, status, vera)
    order(
        khadija,
        order_date=today - timedelta(days=5),
        expected_delivery_date=today - timedelta(days=1),
    )
    cancelled = order(moussa, expected_delivery_date=today)
    order_services.change_status(cancelled, "cancelled", vera, cancel_reason="x")
    for customer, amount in ((khadija, "1000"), (moussa, "500")):
        Payment.objects.create(
            owner=vera, customer=customer, payment_date=today, amount=D(amount), created_by=vera
        )
    Expense.objects.create(
        owner=vera,
        category=ExpenseCategory.objects.get(name_fr="Emballage"),
        expense_date=today,
        amount=D("700"),
        created_by=vera,
    )
    Notification.objects.create(user=vera, kind="low_stock", message_ar="م", message_fr="Stock bas")

    # Marché
    for status in ("published", "pending"):
        Listing.objects.create(
            owner=alice,
            variety=amhat,
            oasis=oasis,
            title="Amhat",
            language="fr",
            price_per_kg=D("350"),
            quantity_kg=D("10"),
            contact_phone=alice.phone,
            status=status,
        )
    return {"direction": direction, "alice": alice, "bob": bob, "vera": vera, "agent": agent}


# --- Direction -----------------------------------------------------------------------


def test_tableau_de_bord_de_la_direction(world):
    data = client_for(world["direction"]).get(DIRECTION_URL).data
    year = timezone.localdate().year
    assert data["period"] == {"date_from": f"{year}-01-01", "date_to": str(timezone.localdate())}
    assert data["accounts"] == {
        "farmers": 4,
        "sellers": 2,
        "field_agents": 1,
        "pending": 1,
        "suspended": 1,
    }
    assert data["farms"] == 2
    assert data["palms"] == {"productive": 180, "young": 30, "total": 210}
    assert data["palms_by_variety"] == [
        {"variety": "Amhat", "variety_ar": "أمهات", "productive": 150, "young": 20, "total": 170},
        {"variety": "Tijib", "variety_ar": "تيجب", "productive": 30, "young": 10, "total": 40},
    ]
    assert data["production_by_season"] == [
        {"season": 2026, "total_kg": "1200.00"},
        {"season": 2025, "total_kg": "120.00"},
    ]
    assert data["market"] == {"published": 1, "pending": 1}
    assert data["orders"] == {
        "by_status": {
            "received": 1,
            "confirmed": 0,
            "prepared": 0,
            "out_for_delivery": 0,
            "delivered": 1,
            "cancelled": 1,
        },
        "late": 1,
    }
    assert data["stock"] == {"products": 2, "low_stock": 1, "stock_value": "16000.00"}
    assert data["amounts_due"] == {
        "customers_owe": "3000.00",
        "customer_advances": "500.00",
        "suppliers_owed": "10000.00",
    }
    assert data["money"] == {
        "direct_sales_total": "35000.00",
        "orders_total": "4000.00",
        "sales_total": "39000.00",
        "expenses_total": "2700.00",
        "profit": "36300.00",
    }


def test_montants_en_texte_exact_jamais_en_float(world):
    data = client_for(world["direction"]).get(DIRECTION_URL).data
    assert all(isinstance(v, str) for v in data["money"].values())


def test_periode(world):
    client = client_for(world["direction"])
    next_year = timezone.localdate().year + 1
    data = client.get(
        DIRECTION_URL, {"date_from": f"{next_year}-01-01", "date_to": f"{next_year}-12-31"}
    ).data
    assert data["money"]["sales_total"] == "0.00" and data["money"]["profit"] == "0.00"
    assert data["palms"]["total"] == 210  # les palmiers ne dépendent pas de la période
    assert (
        client.get(DIRECTION_URL, {"date_from": "2026-12-01", "date_to": "2026-01-01"}).status_code
        == 400
    )


@pytest.mark.parametrize("who", ["alice", "vera", "agent"])
def test_tableau_de_la_direction_reserve(world, who):
    assert client_for(world[who]).get(DIRECTION_URL).status_code == 403


# --- Tableaux personnels ------------------------------------------------------------


def test_tableau_de_l_agricultrice(world):
    data = client_for(world["alice"]).get(ME_URL).data
    assert "seller" not in data and "field_agent" not in data
    farmer = data["farmer"]
    assert farmer["farms"] == 1
    assert farmer["palms"] == {"productive": 130, "young": 30, "total": 160}
    assert farmer["production_by_season"] == [
        {"season": 2026, "total_kg": "900.00"},
        {"season": 2025, "total_kg": "120.00"},
    ]
    assert farmer["money"] == {
        "direct_sales_total": "35000.00",
        "orders_total": "0.00",
        "sales_total": "35000.00",
        "expenses_total": "2000.00",
        "profit": "33000.00",
    }


def test_tableau_de_la_vendeuse(world):
    data = client_for(world["vera"]).get(ME_URL).data
    assert "farmer" not in data
    assert data["unread_notifications"] == 1
    seller = data["seller"]
    assert seller["customers"] == 2
    assert seller["orders"]["late"] == 1
    assert seller["orders"]["by_status"]["delivered"] == 1
    assert seller["stock"] == {"products": 2, "low_stock": 1, "stock_value": "16000.00"}
    assert seller["amounts_due"] == {
        "customers_owe": "3000.00",
        "customer_advances": "500.00",
        "suppliers_owed": "10000.00",
    }
    assert seller["money"]["orders_total"] == "4000.00"
    assert seller["money"]["expenses_total"] == "700.00"
    assert seller["money"]["profit"] == "3300.00"


def test_tableau_de_l_agent(world):
    data = client_for(world["agent"]).get(ME_URL).data["field_agent"]
    assert (data["farmers"], data["farmers_claimed"], data["farmers_pending"]) == (1, 0, 1)
    assert data["farms"] == 1
    assert data["palms"] == {"productive": 50, "young": 0, "total": 50}


def test_agriculteur_et_vendeur_a_les_deux_parties(world):
    data = client_for(world["bob"]).get(ME_URL).data
    assert data["roles"] == ["farmer", "seller"]
    assert data["farmer"]["palms"]["total"] == 0
    assert data["seller"]["amounts_due"]["customers_owe"] == "0.00"


def test_tableau_personnel_de_la_direction(world):
    data = client_for(world["direction"]).get(ME_URL).data
    assert set(data) == {"period", "roles", "unread_notifications"}


def test_tableau_personnel_exige_une_connexion(world):
    assert APIClient().get(ME_URL).status_code == 401
