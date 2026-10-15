"""T11 – Factures : numéros uniques sans trou, PDF bilingue généré."""

import re
import threading
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import Role, User
from customers.models import Customer
from inventory import services as stock
from inventory.models import Product
from invoices import services
from invoices.models import Invoice, InvoiceSequence
from invoices.pdf import has_arabic, runs, shape
from orders import services as order_services
from orders.models import OrderStatus
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

INVOICES = "/api/invoices/"
D = Decimal
YEAR = timezone.localdate().year


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


def make_seller():
    seller = UserFactory(full_name="Vera", roles=[Role.SELLER])
    seller.profile.business_name = "تمور أطار – Dattes d'Atar"
    seller.profile.save()
    customer = Customer.objects.create(
        owner=seller, name="خديجة بنت محمد", phone="+22246000000", city="Atar"
    )
    product = Product.objects.create(owner=seller, name="أمهات – Amhat", sale_price=D("400"))
    stock.record_movement(product, "adjust_in", D("1000"), seller, note="stock")
    return seller, customer, product


def make_order(seller, customer, product, status=OrderStatus.CONFIRMED, lines=1):
    order = order_services.create_order(
        seller,
        customer,
        [{"product": product, "quantity": D("10"), "unit_price": D("400")}] * lines,
        seller,
        expected_delivery_date=timezone.localdate() + timedelta(days=2),
        delivery_fee=D("200"),
        discount=D("50"),
    )
    path = ["confirmed", "prepared", "out_for_delivery", "delivered"]
    for step in path[: path.index(status) + 1] if status != OrderStatus.RECEIVED else []:
        order_services.change_status(order, step, seller)
    order.refresh_from_db()
    return order


@pytest.fixture
def w():
    seller, customer, product = make_seller()
    return type(
        "W",
        (),
        {
            "seller": seller,
            "customer": customer,
            "product": product,
            "client": client_for(seller),
            "order": lambda self, **kw: make_order(seller, customer, product, **kw),
        },
    )()


def create(w, order):
    return w.client.post(INVOICES, {"order": order.id}, format="json")


# --- Numérotation ----------------------------------------------------------------


def test_facture_d_une_commande_confirmee(w):
    order = w.order()
    response = create(w, order)
    assert response.status_code == 201, response.data
    data = response.data
    assert data["number"] == f"FAC-{YEAR}-0001"
    assert (data["subtotal"], data["delivery_fee"], data["discount"], data["total_amount"]) == (
        "4000.00",
        "200.00",
        "50.00",
        "4150.00",
    )
    assert data["seller_snapshot"]["name"] == "تمور أطار – Dattes d'Atar"
    assert data["customer_snapshot"]["name"] == "خديجة بنت محمد"
    assert data["lines_snapshot"] == [
        {
            "product": "أمهات – Amhat",
            "unit": "kg",
            "quantity": "10.00",
            "unit_price": "400.00",
            "line_total": "4000.00",
        }
    ]


def test_numeros_sans_trou_et_annulation_garde_le_numero(w):
    numbers = [create(w, w.order()).data["number"] for _ in range(3)]
    assert numbers == [f"FAC-{YEAR}-000{i}" for i in (1, 2, 3)]
    second = Invoice.objects.get(number=numbers[1])
    response = w.client.post(
        f"{INVOICES}{second.id}/cancel/", {"reason": "erreur de prix"}, format="json"
    )
    assert response.status_code == 200 and response.data["status"] == "cancelled"
    # La commande peut être refacturée : nouveau numéro, l'ancien n'est jamais réutilisé.
    again = create(w, second.order)
    assert again.status_code == 201
    assert again.data["number"] == f"FAC-{YEAR}-0004"
    sequences = sorted(Invoice.objects.values_list("sequence", flat=True))
    assert sequences == [1, 2, 3, 4]


def test_numerotation_par_vendeur_et_par_annee(w):
    create(w, w.order())
    other_seller, other_customer, other_product = make_seller()
    other_order = make_order(other_seller, other_customer, other_product)
    assert services.create_invoice(other_order, other_seller).number == f"FAC-{YEAR}-0001"
    next_year = services.create_invoice(w.order(), w.seller, issue_date=date(YEAR + 1, 1, 2))
    assert next_year.number == f"FAC-{YEAR + 1}-0001"


def test_echec_de_creation_ne_laisse_pas_de_trou(w, monkeypatch):
    order = w.order()

    def broken(**kwargs):
        raise RuntimeError("panne au milieu")

    monkeypatch.setattr(Invoice.objects, "create", broken)
    with pytest.raises(RuntimeError):
        services.create_invoice(order, w.seller)
    monkeypatch.undo()
    assert not Invoice.objects.exists()
    assert InvoiceSequence.objects.filter(owner=w.seller).first() is None
    assert services.create_invoice(order, w.seller).sequence == 1


@pytest.mark.django_db(transaction=True)
def test_deux_factures_simultanees_ont_des_numeros_differents():
    seller, customer, product = make_seller()
    orders = [make_order(seller, customer, product) for _ in range(2)]
    barrier = threading.Barrier(2)
    numbers = []

    def invoice(order):
        try:
            barrier.wait()
            numbers.append(services.create_invoice(order, seller).sequence)
        finally:
            connection.close()

    threads = [threading.Thread(target=invoice, args=(o,)) for o in orders]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(numbers) == [1, 2]


# --- Règles ----------------------------------------------------------------------


@pytest.mark.parametrize("status", [OrderStatus.RECEIVED])
def test_commande_non_confirmee_refusee(w, status):
    response = create(w, w.order(status=status))
    assert response.status_code == 400
    assert not Invoice.objects.exists()


def test_commande_annulee_refusee(w):
    order = w.order(status=OrderStatus.RECEIVED)
    order_services.change_status(order, "cancelled", w.seller, cancel_reason="x")
    assert create(w, order).status_code == 400


def test_commande_livree_facturable(w):
    assert create(w, w.order(status=OrderStatus.DELIVERED)).status_code == 201


def test_une_seule_facture_valide_par_commande(w):
    order = w.order()
    assert create(w, order).status_code == 201
    response = create(w, order)
    assert response.status_code == 400
    assert "déjà une facture" in str(response.data)


def test_facture_figee_si_le_client_change(w):
    invoice = services.create_invoice(w.order(), w.seller)
    Customer.objects.filter(pk=w.customer.pk).update(name="Nouveau nom")
    assert (
        w.client.get(f"{INVOICES}{invoice.id}/").data["customer_snapshot"]["name"]
        == "خديجة بنت محمد"
    )


def test_annulation(w):
    invoice = services.create_invoice(w.order(), w.seller)
    url = f"{INVOICES}{invoice.id}/cancel/"
    assert w.client.post(url, {}, format="json").status_code == 400
    assert w.client.post(url, {"reason": "  "}, format="json").status_code == 400
    assert w.client.post(url, {"reason": "erreur"}, format="json").status_code == 200
    assert w.client.post(url, {"reason": "encore"}, format="json").status_code == 400
    assert w.client.delete(f"{INVOICES}{invoice.id}/").status_code == 405
    other = services.create_invoice(w.order(), w.seller)
    with pytest.raises(services.InvoiceError):
        services.cancel_invoice(other, "   ")


def test_annuler_la_commande_annule_la_facture(w):
    order = w.order()
    invoice = services.create_invoice(order, w.seller)
    order_services.change_status(order, "cancelled", w.seller, cancel_reason="client absent")
    invoice.refresh_from_db()
    assert invoice.status == Invoice.Status.CANCELLED
    assert order.number in invoice.cancel_reason


def test_filtres(w):
    services.create_invoice(w.order(), w.seller)
    cancelled = services.create_invoice(w.order(), w.seller)
    services.cancel_invoice(cancelled, "x")
    assert len(w.client.get(INVOICES, {"status": "issued"}).data) == 1
    assert [i["id"] for i in w.client.get(INVOICES, {"status": "cancelled"}).data] == [cancelled.id]
    assert len(w.client.get(INVOICES, {"year": YEAR}).data) == 2


# --- PDF ---------------------------------------------------------------------------


def page_count(pdf):
    return len(re.findall(rb"/Type /Page[^s]", pdf))


def test_pdf_bilingue_genere(w):
    invoice = services.create_invoice(w.order(), w.seller)
    response = w.client.get(f"{INVOICES}{invoice.id}/pdf/")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert f'filename="{invoice.number}.pdf"' in response["Content-Disposition"]
    pdf = response.content
    assert pdf.startswith(b"%PDF") and len(pdf) > 5000
    assert b"NotoNaskhArabic" in pdf  # police arabe intégrée
    assert b"Helvetica" in pdf  # police latine
    assert page_count(pdf) == 1


def test_pdf_sur_plusieurs_pages(w):
    invoice = services.create_invoice(w.order(lines=40), w.seller)
    assert page_count(w.client.get(f"{INVOICES}{invoice.id}/pdf/").content) == 2
    services.cancel_invoice(invoice, "x")  # tampon « ANNULÉE / ملغاة »
    assert page_count(w.client.get(f"{INVOICES}{invoice.id}/pdf/").content) == 2


def test_mise_en_forme_de_l_arabe():
    assert has_arabic("خديجة") and not has_arabic("Khadija") and not has_arabic(None)
    shaped = shape("خديجة")
    assert shaped != "خديجة"  # lettres liées et ordre droite → gauche
    assert shape("Amhat 10 kg") == "Amhat 10 kg"
    pieces = runs(shape("Wahaty · واحتي"))
    fonts = [font for font, _ in pieces]
    assert fonts[0] == "Helvetica" and "NotoNaskhArabic" in fonts
    assert "".join(text for _, text in pieces) == shape("Wahaty · واحتي")


# --- Isolation et rôles ----------------------------------------------------------


def test_un_autre_vendeur_ne_voit_rien(w):
    invoice = services.create_invoice(w.order(), w.seller)
    other = client_for(UserFactory(roles=[Role.SELLER]))
    assert other.get(INVOICES).data == []
    for url in (f"{INVOICES}{invoice.id}/", f"{INVOICES}{invoice.id}/pdf/"):
        assert other.get(url).status_code == 404
    assert (
        other.post(f"{INVOICES}{invoice.id}/cancel/", {"reason": "x"}, format="json").status_code
        == 404
    )
    response = other.post(INVOICES, {"order": w.order().id}, format="json")
    assert response.status_code == 400 and "order" in response.data


@pytest.mark.parametrize("roles", [[Role.FARMER], [Role.FIELD_AGENT]])
def test_factures_reservees_aux_vendeurs(roles):
    assert client_for(UserFactory(roles=roles)).get(INVOICES).status_code == 403


def test_direction_lit_et_telecharge_mais_ne_cree_pas(w):
    invoice = services.create_invoice(w.order(), w.seller)
    direction = client_for(UserFactory(roles=[Role.DIRECTION]))
    assert direction.get(f"{INVOICES}{invoice.id}/pdf/").status_code == 200
    assert direction.post(INVOICES, {"order": invoice.order_id}, format="json").status_code == 403


def test_textes_lisibles(w):
    invoice = services.create_invoice(w.order(), w.seller)
    assert str(invoice) == invoice.number
    assert str(InvoiceSequence.objects.get()).endswith(f"{YEAR} : 1")


@pytest.mark.parametrize("model", ["invoice", "invoicesequence"])
def test_administration_en_lecture_seule(client, w, model):
    services.create_invoice(w.order(), w.seller)
    client.force_login(User.objects.create_superuser("46000007", "Oasis-Adrar-2026"))
    assert client.get(f"/admin/invoices/{model}/").status_code == 200
