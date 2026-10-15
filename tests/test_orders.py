"""T10 – Commandes et livraison : statuts, historique, retards, rappels, stock à la livraison."""

from datetime import timedelta
from decimal import Decimal
from io import StringIO
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import Role, User
from customers.models import Customer, Payment
from finance.models import Expense, ExpenseCategory
from inventory import services as stock
from inventory.models import Product, StockMovement
from orders import services
from orders.models import Notification, Order, OrderStatus
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

ORDERS, NOTIFS = "/api/orders/", "/api/notifications/"
D = Decimal


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


def today():
    return timezone.localdate()


@pytest.fixture
def w():
    seller = UserFactory(full_name="Vera", roles=[Role.SELLER])
    customer = Customer.objects.create(owner=seller, name="Khadija")
    amhat = Product.objects.create(owner=seller, name="Amhat", sale_price=D("400"))
    tijib = Product.objects.create(owner=seller, name="Carton Tijib", unit="box")
    for product, qty in ((amhat, "50"), (tijib, "10")):
        stock.record_movement(product, "adjust_in", D(qty), seller, note="stock initial")
    return SimpleNamespace(
        seller=seller,
        client=client_for(seller),
        customer=customer,
        amhat=amhat,
        tijib=tijib,
    )


def order_payload(w, **overrides):
    return {
        "customer": w.customer.id,
        "expected_delivery_date": str(today() + timedelta(days=3)),
        "delivery_fee": "200",
        "discount": "1",
        "items": [
            {"product": w.amhat.id, "quantity": "10"},  # prix par défaut : 400
            {"product": w.tijib.id, "quantity": "2", "unit_price": "1250.50"},
        ],
        **overrides,
    }


def make_order(w, **overrides):
    response = w.client.post(ORDERS, order_payload(w, **overrides), format="json")
    assert response.status_code == 201, response.data
    return Order.objects.get(pk=response.data["id"])


def move(w, order, status, **extra):
    return w.client.post(f"{ORDERS}{order.id}/status/", {"status": status, **extra}, format="json")


def deliver(w, order):
    for status in ("confirmed", "prepared", "out_for_delivery", "delivered"):
        assert move(w, order, status).status_code == 200


def current(product):
    return stock.current_stock(product)


# --- Création et totaux ----------------------------------------------------------


def test_creation_avec_totaux_et_historique(w):
    response = w.client.post(ORDERS, order_payload(w), format="json")
    assert response.status_code == 201, response.data
    data = response.data
    assert data["number"] == "CMD-0001"
    assert data["status"] == "received"
    assert [(line["unit_price"], line["line_total"]) for line in data["lines"]] == [
        ("400.00", "4000.00"),
        ("1250.50", "2501.00"),
    ]
    assert (data["subtotal"], data["total_amount"]) == ("6501.00", "6700.00")
    assert [(h["from_status"], h["to_status"]) for h in data["history"]] == [("", "received")]


def test_numeros_sequentiels_par_vendeur(w):
    assert make_order(w).number == "CMD-0001"
    assert make_order(w).number == "CMD-0002"
    other = UserFactory(roles=[Role.SELLER])
    customer = Customer.objects.create(owner=other, name="X")
    order = services.create_order(other, customer, [], other, expected_delivery_date=today())
    assert order.number == "CMD-0001"


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"items": []}, "items"),
        ({"items": [{"product": 0, "quantity": "1"}]}, "items"),
        ({"discount": "-1"}, "discount"),
        ({"delivery_fee": "-5"}, "delivery_fee"),
        ({"order_date": "2099-01-01"}, "order_date"),
    ],
)
def test_commande_invalide(w, overrides, field):
    response = w.client.post(ORDERS, order_payload(w, **overrides), format="json")
    assert response.status_code == 400
    assert field in response.data


def test_prix_obligatoire_si_le_produit_n_en_a_pas(w):
    payload = order_payload(w, items=[{"product": w.tijib.id, "quantity": "1"}])
    response = w.client.post(ORDERS, payload, format="json")
    assert response.status_code == 400


def test_remise_superieure_au_montant_refusee(w):
    response = w.client.post(ORDERS, order_payload(w, discount="7000"), format="json")
    assert response.status_code == 400
    assert not Order.objects.exists()


def test_livraison_avant_la_commande_refusee(w):
    payload = order_payload(
        w, order_date=str(today()), expected_delivery_date=str(today() - timedelta(days=1))
    )
    response = w.client.post(ORDERS, payload, format="json")
    assert response.status_code == 400
    assert "expected_delivery_date" in response.data


# --- Cycle des statuts -----------------------------------------------------------


def test_cycle_complet_stock_retire_a_la_livraison(w):
    order = make_order(w)
    for status in ("confirmed", "prepared", "out_for_delivery"):
        response = move(w, order, status, note=f"→ {status}")
        assert response.status_code == 200, response.data
        assert current(w.amhat) == D("50")  # pas encore retiré
    response = move(w, order, "delivered")
    assert response.status_code == 200
    assert response.data["status"] == "delivered" and response.data["delivered_at"]
    assert (current(w.amhat), current(w.tijib)) == (D("40"), D("8"))
    sales = StockMovement.objects.filter(order=order, kind="sale")
    assert {(m.product_id, m.quantity) for m in sales} == {
        (w.amhat.id, D("10")),
        (w.tijib.id, D("2")),
    }
    history = response.data["history"]
    assert [h["to_status"] for h in history] == [
        "received",
        "confirmed",
        "prepared",
        "out_for_delivery",
        "delivered",
    ]
    assert {h["changed_by"] for h in history} == {w.seller.id}
    assert history[1]["note"] == "→ confirmed"


@pytest.mark.parametrize(
    ("path", "target"),
    [
        ([], "delivered"),
        ([], "prepared"),
        ([], "out_for_delivery"),
        (["confirmed"], "received"),
        (["confirmed", "prepared"], "confirmed"),
        (["confirmed", "prepared", "out_for_delivery"], "cancelled"),
        (["confirmed", "prepared", "out_for_delivery", "delivered"], "cancelled"),
        (["confirmed", "prepared", "out_for_delivery", "delivered"], "out_for_delivery"),
    ],
)
def test_transitions_interdites_refusees(w, path, target):
    order = make_order(w)
    for status in path:
        assert move(w, order, status, cancel_reason="x").status_code == 200
    before = Order.objects.get(pk=order.pk).status
    response = move(w, order, target, cancel_reason="x")
    assert response.status_code == 400
    assert "Passage interdit" in str(response.data)
    assert Order.objects.get(pk=order.pk).status == before


def test_commande_annulee_definitive(w):
    order = make_order(w)
    assert move(w, order, "cancelled", cancel_reason="client absent").status_code == 200
    assert move(w, order, "confirmed").status_code == 400


def test_annulation_avec_motif_obligatoire(w):
    order = make_order(w)
    assert move(w, order, "confirmed").status_code == 200
    assert move(w, order, "prepared").status_code == 200
    assert move(w, order, "cancelled").status_code == 400
    response = move(w, order, "cancelled", cancel_reason="rupture chez le client")
    assert response.status_code == 200
    assert response.data["cancel_reason"] == "rupture chez le client"
    assert current(w.amhat) == D("50")


def test_statut_inconnu(w):
    order = make_order(w)
    assert move(w, order, "perdue").status_code == 400


def test_confirmation_refusee_si_stock_insuffisant(w):
    order = make_order(w, items=[{"product": w.amhat.id, "quantity": "60"}])
    response = move(w, order, "confirmed")
    assert response.status_code == 400
    assert "Stock insuffisant" in str(response.data)
    assert Order.objects.get(pk=order.pk).status == "received"


def test_livraison_annulee_entierement_si_stock_manque(w):
    """Transaction : le stock du 2e produit manque → aucune sortie, statut inchangé."""
    order = make_order(w)
    for status in ("confirmed", "prepared", "out_for_delivery"):
        move(w, order, status)
    stock.record_movement(w.tijib, "loss", D("9"), w.seller, note="abîmé")  # reste 1, il en faut 2
    movements = StockMovement.objects.count()
    response = move(w, order, "delivered")
    assert response.status_code == 400
    assert Order.objects.get(pk=order.pk).status == "out_for_delivery"
    assert StockMovement.objects.count() == movements
    assert current(w.amhat) == D("50")


def test_meme_produit_sur_deux_lignes_additionne(w):
    order = make_order(
        w,
        discount="0",
        items=[
            {"product": w.amhat.id, "quantity": "30"},
            {"product": w.amhat.id, "quantity": "25"},
        ],
    )
    response = move(w, order, "confirmed")
    assert response.status_code == 400  # 55 demandés pour 50 en stock


# --- Modification ----------------------------------------------------------------


def test_modifier_les_lignes_en_statut_recue(w):
    order = make_order(w)
    response = w.client.patch(
        f"{ORDERS}{order.id}/",
        {"items": [{"product": w.amhat.id, "quantity": "1"}], "discount": "0"},
        format="json",
    )
    assert response.status_code == 200, response.data
    assert (response.data["subtotal"], response.data["total_amount"]) == ("400.00", "600.00")
    assert len(response.data["lines"]) == 1


def test_lignes_bloquees_apres_confirmation(w):
    order = make_order(w)
    move(w, order, "confirmed")
    url = f"{ORDERS}{order.id}/"
    response = w.client.patch(
        url, {"items": [{"product": w.amhat.id, "quantity": "1"}]}, format="json"
    )
    assert response.status_code == 400
    assert w.client.patch(url, {"discount": "5"}, format="json").status_code == 400
    response = w.client.patch(
        url, {"notes": "appeler avant", "delivery_address": "Atar"}, format="json"
    )
    assert response.status_code == 200
    assert response.data["total_amount"] == "6700.00"


def test_commande_livree_non_modifiable(w):
    order = make_order(w)
    deliver(w, order)
    assert w.client.patch(f"{ORDERS}{order.id}/", {"notes": "x"}, format="json").status_code == 400


def test_commande_jamais_supprimee(w):
    order = make_order(w)
    assert w.client.delete(f"{ORDERS}{order.id}/").status_code == 405
    assert Order.objects.filter(pk=order.pk).exists()


# --- Retards ---------------------------------------------------------------------


def make_dated_order(w, order_days_ago, expected_days_ago, status=OrderStatus.RECEIVED):
    order = services.create_order(
        w.seller,
        w.customer,
        [{"product": w.amhat, "quantity": D("1"), "unit_price": D("400")}],
        w.seller,
        order_date=today() - timedelta(days=order_days_ago),
        expected_delivery_date=today() - timedelta(days=expected_days_ago),
    )
    reason = "annulée pour le test" if status == OrderStatus.CANCELLED else ""
    Order.objects.filter(pk=order.pk).update(status=status, cancel_reason=reason)
    return Order.objects.get(pk=order.pk)


def test_retard_detecte(w):
    late = make_dated_order(w, 5, 2, OrderStatus.CONFIRMED)
    on_time = make_dated_order(w, 5, -1)
    delivered = make_dated_order(w, 5, 2, OrderStatus.DELIVERED)
    cancelled = make_dated_order(w, 5, 2, OrderStatus.CANCELLED)
    due_today = make_dated_order(w, 5, 0)
    assert (late.is_late, late.days_late) == (True, 2)
    for order in (on_time, delivered, cancelled, due_today):
        assert (order.is_late, order.days_late) == (False, 0)
    data = w.client.get(f"{ORDERS}{late.id}/").data
    assert (data["is_late"], data["days_late"]) == (True, 2)
    assert [o["id"] for o in w.client.get(ORDERS, {"late": "true"}).data] == [late.id]
    assert late.id not in [o["id"] for o in w.client.get(ORDERS, {"late": "false"}).data]


def test_filtres(w):
    order = make_order(w)
    assert [o["id"] for o in w.client.get(ORDERS, {"status": "received"}).data] == [order.id]
    assert w.client.get(ORDERS, {"status": "delivered"}).data == []
    expected = str(today() + timedelta(days=3))
    assert len(w.client.get(ORDERS, {"expected_from": expected, "expected_to": expected}).data) == 1


# --- Rappels (commande planifiée) -------------------------------------------------


def test_commande_de_rappel(w):
    late = make_dated_order(w, 5, 3, OrderStatus.PREPARED)
    due = make_dated_order(w, 1, -1)  # à livrer demain
    make_dated_order(w, 5, 3, OrderStatus.DELIVERED)  # livrée : pas de rappel
    Product.objects.filter(pk=w.tijib.pk).update(low_stock_threshold=D("10"))
    out = StringIO()
    call_command("send_order_reminders", stdout=out)
    assert "1 livraison(s) demain, 1 retard(s), 1 stock(s) bas" in out.getvalue()
    notifs = {n.kind: n for n in Notification.objects.all()}
    assert notifs["order_late"].order == late and notifs["order_late"].user == w.seller
    assert "en retard de 3 jour(s)" in notifs["order_late"].message_fr
    assert "متأخر" in notifs["order_late"].message_ar
    assert notifs["delivery_due"].order == due
    assert "Carton Tijib" in notifs["low_stock"].message_fr
    # Relancer le même jour ne crée pas de doublon.
    out = StringIO()
    call_command("send_order_reminders", stdout=out)
    assert "0 livraison(s) demain, 0 retard(s), 0 stock(s) bas" in out.getvalue()
    assert Notification.objects.count() == 3


def test_commande_de_rappel_pour_une_date(w):
    make_dated_order(w, 5, 3)
    out = StringIO()
    call_command("send_order_reminders", "--date", str(today() + timedelta(days=1)), stdout=out)
    assert "1 retard(s)" in out.getvalue()
    assert "4 jour(s)" in Notification.objects.get().message_fr


def test_notifications_dans_la_plateforme(w):
    make_dated_order(w, 5, 3)
    make_dated_order(w, 5, 4)
    call_command("send_order_reminders", stdout=StringIO())
    data = w.client.get(NOTIFS).data
    assert len(data) == 2 and data[0]["order_number"].startswith("CMD-")
    first = data[0]["id"]
    assert w.client.post(f"{NOTIFS}{first}/read/").data["read_at"] is not None
    assert len(w.client.get(NOTIFS, {"unread": "true"}).data) == 1
    assert w.client.post(f"{NOTIFS}read-all/").data == {"marked": 1}
    assert w.client.get(NOTIFS, {"unread": "true"}).data == []
    assert w.client.post(f"{NOTIFS}{first}/read/").status_code == 200  # déjà lue : sans effet
    other = client_for(UserFactory(roles=[Role.SELLER]))
    assert other.get(NOTIFS).data == []
    assert other.post(f"{NOTIFS}{first}/read/").status_code == 404


# --- Branchement : clients (T09) et bénéfice (T07) --------------------------------


def test_clients_dette_total_et_segment(w):
    first = make_order(w)
    deliver(w, first)  # 6 700,00 livrés
    second = make_order(w)  # pas encore livrée
    third = make_order(w)
    move(w, third, "cancelled", cancel_reason="erreur")
    Payment.objects.create(
        owner=w.seller,
        customer=w.customer,
        order=first,
        payment_date=today(),
        amount=D("2000"),
        created_by=w.seller,
    )
    data = w.client.get(f"/api/customers/{w.customer.id}/").data
    assert data["orders_count"] == 2  # l'annulée ne compte pas
    assert data["total_purchased"] == "6700.00"  # seulement la livrée
    assert (data["paid_total"], data["balance"]) == ("2000.00", "4700.00")
    assert data["segment"] == "new"
    assert second.status == "received"


def test_client_fidele_avec_de_vraies_commandes(w):
    for _ in range(3):
        make_order(w)
    assert w.client.get(f"/api/customers/{w.customer.id}/").data["segment"] == "loyal"


def test_paiement_lie_a_une_commande(w):
    order = make_order(w)
    other_customer = Customer.objects.create(owner=w.seller, name="Autre")
    payload = {
        "customer": other_customer.id,
        "order": order.id,
        "payment_date": str(today()),
        "amount": "10",
    }
    assert w.client.post("/api/customer-payments/", payload, format="json").status_code == 400
    move(w, order, "cancelled", cancel_reason="x")
    payload["customer"] = w.customer.id
    assert w.client.post("/api/customer-payments/", payload, format="json").status_code == 400
    ok = make_order(w)
    payload["order"] = ok.id
    response = w.client.post("/api/customer-payments/", payload, format="json")
    assert response.status_code == 201 and response.data["order"] == ok.id


def test_benefice_du_vendeur_avec_commandes_livrees(w):
    deliver(w, make_order(w))
    make_order(w)  # non livrée : ne compte pas
    Expense.objects.create(
        owner=w.seller,
        category=ExpenseCategory.objects.get(name_fr="Emballage"),
        expense_date=today(),
        amount=D("700"),
        created_by=w.seller,
    )
    data = w.client.get("/api/finance/summary/").data
    assert (data["direct_sales_total"], data["orders_total"], data["sales_total"]) == (
        "0.00",
        "6700.00",
        "6700.00",
    )
    assert data["profit"] == "6000.00"
    assert data["by_month"][-1]["sales"] == "6700.00"
    future = str(today() + timedelta(days=40))
    assert (
        w.client.get("/api/finance/summary/", {"date_from": future}).data["orders_total"] == "0.00"
    )
    past = str(today() - timedelta(days=40))
    assert w.client.get("/api/finance/summary/", {"date_to": past}).data["orders_total"] == "0.00"


# --- Isolation et rôles ----------------------------------------------------------


def test_un_autre_vendeur_ne_voit_et_ne_touche_rien(w):
    order = make_order(w)
    other = client_for(UserFactory(roles=[Role.SELLER]))
    assert other.get(ORDERS).data == []
    assert other.get(f"{ORDERS}{order.id}/").status_code == 404
    assert other.patch(f"{ORDERS}{order.id}/", {"notes": "x"}, format="json").status_code == 404
    assert (
        other.post(
            f"{ORDERS}{order.id}/status/", {"status": "confirmed"}, format="json"
        ).status_code
        == 404
    )
    response = other.post(ORDERS, order_payload(w), format="json")  # client et produits de Vera
    assert response.status_code == 400
    assert "customer" in response.data and "items" in response.data
    assert Order.objects.get(pk=order.pk).status == "received"


@pytest.mark.parametrize("roles", [[Role.FARMER], [Role.FIELD_AGENT]])
def test_commandes_reservees_aux_vendeurs(roles):
    assert client_for(UserFactory(roles=roles)).get(ORDERS).status_code == 403


def test_direction_lit_mais_ne_change_pas_les_statuts(w):
    order = make_order(w)
    direction = client_for(UserFactory(roles=[Role.DIRECTION]))
    assert direction.get(f"{ORDERS}{order.id}/").status_code == 200
    response = direction.post(f"{ORDERS}{order.id}/status/", {"status": "confirmed"}, format="json")
    assert response.status_code == 403


def test_textes_lisibles(w):
    order = make_order(w)
    item = order.items.first()
    history = order.history.first()
    assert str(order) == f"Commande {order.number}"
    assert str(item) == "Amhat × 10.00"
    assert str(history) == f"Commande {order.number} : — → received"
    notif = Notification.objects.create(
        user=w.seller, kind="order_late", order=order, message_ar="م", message_fr="Retard"
    )
    assert str(notif) == "Retard"


@pytest.mark.parametrize("model", ["order", "notification"])
def test_administration_en_lecture_seule(client, w, model):
    make_order(w)
    client.force_login(User.objects.create_superuser("46000006", "Oasis-Adrar-2026"))
    assert client.get(f"/admin/orders/{model}/").status_code == 200
    order = Order.objects.first()
    if model == "order":
        assert client.get(f"/admin/orders/order/{order.id}/change/").status_code == 200
