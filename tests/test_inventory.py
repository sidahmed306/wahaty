"""T08 – Stock et fournisseurs : stock jamais négatif, dette exacte, transactions annulées."""

import threading
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.db import IntegrityError, connection, transaction
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import Role, User
from inventory import services
from inventory.models import Product, Purchase, StockMovement, Supplier, SupplierPayment
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

SUPPLIERS, PRODUCTS, PURCHASES, MOVEMENTS, PAYMENTS = (
    "/api/suppliers/",
    "/api/products/",
    "/api/purchases/",
    "/api/stock-movements/",
    "/api/supplier-payments/",
)


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


def D(value):  # noqa: N802
    return Decimal(value)


@pytest.fixture
def w():
    """Vendeuse Vera : achat de 27 505,00 MRU, 10 000 payés → reste à payer 17 505,00."""
    vera = UserFactory(full_name="Vera", roles=[Role.SELLER])
    coop = Supplier.objects.create(owner=vera, name="Coopérative d'Atar")
    other_supplier = Supplier.objects.create(owner=vera, name="Ferme Ouadane")
    amhat = Product.objects.create(
        owner=vera, name="Amhat 1er choix", unit="kg", low_stock_threshold=D("20")
    )
    tijib = Product.objects.create(owner=vera, name="Carton Tijib", unit="box")
    purchase = services.create_purchase(
        owner=vera,
        supplier=coop,
        purchase_date=date(2026, 9, 1),
        lines=[
            {"product": amhat, "quantity": D("50"), "unit_cost": D("300")},
            {"product": tijib, "quantity": D("10"), "unit_cost": D("1250.50")},
        ],
        user=vera,
        reference="BON-17",
    )
    services.record_supplier_payment(
        vera, coop, D("10000"), vera, payment_date=date(2026, 9, 2), method="bankily"
    )
    return SimpleNamespace(
        vera=vera,
        client=client_for(vera),
        coop=coop,
        other_supplier=other_supplier,
        amhat=amhat,
        tijib=tijib,
        purchase=purchase,
    )


def stock(product):
    return services.current_stock(product)


# --- Achats et stock -------------------------------------------------------------


def test_achat_ajoute_au_stock_et_a_la_dette(w):
    assert w.purchase.total_amount == D("27505.00")
    assert stock(w.amhat) == D("50") and stock(w.tijib) == D("10")
    data = w.client.get(f"{SUPPLIERS}{w.coop.id}/").data
    assert (data["purchases_total"], data["paid_total"], data["balance"]) == (
        "27505.00",
        "10000.00",
        "17505.00",
    )


def test_achat_par_l_api(w):
    response = w.client.post(
        PURCHASES,
        {
            "supplier": w.other_supplier.id,
            "purchase_date": "2026-10-01",
            "reference": "B-2",
            "lines": [
                {"product": w.amhat.id, "quantity": "12.5", "unit_cost": "280.40"},
                {"product": w.tijib.id, "quantity": "3", "unit_cost": "999.99"},
            ],
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    assert response.data["total_amount"] == "6504.97"  # 3505,00 + 2999,97
    assert len(response.data["items"]) == 2
    assert stock(w.amhat) == D("62.5")
    assert w.client.get(f"{SUPPLIERS}{w.other_supplier.id}/").data["balance"] == "6504.97"


@pytest.mark.parametrize(
    "line",
    [
        {"quantity": "0", "unit_cost": "10"},
        {"quantity": "-3", "unit_cost": "10"},
        {"quantity": "3", "unit_cost": "-10"},
        {"quantity": "3", "unit_cost": "0"},
    ],
)
def test_ligne_d_achat_invalide(w, line):
    response = w.client.post(
        PURCHASES,
        {
            "supplier": w.coop.id,
            "purchase_date": "2026-10-01",
            "lines": [{"product": w.amhat.id, **line}],
        },
        format="json",
    )
    assert response.status_code == 400
    assert Purchase.objects.count() == 1


def test_achat_sans_ligne_refuse(w):
    response = w.client.post(
        PURCHASES,
        {"supplier": w.coop.id, "purchase_date": "2026-10-01", "lines": []},
        format="json",
    )
    assert response.status_code == 400


def test_achat_trop_eleve_refuse(w):
    line = {"product": w.amhat.id, "quantity": "99999999", "unit_cost": "9999999999"}
    response = w.client.post(
        PURCHASES,
        {"supplier": w.coop.id, "purchase_date": "2026-10-01", "lines": [line]},
        format="json",
    )
    assert response.status_code == 400


def test_achat_annule_entierement_si_une_ligne_echoue(w, monkeypatch):
    """Transaction : si la 2e ligne échoue, l'achat et la 1re ligne disparaissent aussi."""
    real = services.record_movement
    calls = {"n": 0}

    def failing(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("coupure au milieu de l'achat")
        return real(*args, **kwargs)

    monkeypatch.setattr(services, "record_movement", failing)
    before = (Purchase.objects.count(), StockMovement.objects.count(), stock(w.amhat))
    with pytest.raises(RuntimeError):
        services.create_purchase(
            owner=w.vera,
            supplier=w.coop,
            purchase_date=date(2026, 10, 1),
            lines=[
                {"product": w.amhat, "quantity": D("5"), "unit_cost": D("1")},
                {"product": w.tijib, "quantity": D("5"), "unit_cost": D("1")},
            ],
            user=w.vera,
        )
    assert (Purchase.objects.count(), StockMovement.objects.count(), stock(w.amhat)) == before
    assert services.supplier_balance(w.coop) == D("17505.00")


# --- Stock jamais négatif --------------------------------------------------------


def test_sortie_superieure_au_stock_refusee(w):
    response = w.client.post(
        MOVEMENTS,
        {"product": w.amhat.id, "kind": "loss", "quantity": "50.01", "note": "abîmé"},
        format="json",
    )
    assert response.status_code == 400
    assert "Stock insuffisant" in str(response.data)
    assert stock(w.amhat) == D("50")


def test_sortie_de_tout_le_stock_possible(w):
    response = w.client.post(
        MOVEMENTS,
        {"product": w.amhat.id, "kind": "loss", "quantity": "50", "note": "humidité"},
        format="json",
    )
    assert response.status_code == 201, response.data
    assert stock(w.amhat) == D("0")
    assert (
        w.client.post(
            MOVEMENTS,
            {"product": w.amhat.id, "kind": "adjust_out", "quantity": "0.01", "note": "x"},
            format="json",
        ).status_code
        == 400
    )


def test_correction_positive(w):
    response = w.client.post(
        MOVEMENTS,
        {"product": w.tijib.id, "kind": "adjust_in", "quantity": "2", "note": "inventaire"},
        format="json",
    )
    assert response.status_code == 201
    assert stock(w.tijib) == D("12")


@pytest.mark.django_db(transaction=True)
def test_deux_sorties_simultanees_une_seule_passe():
    """Deux ventes en même temps de 7 sur un stock de 10 : une seule doit réussir."""
    seller = UserFactory(roles=[Role.SELLER])
    product = Product.objects.create(owner=seller, name="Dattes")
    StockMovement.objects.create(product=product, kind="adjust_in", quantity=10, created_by=seller)
    barrier = threading.Barrier(2)
    results = []

    def sell():
        try:
            barrier.wait()
            services.record_movement(product, "loss", D("7"), seller, note="vente")
            results.append("ok")
        except services.StockError:
            results.append("refusé")
        finally:
            connection.close()

    threads = [threading.Thread(target=sell) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["ok", "refusé"]
    assert stock(product) == D("3")


@pytest.mark.parametrize("kind", ["purchase", "sale", "return", "inconnu"])
def test_types_non_manuels_refuses(w, kind):
    response = w.client.post(
        MOVEMENTS,
        {"product": w.amhat.id, "kind": kind, "quantity": "1", "note": "x"},
        format="json",
    )
    assert response.status_code == 400
    assert "kind" in response.data


def test_justification_obligatoire(w):
    response = w.client.post(
        MOVEMENTS, {"product": w.amhat.id, "kind": "loss", "quantity": "1"}, format="json"
    )
    assert response.status_code == 400
    assert "note" in response.data


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_mouvement_jamais_modifie_ni_supprime(w, method):
    movement = StockMovement.objects.first()
    response = getattr(w.client, method)(
        f"{MOVEMENTS}{movement.id}/", {"quantity": "1"}, format="json"
    )
    assert response.status_code == 405


def test_historique_des_mouvements(w):
    data = w.client.get(MOVEMENTS, {"product": w.amhat.id}).data
    assert [(m["kind"], m["quantity"], m["unit_cost"]) for m in data] == [
        ("purchase", "50.00", "300.00")
    ]


def test_base_refuse_un_achat_sans_cout(w):
    with pytest.raises(IntegrityError), transaction.atomic():
        StockMovement.objects.create(
            product=w.amhat, kind="purchase", quantity=1, created_by=w.vera
        )


# --- Fournisseurs : reste à payer ------------------------------------------------


def test_paiement_reduit_la_dette(w):
    response = w.client.post(
        PAYMENTS,
        {
            "supplier": w.coop.id,
            "purchase": w.purchase.id,
            "payment_date": "2026-10-01",
            "amount": "7505.00",
            "method": "cash",
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    assert services.supplier_balance(w.coop) == D("10000.00")


def test_payer_plus_que_le_reste_refuse(w):
    payload = {"supplier": w.coop.id, "payment_date": "2026-10-01", "amount": "17505.01"}
    response = w.client.post(PAYMENTS, payload, format="json")
    assert response.status_code == 400
    assert SupplierPayment.objects.count() == 1
    payload["amount"] = "17505.00"
    assert w.client.post(PAYMENTS, payload, format="json").status_code == 201
    assert services.supplier_balance(w.coop) == D("0.00")


@pytest.mark.parametrize("amount", ["0", "-100", "1.234"])
def test_paiement_invalide(w, amount):
    payload = {"supplier": w.coop.id, "payment_date": "2026-10-01", "amount": amount}
    assert w.client.post(PAYMENTS, payload, format="json").status_code == 400


def test_paiement_d_un_achat_d_un_autre_fournisseur_refuse(w):
    payload = {
        "supplier": w.other_supplier.id,
        "purchase": w.purchase.id,
        "payment_date": "2026-10-01",
        "amount": "1",
    }
    response = w.client.post(PAYMENTS, payload, format="json")
    assert response.status_code == 400
    assert "purchase" in response.data


def test_annuler_un_paiement_remet_la_dette(w):
    payment = SupplierPayment.objects.get()
    assert w.client.delete(f"{PAYMENTS}{payment.id}/").status_code == 204
    assert services.supplier_balance(w.coop) == D("27505.00")
    assert w.client.patch(
        f"{PAYMENTS}{payment.id}/", {"amount": "1"}, format="json"
    ).status_code in (404, 405)


def test_fournisseur_avec_dette_non_supprimable(w):
    assert w.client.delete(f"{SUPPLIERS}{w.coop.id}/").status_code == 400
    assert w.client.delete(f"{SUPPLIERS}{w.other_supplier.id}/").status_code == 204


def test_fournisseur_telephone_normalise(w):
    response = w.client.post(SUPPLIERS, {"name": "Ahmed", "phone": "36 11 22 33"}, format="json")
    assert response.status_code == 201
    assert response.data["phone"] == "+22236112233"
    assert response.data["balance"] == "0.00"


# --- Annulation d'un achat -------------------------------------------------------


def test_annuler_un_achat_non_paye(w):
    small = services.create_purchase(
        owner=w.vera,
        supplier=w.other_supplier,
        purchase_date=date(2026, 9, 5),
        lines=[{"product": w.amhat, "quantity": D("5"), "unit_cost": D("100")}],
        user=w.vera,
    )
    response = w.client.post(
        f"{PURCHASES}{small.id}/cancel/", {"reason": "erreur de saisie"}, format="json"
    )
    assert response.status_code == 200, response.data
    assert response.data["cancelled_at"] is not None
    assert stock(w.amhat) == D("50")
    assert services.supplier_balance(w.other_supplier) == D("0.00")
    again = w.client.post(f"{PURCHASES}{small.id}/cancel/", {"reason": "x"}, format="json")
    assert again.status_code == 400
    assert [p["id"] for p in w.client.get(PURCHASES, {"cancelled": "true"}).data] == [small.id]


def test_annuler_un_achat_deja_paye_refuse(w):
    response = w.client.post(f"{PURCHASES}{w.purchase.id}/cancel/", {"reason": "x"}, format="json")
    assert response.status_code == 400
    w.purchase.refresh_from_db()
    assert not w.purchase.is_cancelled


def test_annulation_refusee_et_rien_ne_change_si_marchandise_deja_sortie(w):
    """Transaction : l'annulation échoue sur la 2e ligne → la 1re sortie est annulée aussi."""
    purchase = services.create_purchase(
        owner=w.vera,
        supplier=w.other_supplier,
        purchase_date=date(2026, 9, 5),
        lines=[
            {"product": w.amhat, "quantity": D("5"), "unit_cost": D("1")},
            {"product": w.tijib, "quantity": D("3"), "unit_cost": D("1")},
        ],
        user=w.vera,
    )
    services.record_movement(w.tijib, "loss", D("12"), w.vera, note="vendu au marché")
    movements_before = StockMovement.objects.count()
    response = w.client.post(f"{PURCHASES}{purchase.id}/cancel/", {"reason": "x"}, format="json")
    assert response.status_code == 400
    purchase.refresh_from_db()
    assert not purchase.is_cancelled
    assert StockMovement.objects.count() == movements_before
    assert stock(w.amhat) == D("55") and stock(w.tijib) == D("1")


def test_motif_d_annulation_obligatoire(w):
    assert (
        w.client.post(f"{PURCHASES}{w.purchase.id}/cancel/", {}, format="json").status_code == 400
    )


# --- Produits --------------------------------------------------------------------


def test_stock_bas(w):
    services.record_movement(w.amhat, "loss", D("31"), w.vera, note="x")  # reste 19 ≤ 20
    data = {p["name"]: p for p in w.client.get(PRODUCTS).data}
    assert data["Amhat 1er choix"]["stock"] == "19.00"
    assert data["Amhat 1er choix"]["is_low_stock"] is True
    assert data["Carton Tijib"]["is_low_stock"] is False
    assert [p["name"] for p in w.client.get(PRODUCTS, {"low_stock": "true"}).data] == [
        "Amhat 1er choix"
    ]
    assert [p["name"] for p in w.client.get(PRODUCTS, {"low_stock": "false"}).data] == [
        "Carton Tijib"
    ]


def test_produit_avec_stock_non_supprimable(w):
    assert w.client.delete(f"{PRODUCTS}{w.amhat.id}/").status_code == 400
    empty = Product.objects.create(owner=w.vera, name="Vide")
    assert w.client.delete(f"{PRODUCTS}{empty.id}/").status_code == 204


def test_nom_de_produit_unique(w):
    assert w.client.post(PRODUCTS, {"name": "carton tijib"}, format="json").status_code == 400
    response = w.client.post(
        PRODUCTS, {"name": "Sac Amhat 25 kg", "unit": "bag", "sale_price": "9000"}, format="json"
    )
    assert response.status_code == 201
    assert response.data["stock"] == "0.00"
    assert (
        w.client.patch(
            f"{PRODUCTS}{w.tijib.id}/", {"name": "Amhat 1er choix"}, format="json"
        ).status_code
        == 400
    )
    assert (
        w.client.patch(
            f"{PRODUCTS}{w.tijib.id}/", {"sale_price": "1500"}, format="json"
        ).status_code
        == 200
    )


# --- Isolation et rôles ----------------------------------------------------------


def test_un_autre_vendeur_ne_voit_et_ne_touche_rien(w):
    other = client_for(UserFactory(roles=[Role.SELLER]))
    for url in (SUPPLIERS, PRODUCTS, PURCHASES, MOVEMENTS, PAYMENTS):
        assert other.get(url).data == []
    assert other.get(f"{SUPPLIERS}{w.coop.id}/").status_code == 404
    assert other.get(f"{PRODUCTS}{w.amhat.id}/").status_code == 404
    assert other.patch(f"{PRODUCTS}{w.amhat.id}/", {"name": "x"}, format="json").status_code == 404
    assert (
        other.post(
            f"{PURCHASES}{w.purchase.id}/cancel/", {"reason": "x"}, format="json"
        ).status_code
        == 404
    )
    # Il ne peut pas utiliser les produits / fournisseurs de Vera.
    response = other.post(
        MOVEMENTS,
        {"product": w.amhat.id, "kind": "loss", "quantity": "1", "note": "x"},
        format="json",
    )
    assert response.status_code == 400 and "product" in response.data
    response = other.post(
        PAYMENTS,
        {"supplier": w.coop.id, "payment_date": "2026-10-01", "amount": "1"},
        format="json",
    )
    assert response.status_code == 400 and "supplier" in response.data
    assert stock(w.amhat) == D("50")


@pytest.mark.parametrize("roles", [[Role.FARMER], [Role.FIELD_AGENT]])
def test_espace_vendeur_interdit_aux_autres_roles(w, roles):
    client = client_for(UserFactory(roles=roles))
    for url in (SUPPLIERS, PRODUCTS, PURCHASES, MOVEMENTS, PAYMENTS):
        assert client.get(url).status_code == 403


def test_direction_lit_mais_n_ecrit_pas(w):
    client = client_for(UserFactory(roles=[Role.DIRECTION]))
    assert client.get(f"{SUPPLIERS}{w.coop.id}/").data["balance"] == "17505.00"
    assert len(client.get(MOVEMENTS).data) == 2
    assert client.post(PRODUCTS, {"name": "x"}, format="json").status_code == 403
    assert (
        client.post(
            f"{PURCHASES}{w.purchase.id}/cancel/", {"reason": "x"}, format="json"
        ).status_code
        == 403
    )


def test_textes_lisibles(w):
    movement = StockMovement.objects.get(product=w.amhat)
    assert str(movement) == "Amhat 1er choix +50.00 (Achat (entrée))"
    assert movement.signed_quantity == D("50")
    out = services.record_movement(w.amhat, "loss", D("1"), w.vera, note="x")
    assert out.signed_quantity == D("-1") and "−1" in str(out)
    assert str(w.purchase) == "Achat BON-17 – Coopérative d'Atar – 27505.00 MRU"
    assert str(SupplierPayment.objects.get()).startswith("Paiement 10000.00 MRU à Coopérative")
    assert str(w.coop) == "Coopérative d'Atar" and str(w.amhat) == "Amhat 1er choix"


@pytest.mark.parametrize(
    "model", ["supplier", "product", "purchase", "stockmovement", "supplierpayment"]
)
def test_administration_en_lecture_seule(client, w, model):
    client.force_login(User.objects.create_superuser("46000004", "Oasis-Adrar-2026"))
    assert client.get(f"/admin/inventory/{model}/").status_code == 200
    assert client.get(f"/admin/inventory/{model}/add/").status_code == 403


def test_paiement_d_un_achat_annule_refuse(w):
    small = services.create_purchase(
        owner=w.vera,
        supplier=w.other_supplier,
        purchase_date=date(2026, 9, 5),
        lines=[{"product": w.amhat, "quantity": D("1"), "unit_cost": D("10")}],
        user=w.vera,
    )
    services.cancel_purchase(small, "erreur", w.vera)
    payload = {
        "supplier": w.other_supplier.id,
        "purchase": small.id,
        "payment_date": "2026-10-01",
        "amount": "1",
    }
    response = w.client.post(PAYMENTS, payload, format="json")
    assert response.status_code == 400
    assert "purchase" in response.data
