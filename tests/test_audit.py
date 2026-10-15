"""T13 – Journal d'audit : qui, quand, quoi ; jamais modifiable."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import AccountStatus, Role, User
from audit.models import AuditLog
from customers.models import Customer
from finance.models import Sale
from inventory import services as stock
from inventory.models import Product
from orders import services as order_services
from tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db

D = Decimal


def client_for(user, **extra):
    client = APIClient(**extra)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


def entries(**filters):
    return AuditLog.objects.filter(**filters)


@pytest.fixture
def seller_setup():
    seller = UserFactory(roles=[Role.SELLER])
    customer = Customer.objects.create(owner=seller, name="Khadija")
    product = Product.objects.create(owner=seller, name="Amhat", sale_price=D("400"))
    stock.record_movement(product, "adjust_in", D("100"), seller, note="stock")
    order = order_services.create_order(
        seller,
        customer,
        [{"product": product, "quantity": D("2"), "unit_price": D("400")}],
        seller,
        expected_delivery_date=timezone.localdate() + timedelta(days=1),
    )
    return seller, customer, product, order


def test_changement_de_statut_de_commande(seller_setup):
    seller, _, _, order = seller_setup
    client = client_for(seller, REMOTE_ADDR="41.188.10.20")
    assert (
        client.post(
            f"/api/orders/{order.id}/status/", {"status": "confirmed"}, format="json"
        ).status_code
        == 200
    )
    entry = entries(object_type="orders.Order", action="status_change").get()
    assert entry.user == seller and entry.acting_for is None
    assert entry.object_id == str(order.id) and entry.object_repr == f"Commande {order.number}"
    assert entry.changes["status"] == ["received", "confirmed"]
    assert entry.ip_address == "41.188.10.20"
    assert entry.created_at is not None


def test_paiement_cree_puis_annule(seller_setup):
    seller, customer, _, _ = seller_setup
    client = client_for(seller)
    response = client.post(
        "/api/customer-payments/",
        {"customer": customer.id, "payment_date": str(timezone.localdate()), "amount": "1500.50"},
        format="json",
    )
    created = entries(object_type="customers.Payment", action="create").get()
    assert created.changes["amount"] == [None, "1500.50"]
    assert created.user == seller
    client.delete(f"/api/customer-payments/{response.data['id']}/")
    deleted = entries(object_type="customers.Payment", action="delete").get()
    assert deleted.changes["is_active"] == [True, False]


def test_mouvements_de_stock_et_livraison(seller_setup):
    seller, _, product, order = seller_setup
    for status in ("confirmed", "prepared", "out_for_delivery", "delivered"):
        order_services.change_status(order, status, seller)
    movements = entries(object_type="inventory.StockMovement")
    assert movements.count() == 2  # entrée initiale + sortie de livraison
    sale = movements.filter(changes__kind=[None, "sale"]).get()
    assert sale.changes["quantity"] == [None, "2.00"]
    statuses = [
        e.changes["status"][1]
        for e in entries(object_type="orders.Order", action="status_change").order_by("id")
    ]
    assert statuses == ["confirmed", "prepared", "out_for_delivery", "delivered"]


def test_agent_qui_saisit_pour_un_agriculteur():
    agent = UserFactory(roles=[Role.FIELD_AGENT])
    farmer = UserFactory(registered_by=agent)
    response = client_for(agent).post(
        "/api/sales/",
        {
            "owner": farmer.id,
            "sale_date": str(timezone.localdate()),
            "quantity_kg": "10",
            "unit_price": "300",
        },
        format="json",
    )
    assert response.status_code == 201
    entry = entries(object_type="finance.Sale").get()
    assert (entry.user, entry.acting_for) == (agent, farmer)
    assert entry.changes["total_amount"] == [None, "3000.00"]


def test_validation_d_un_compte_par_la_direction():
    direction = UserFactory(roles=[Role.DIRECTION])
    user = UserFactory(status=AccountStatus.PENDING)
    client_for(direction).post(f"/api/users/{user.id}/approve/")
    entry = entries(object_type="accounts.User", action="status_change").get()
    assert entry.user == direction
    assert entry.changes == {"status": ["pending", "approved"]}


def test_actions_de_l_administration_journalisees(client):
    admin = User.objects.create_superuser("46000009", "Oasis-Adrar-2026")
    users = UserFactory.create_batch(2, status=AccountStatus.PENDING)
    client.force_login(admin)
    client.post(
        "/admin/accounts/user/",
        {"action": "approve_accounts", "_selected_action": [u.pk for u in users]},
    )
    assert entries(object_type="accounts.User", action="status_change", user=admin).count() == 2
    client.post(
        "/admin/accounts/user/", {"action": "suspend_accounts", "_selected_action": [users[0].pk]}
    )
    assert entries(changes__status=["approved", "suspended"]).count() == 1


def test_connexion_reussie_et_refusee():
    user = UserFactory()
    client = APIClient()
    client.post(
        "/api/auth/login/", {"phone": user.phone, "password": DEFAULT_PASSWORD}, format="json"
    )
    login = entries(action="login").get()
    assert login.user == user and login.object_id == str(user.id)
    user.refresh_from_db()
    assert user.last_login is not None
    client.post("/api/auth/login/", {"phone": user.phone, "password": "Mauvais-123"}, format="json")
    failed = entries(action="login_failed").get()
    assert failed.user is None
    assert failed.changes == {"phone": user.phone}
    assert "Mauvais" not in str(failed.changes)  # le mot de passe n'est jamais journalisé


def test_mot_de_passe_jamais_dans_le_journal():
    user = UserFactory()
    created = entries(object_type="accounts.User", object_id=str(user.id), action="create").get()
    assert "password" not in created.changes
    user.set_password("Nouveau-Mot-2026")
    user.save()
    assert not entries(object_type="accounts.User", action="update").exists()


def test_enregistrer_sans_changement_ne_cree_rien(seller_setup):
    _, customer, product, _ = seller_setup
    before = AuditLog.objects.count()
    product.save()
    assert AuditLog.objects.count() == before


def test_action_automatique_sans_utilisateur():
    farmer = UserFactory()
    Sale.objects.create(
        owner=farmer,
        sale_date=timezone.localdate(),
        quantity_kg=D("1"),
        unit_price=D("1"),
        created_by=farmer,
    )
    entry = entries(object_type="finance.Sale").get()
    assert entry.user is None and entry.ip_address is None


def test_adresse_ip_derriere_un_proxy(seller_setup):
    seller, _, product, _ = seller_setup
    client = client_for(seller, HTTP_X_FORWARDED_FOR="102.16.5.9, 10.0.0.1")
    client.patch(f"/api/products/{product.id}/", {"sale_price": "450"}, format="json")
    entry = entries(object_type="inventory.Product", action="update").get()
    assert entry.ip_address == "102.16.5.9"
    assert entry.changes == {"sale_price": ["400.00", "450.00"]}


# --- Journal jamais modifiable -------------------------------------------------------


def test_journal_ni_modifiable_ni_effacable(seller_setup):
    entry = AuditLog.objects.first()
    entry.object_repr = "falsifié"
    with pytest.raises(PermissionError):
        entry.save()
    with pytest.raises(PermissionError):
        entry.delete()
    with pytest.raises(PermissionError):
        AuditLog.objects.all().update(object_repr="x")
    with pytest.raises(PermissionError):
        AuditLog.objects.all().delete()
    assert AuditLog.objects.filter(object_repr="falsifié").count() == 0


# --- API -------------------------------------------------------------------------------


def test_api_reservee_a_la_direction(seller_setup):
    seller = seller_setup[0]
    assert client_for(seller).get("/api/audit/").status_code == 403
    assert APIClient().get("/api/audit/").status_code == 401
    direction = client_for(UserFactory(roles=[Role.DIRECTION]))
    data = direction.get("/api/audit/").data
    assert data["count"] == AuditLog.objects.count() and "results" in data
    assert direction.post("/api/audit/", {}, format="json").status_code == 405
    entry = AuditLog.objects.first()
    assert direction.delete(f"/api/audit/{entry.id}/").status_code == 405


def test_filtres_de_l_api(seller_setup):
    seller, _, _, order = seller_setup
    direction = client_for(UserFactory(roles=[Role.DIRECTION]))
    by_object = direction.get(
        "/api/audit/", {"object_type": "orders.Order", "object_id": order.id}
    ).data
    # Commande créée hors requête (fixture) : pas d'auteur, action « création ».
    assert by_object["count"] == 1
    assert by_object["results"][0]["action"] == "create"
    assert by_object["results"][0]["user_name"] is None
    today = str(timezone.localdate())
    assert direction.get("/api/audit/", {"date_from": today, "date_to": today}).data["count"] > 0
    assert direction.get("/api/audit/", {"action": "login"}).data["count"] == 0


def test_textes_et_administration(client, seller_setup):
    entry = AuditLog.objects.filter(object_type="orders.Order").first()
    assert "Création" in str(entry) and "Commande" in str(entry)
    client.force_login(User.objects.create_superuser("46000010", "Oasis-Adrar-2026"))
    assert client.get("/admin/audit/auditlog/").status_code == 200
    assert client.get("/admin/audit/auditlog/add/").status_code == 403


def test_valeurs_inhabituelles_et_chargement_de_donnees():
    from datetime import time

    from audit.recorder import _plain, _record_save

    assert _plain(time(8, 30)) == "08:30:00"  # type sans conversion prévue : texte
    farmer = UserFactory()
    before = AuditLog.objects.count()
    # Chargement de données (loaddata, raw=True) : rien n'est journalisé.
    _record_save(Sale, Sale(owner=farmer), created=True, raw=True)
    assert AuditLog.objects.count() == before
