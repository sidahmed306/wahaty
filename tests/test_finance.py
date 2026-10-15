"""T07 – Ventes et dépenses : montants MRU décimaux, bénéfice exact, isolation."""

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import Role
from farms.models import Farm
from finance.models import Expense, ExpenseCategory, Sale
from oases.models import Oasis, Region
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

SALES, EXPENSES, SUMMARY, CATEGORIES = (
    "/api/sales/",
    "/api/expenses/",
    "/api/finance/summary/",
    "/api/expense-categories/",
)


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


def cat(name_fr):
    return ExpenseCategory.objects.get(name_fr=name_fr)


@pytest.fixture
def w():
    """Jeu de données connu pour Alice (agricultrice) : bénéfice attendu 32 849,94 MRU."""
    oasis = Oasis.objects.create(
        region=Region.objects.get(slug="atar"), name_ar="آزوكي", name_fr="Azougui"
    )
    alice = UserFactory(full_name="Alice", roles=[Role.FARMER])
    bob = UserFactory(full_name="Bob", roles=[Role.FARMER])
    seller = UserFactory(full_name="Vendeuse", roles=[Role.SELLER])
    agent = UserFactory(roles=[Role.FIELD_AGENT])
    managed = UserFactory(registered_by=agent)
    managed2 = UserFactory(registered_by=agent)
    claimed = UserFactory(registered_by=agent, claimed_at=timezone.now())

    def farm(owner):
        return Farm.objects.create(owner=owner, oasis=oasis, name="Ferme", created_by=owner)

    alice_farm = farm(alice)
    for day, kg, price in [
        (date(2026, 7, 10), "100", "350.50"),  # 35 050,00
        (date(2026, 7, 20), "33.33", "3"),  # 99,99
        (date(2026, 8, 5), "2.5", "0.10"),  # 0,25
    ]:
        Sale.objects.create(
            owner=alice,
            farm=alice_farm,
            sale_date=day,
            quantity_kg=Decimal(kg),
            unit_price=Decimal(price),
            created_by=alice,
        )
    for day, category, amount in [
        (date(2026, 7, 1), "Eau et irrigation", "1200.00"),
        (date(2026, 7, 15), "Main-d'œuvre", "800.10"),
        (date(2026, 8, 2), "Engrais", "300.20"),
    ]:
        Expense.objects.create(
            owner=alice,
            category=cat(category),
            expense_date=day,
            amount=Decimal(amount),
            created_by=alice,
        )
    Sale.objects.create(
        owner=bob,
        sale_date=date(2026, 7, 1),
        quantity_kg=Decimal("10"),
        unit_price=Decimal("100"),
        created_by=bob,
    )
    return SimpleNamespace(
        oasis=oasis,
        alice=alice,
        bob=bob,
        seller=seller,
        agent=agent,
        managed=managed,
        managed2=managed2,
        claimed=claimed,
        alice_farm=alice_farm,
        managed_farm=farm(managed),
        managed2_farm=farm(managed2),
    )


def sale_payload(**overrides):
    return {"sale_date": "2026-09-01", "quantity_kg": "10", "unit_price": "250", **overrides}


def expense_payload(**overrides):
    return {
        "category": cat("Transport").id,
        "expense_date": "2026-09-01",
        "amount": "1500",
        **overrides,
    }


# --- Montants -------------------------------------------------------------------


def test_total_calcule_par_le_serveur(w):
    response = client_for(w.alice).post(
        SALES,
        sale_payload(quantity_kg="12.5", unit_price="410.40", total_amount="1"),
        format="json",
    )
    assert response.status_code == 201, response.data
    assert response.data["total_amount"] == "5130.00"


@pytest.mark.parametrize(
    ("kg", "price", "total"),
    [("1.15", "1.15", "1.32"), ("1.25", "1.25", "1.56"), ("0.5", "0.05", "0.03")],
)
def test_arrondi_au_centime(w, kg, price, total):
    response = client_for(w.alice).post(
        SALES, sale_payload(quantity_kg=kg, unit_price=price), format="json"
    )
    assert response.data["total_amount"] == total


def test_total_recalcule_si_le_prix_change(w):
    sale = Sale.objects.filter(owner=w.alice).first()
    response = client_for(w.alice).patch(f"{SALES}{sale.id}/", {"unit_price": "1"}, format="json")
    assert response.status_code == 200
    assert Decimal(response.data["total_amount"]) == sale.quantity_kg


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"unit_price": "-10"}, "unit_price"),
        ({"unit_price": "0"}, "unit_price"),
        ({"quantity_kg": "-1"}, "quantity_kg"),
        ({"quantity_kg": "0"}, "quantity_kg"),
        ({"unit_price": "1.001"}, "unit_price"),
        ({"unit_price": "abc"}, "unit_price"),
        ({"sale_date": str(timezone.localdate() + timedelta(days=1))}, "sale_date"),
    ],
)
def test_vente_invalide_refusee(w, changes, field):
    response = client_for(w.alice).post(SALES, sale_payload(**changes), format="json")
    assert response.status_code == 400
    assert field in response.data


def test_montant_total_trop_eleve_refuse(w):
    payload = sale_payload(quantity_kg="99999999", unit_price="9999999999")
    assert client_for(w.alice).post(SALES, payload, format="json").status_code == 400


@pytest.mark.parametrize("amount", ["-1500", "0", "-0.01", "12.345"])
def test_depense_negative_ou_nulle_refusee(w, amount):
    response = client_for(w.alice).post(EXPENSES, expense_payload(amount=amount), format="json")
    assert response.status_code == 400
    assert "amount" in response.data


def test_base_refuse_les_montants_negatifs(w):
    from django.db import IntegrityError, transaction

    with pytest.raises(IntegrityError), transaction.atomic():
        Expense.objects.create(
            owner=w.alice,
            category=cat("Autre"),
            expense_date=date(2026, 1, 1),
            amount=Decimal("-5"),
            created_by=w.alice,
        )


# --- Bénéfice -------------------------------------------------------------------


def test_benefice_exact(w):
    data = client_for(w.alice).get(SUMMARY).data
    assert data["sales_total"] == "35150.24"
    assert data["expenses_total"] == "2300.30"
    assert data["profit"] == "32849.94"
    assert [(c["category"]["name_fr"], c["total"]) for c in data["expenses_by_category"]] == [
        ("Eau et irrigation", "1200.00"),
        ("Main-d'œuvre", "800.10"),
        ("Engrais", "300.20"),
    ]
    assert data["by_month"] == [
        {"month": "2026-07", "sales": "35149.99", "expenses": "2000.10", "profit": "33149.89"},
        {"month": "2026-08", "sales": "0.25", "expenses": "300.20", "profit": "-299.95"},
    ]


def test_benefice_sur_une_periode(w):
    data = (
        client_for(w.alice).get(SUMMARY, {"date_from": "2026-08-01", "date_to": "2026-08-31"}).data
    )
    assert (data["sales_total"], data["expenses_total"], data["profit"]) == (
        "0.25",
        "300.20",
        "-299.95",
    )


def test_periode_inversee_refusee(w):
    response = client_for(w.alice).get(
        SUMMARY, {"date_from": "2026-09-01", "date_to": "2026-08-01"}
    )
    assert response.status_code == 400


def test_lignes_supprimees_exclues_du_benefice(w):
    client = client_for(w.alice)
    expense = Expense.objects.get(amount=Decimal("1200.00"))
    assert client.delete(f"{EXPENSES}{expense.id}/").status_code == 204
    assert Expense.objects.filter(pk=expense.pk).exists()  # suppression douce
    assert client.get(SUMMARY).data["profit"] == "34049.94"
    assert client.get(f"{EXPENSES}{expense.id}/").status_code == 404


def test_benefice_vide_a_zero(w):
    data = client_for(w.managed).get(SUMMARY).data
    assert (data["sales_total"], data["expenses_total"], data["profit"]) == ("0.00", "0.00", "0.00")
    assert data["by_month"] == [] and data["expenses_by_category"] == []


# --- Isolation ------------------------------------------------------------------


def test_b_ne_voit_ni_ne_modifie_les_chiffres_d_alice(w):
    client = client_for(w.bob)
    sale = Sale.objects.filter(owner=w.alice).first()
    expense = Expense.objects.filter(owner=w.alice).first()
    assert {s["owner"] for s in client.get(SALES).data} == {w.bob.id}
    assert client.get(EXPENSES).data == []
    assert client.get(f"{SALES}{sale.id}/").status_code == 404
    assert client.patch(f"{SALES}{sale.id}/", {"unit_price": "1"}, format="json").status_code == 404
    assert client.delete(f"{EXPENSES}{expense.id}/").status_code == 404
    assert client.get(SUMMARY).data["sales_total"] == "1000.00"
    assert client.get(SUMMARY, {"owner": w.alice.id}).status_code == 404
    assert client.get(SUMMARY, {"owner": 999999}).status_code == 404


def test_b_ne_peut_pas_utiliser_la_ferme_d_alice(w):
    response = client_for(w.bob).post(SALES, sale_payload(farm=w.alice_farm.id), format="json")
    assert response.status_code == 400
    assert "farm" in response.data


def test_direction_lit_tout_mais_n_ecrit_pas(w):
    client = client_for(UserFactory(roles=[Role.DIRECTION]))
    assert len(client.get(SALES).data) == 4
    assert client.get(SUMMARY).data["sales_total"] == "36150.24"
    assert client.get(SUMMARY, {"owner": w.alice.id}).data["profit"] == "32849.94"
    assert client.post(SALES, sale_payload(), format="json").status_code == 403
    assert client.post(EXPENSES, expense_payload(), format="json").status_code == 403


# --- Vendeur --------------------------------------------------------------------


def test_vendeur_saisit_ses_depenses(w):
    client = client_for(w.seller)
    response = client.post(EXPENSES, expense_payload(category=cat("Emballage").id), format="json")
    assert response.status_code == 201
    assert client.get(SUMMARY).data["profit"] == "-1500.00"


def test_vendeur_ne_peut_pas_utiliser_une_categorie_agricole(w):
    response = client_for(w.seller).post(
        EXPENSES, expense_payload(category=cat("Engrais").id), format="json"
    )
    assert response.status_code == 400
    assert "category" in response.data


def test_vendeur_n_a_pas_de_ventes_directes(w):
    assert client_for(w.seller).post(SALES, sale_payload(), format="json").status_code == 403


def test_agriculteur_et_vendeur_utilise_toutes_les_categories(w):
    both = UserFactory(roles=[Role.FARMER, Role.SELLER])
    client = client_for(both)
    for name in ("Engrais", "Emballage"):
        response = client.post(EXPENSES, expense_payload(category=cat(name).id), format="json")
        assert response.status_code == 201


# --- Agent de terrain -----------------------------------------------------------


def test_agent_saisit_pour_son_agriculteur(w):
    client = client_for(w.agent)
    response = client.post(
        SALES, sale_payload(owner=w.managed.id, farm=w.managed_farm.id), format="json"
    )
    assert response.status_code == 201, response.data
    sale = Sale.objects.get(pk=response.data["id"])
    assert sale.owner == w.managed and sale.created_by == w.agent
    assert client.get(SUMMARY, {"owner": w.managed.id}).data["sales_total"] == "2500.00"
    assert client.get(SUMMARY, {"owner": w.alice.id}).status_code == 404


def test_agent_ne_melange_pas_les_fermes_de_ses_agriculteurs(w):
    response = client_for(w.agent).post(
        SALES, sale_payload(owner=w.managed.id, farm=w.managed2_farm.id), format="json"
    )
    assert response.status_code == 400
    assert "farm" in response.data


def test_agent_ne_saisit_pas_apres_reprise(w):
    response = client_for(w.agent).post(
        EXPENSES, expense_payload(owner=w.claimed.id), format="json"
    )
    assert response.status_code == 403


def test_changer_la_ferme_vers_celle_d_un_autre_refuse(w):
    sale = Sale.objects.create(
        owner=w.managed,
        sale_date=date(2026, 9, 1),
        quantity_kg=Decimal("1"),
        unit_price=Decimal("1"),
        created_by=w.agent,
    )
    response = client_for(w.agent).patch(
        f"{SALES}{sale.id}/", {"farm": w.managed2_farm.id}, format="json"
    )
    assert response.status_code == 400


# --- Catégories -----------------------------------------------------------------


def test_categories_de_depart_bilingues(w):
    data = client_for(w.alice).get(CATEGORIES).data
    assert len(data) == 7
    assert data[0]["name_ar"] == "ماء وري"
    assert {
        c["name_fr"] for c in client_for(w.alice).get(CATEGORIES, {"applies_to": "farmer"}).data
    } == {
        "Eau et irrigation",
        "Engrais",
    }


def test_direction_gere_les_categories(w):
    client = client_for(UserFactory(roles=[Role.DIRECTION]))
    response = client.post(CATEGORIES, {"name_ar": "صيانة", "name_fr": "Entretien"}, format="json")
    assert response.status_code == 201
    category_id = response.data["id"]
    assert client.delete(f"{CATEGORIES}{category_id}/").status_code == 204
    assert category_id not in {c["id"] for c in client_for(w.alice).get(CATEGORIES).data}
    assert category_id in {c["id"] for c in client.get(CATEGORIES).data}
    response = client_for(w.alice).post(
        EXPENSES, expense_payload(category=category_id), format="json"
    )
    assert response.status_code == 400


def test_categories_reservees_a_la_direction(w):
    response = client_for(w.alice).post(CATEGORIES, {"name_ar": "س", "name_fr": "X"}, format="json")
    assert response.status_code == 403


def test_textes_lisibles(w):
    sale = Sale.objects.get(unit_price=Decimal("350.50"))
    assert str(sale) == "Vente du 2026-07-10 – 35050.00 MRU"
    assert str(Expense.objects.get(amount=Decimal("300.20"))) == "Engrais – 300.20 MRU (2026-08-02)"
    assert str(cat("Autre")) == "Autre"


@pytest.mark.parametrize("model", ["sale", "expense", "expensecategory"])
def test_pages_d_administration(client, w, model):
    from accounts.models import User

    client.force_login(User.objects.create_superuser("46000003", "Oasis-Adrar-2026"))
    assert client.get(f"/admin/finance/{model}/").status_code == 200
