"""T12 – Marché des dattes : seules les annonces publiées sont publiques, filtres, contact."""

import os
from decimal import Decimal
from types import SimpleNamespace
from urllib.parse import unquote

import pytest
from PIL import Image
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import Role, User
from market import services
from market.models import Listing, ListingPhoto, ListingStatus
from oases.models import DateVariety, Oasis, Region
from orders.models import Notification
from tests.factories import UserFactory
from tests.images import make_image

pytestmark = pytest.mark.django_db

PUBLIC, MINE, REVIEW = "/api/market/listings/", "/api/market/my-listings/", "/api/market/review/"
D = Decimal


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


@pytest.fixture
def w():
    azougui = Oasis.objects.create(
        region=Region.objects.get(slug="atar"), name_ar="آزوكي", name_fr="Azougui"
    )
    chinguetti = Oasis.objects.create(
        region=Region.objects.get(slug="chinguetti"), name_ar="شنقيط", name_fr="Chinguetti"
    )
    amhat = DateVariety.objects.create(
        name_ar="أمهات", name_fr="Amhat", ripening_start_month=7, ripening_end_month=8
    )
    tijib = DateVariety.objects.create(
        name_ar="تيجب", name_fr="Tijib", ripening_start_month=11, ripening_end_month=2
    )
    alice = UserFactory(full_name="Alice", roles=[Role.FARMER], phone="+22236112233")
    alice.profile.whatsapp = "+22246112233"
    alice.profile.save()
    bob = UserFactory(full_name="Bob", roles=[Role.SELLER], preferred_language="fr")
    bob.profile.business_name = "Dattes de Bob"
    bob.profile.save()
    direction = UserFactory(roles=[Role.DIRECTION])
    return SimpleNamespace(
        azougui=azougui,
        chinguetti=chinguetti,
        amhat=amhat,
        tijib=tijib,
        alice=alice,
        bob=bob,
        direction=direction,
        alice_client=client_for(alice),
        bob_client=client_for(bob),
        direction_client=client_for(direction),
    )


def listing(w, owner=None, status=ListingStatus.DRAFT, **fields):
    owner = owner or w.alice
    data = {
        "owner": owner,
        "variety": w.amhat,
        "oasis": w.azougui,
        "title": "Amhat de qualité",
        "language": "fr",
        "price_per_kg": D("350"),
        "quantity_kg": D("200"),
        "contact_phone": owner.phone,
        "status": status,
        **fields,
    }
    return Listing.objects.create(**data)


def payload(w, **overrides):
    return {
        "variety": w.amhat.id,
        "oasis": w.azougui.id,
        "title": "تمر أمهات ممتاز",
        "price_per_kg": "350",
        "quantity_kg": "500",
        **overrides,
    }


def ids(response):
    data = response.data["results"] if "results" in response.data else response.data
    return {row["id"] for row in data}


# --- Création et cycle -------------------------------------------------------------


def test_creation_d_un_brouillon_avec_valeurs_par_defaut(w):
    response = w.alice_client.post(MINE, payload(w), format="json")
    assert response.status_code == 201, response.data
    data = response.data
    assert data["status"] == "draft" and data["is_editable"] is True
    assert data["language"] == "ar"  # langue préférée d'Alice
    assert data["contact_phone"] == "+22236112233"
    assert data["whatsapp_phone"] == "+22246112233"
    assert data["id"] not in ids(APIClient().get(PUBLIC))


def test_cycle_complet_jusqu_a_la_vente(w):
    created = w.alice_client.post(MINE, payload(w), format="json").data
    url = f"{MINE}{created['id']}/"
    assert w.alice_client.post(f"{url}submit/").data["status"] == "pending"
    assert created["id"] not in ids(APIClient().get(PUBLIC))
    response = w.direction_client.post(f"{REVIEW}{created['id']}/approve/")
    assert response.status_code == 200 and response.data["status"] == "published"
    public = APIClient().get(PUBLIC)
    assert ids(public) == {created["id"]}
    assert public.data["results"][0]["published_at"] is not None
    notification = Notification.objects.get(user=w.alice)
    assert notification.kind == "listing_published"
    assert "تم نشر" in notification.message_ar
    assert w.alice_client.post(f"{url}sold/").data["status"] == "sold"
    assert ids(APIClient().get(PUBLIC)) == set()


def test_refus_avec_motif_puis_correction(w):
    item = listing(w, status=ListingStatus.PENDING)
    response = w.direction_client.post(f"{REVIEW}{item.id}/reject/", {}, format="json")
    assert response.status_code == 400
    response = w.direction_client.post(
        f"{REVIEW}{item.id}/reject/", {"reason": "Photo manquante"}, format="json"
    )
    assert response.status_code == 200
    assert (response.data["status"], response.data["rejection_reason"]) == (
        "rejected",
        "Photo manquante",
    )
    assert "Photo manquante" in Notification.objects.get(user=w.alice).message_fr
    url = f"{MINE}{item.id}/"
    assert w.alice_client.patch(url, {"price_per_kg": "300"}, format="json").status_code == 200
    resubmitted = w.alice_client.post(f"{url}submit/").data
    assert (resubmitted["status"], resubmitted["rejection_reason"]) == ("pending", "")


def test_motif_de_refus_vide_refuse(w):
    item = listing(w, status=ListingStatus.PENDING)
    with pytest.raises(services.ListingError):
        services.reject(item, w.direction, "   ")


def test_annonce_publiee_non_modifiable_sans_la_retirer(w):
    item = listing(w, status=ListingStatus.PUBLISHED)
    url = f"{MINE}{item.id}/"
    assert w.alice_client.patch(url, {"price_per_kg": "1"}, format="json").status_code == 400
    assert w.alice_client.post(f"{url}unpublish/").data["status"] == "draft"
    assert w.alice_client.patch(url, {"price_per_kg": "320"}, format="json").status_code == 200


@pytest.mark.parametrize(
    ("status", "action", "who"),
    [
        (ListingStatus.PUBLISHED, "submit", "owner"),
        (ListingStatus.SOLD, "submit", "owner"),
        (ListingStatus.DRAFT, "sold", "owner"),
        (ListingStatus.PENDING, "sold", "owner"),
        (ListingStatus.DRAFT, "unpublish", "owner"),
        (ListingStatus.DRAFT, "approve", "direction"),
        (ListingStatus.PUBLISHED, "approve", "direction"),
        (ListingStatus.REJECTED, "reject", "direction"),
    ],
)
def test_transitions_interdites(w, status, action, who):
    item = listing(w, status=status)
    if who == "owner":
        response = w.alice_client.post(f"{MINE}{item.id}/{action}/")
    else:
        response = w.direction_client.post(
            f"{REVIEW}{item.id}/{action}/", {"reason": "x"}, format="json"
        )
    assert response.status_code == 400
    item.refresh_from_db()
    assert item.status == status


# --- Seules les annonces publiées sont publiques ----------------------------------


def test_seules_les_annonces_publiees_sont_visibles(w):
    published = listing(w, status=ListingStatus.PUBLISHED)
    hidden = [
        listing(w, status=s)
        for s in (
            ListingStatus.DRAFT,
            ListingStatus.PENDING,
            ListingStatus.REJECTED,
            ListingStatus.SOLD,
        )
    ]
    deleted = listing(w, status=ListingStatus.PUBLISHED, is_active=False)
    anonymous = APIClient()
    assert ids(anonymous.get(PUBLIC)) == {published.id}
    assert anonymous.get(f"{PUBLIC}{published.id}/").status_code == 200
    for item in [*hidden, deleted]:
        assert anonymous.get(f"{PUBLIC}{item.id}/").status_code == 404


def test_supprimer_son_annonce_la_retire_du_marche(w):
    item = listing(w, status=ListingStatus.PUBLISHED)
    assert w.alice_client.delete(f"{MINE}{item.id}/").status_code == 204
    assert ids(APIClient().get(PUBLIC)) == set()
    assert Listing.objects.filter(pk=item.pk).exists()


def test_le_public_ne_voit_pas_les_donnees_privees(w):
    listing(w, owner=w.bob, status=ListingStatus.PUBLISHED, whatsapp_phone="")
    row = APIClient().get(PUBLIC).data["results"][0]
    assert row["seller_name"] == "Dattes de Bob"
    for private in ("owner", "status", "whatsapp_phone", "rejection_reason"):
        assert private not in row
    assert row["oasis"]["region"]["slug"] == "atar"


# --- Filtres, tri, pages -----------------------------------------------------------


@pytest.fixture
def market(w):
    return SimpleNamespace(
        cheap=listing(w, status="published", price_per_kg=D("200"), quantity_kg=D("50")),
        tijib=listing(
            w,
            status="published",
            variety=w.tijib,
            oasis=w.chinguetti,
            price_per_kg=D("500"),
            quantity_kg=D("1000"),
            title="Tijib sec de Chinguetti",
        ),
        mid=listing(w, owner=w.bob, status="published", price_per_kg=D("350")),
    )


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"variety": "tijib"}, {"tijib"}),
        ({"variety": "amhat"}, {"cheap", "mid"}),
        ({"oasis": "azougui"}, {"cheap", "mid"}),
        ({"region": "chinguetti"}, {"tijib"}),
        ({"min_price": "300"}, {"tijib", "mid"}),
        ({"max_price": "350"}, {"cheap", "mid"}),
        ({"min_price": "300", "max_price": "400"}, {"mid"}),
        ({"min_quantity": "500"}, {"tijib"}),
        ({"search": "chinguetti"}, {"tijib"}),
        ({"region": "atar", "max_price": "250"}, {"cheap"}),
    ],
)
def test_filtres(w, market, params, expected):
    names = {getattr(market, n).id: n for n in ("cheap", "tijib", "mid")}
    result = APIClient().get(PUBLIC, params)
    assert {names[i] for i in ids(result)} == expected


def test_tri_par_prix_et_pages(w, market):
    rows = APIClient().get(PUBLIC, {"ordering": "price_per_kg"}).data["results"]
    assert [r["price_per_kg"] for r in rows] == ["200.00", "350.00", "500.00"]
    rows = APIClient().get(PUBLIC, {"ordering": "-price_per_kg"}).data["results"]
    assert rows[0]["price_per_kg"] == "500.00"
    page = APIClient().get(PUBLIC, {"page_size": 2}).data
    assert page["count"] == 3 and len(page["results"]) == 2 and page["next"]


# --- Contact WhatsApp / téléphone --------------------------------------------------


def test_lien_whatsapp_et_telephone(w):
    item = listing(w, status="published", whatsapp_phone="+22246112233", title="Amhat bio")
    row = APIClient().get(f"{PUBLIC}{item.id}/").data
    assert row["whatsapp_link"].startswith("https://wa.me/22246112233?text=")
    assert "Amhat bio" in unquote(row["whatsapp_link"]) and "Wahaty" in unquote(
        row["whatsapp_link"]
    )
    assert row["phone_link"] == "tel:+22236112233"


def test_lien_whatsapp_en_arabe_et_numero_de_secours(w):
    item = listing(w, status="published", language="ar", title="تمر", whatsapp_phone="")
    link = item.whatsapp_link
    assert link.startswith("https://wa.me/22236112233?text=")  # pas de WhatsApp : téléphone
    assert "واحتي" in unquote(link)


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"price_per_kg": "0"}, "price_per_kg"),
        ({"price_per_kg": "-5"}, "price_per_kg"),
        ({"quantity_kg": "0"}, "quantity_kg"),
        ({"contact_phone": "0612"}, "contact_phone"),
        ({"whatsapp_phone": "abc"}, "whatsapp_phone"),
        ({"title": ""}, "title"),
    ],
)
def test_annonce_invalide(w, overrides, field):
    response = w.alice_client.post(MINE, payload(w, **overrides), format="json")
    assert response.status_code == 400
    assert field in response.data


def test_variete_ou_oasis_desactivee_refusee(w):
    DateVariety.objects.filter(pk=w.amhat.pk).update(is_active=False)
    assert w.alice_client.post(MINE, payload(w), format="json").status_code == 400


def test_numeros_normalises(w):
    response = w.bob_client.post(
        MINE, payload(w, contact_phone="22 33 44 55", whatsapp_phone="46 33 44 55"), format="json"
    )
    assert response.status_code == 201
    assert (response.data["contact_phone"], response.data["whatsapp_phone"]) == (
        "+22222334455",
        "+22246334455",
    )
    assert response.data["language"] == "fr"


# --- Photos ------------------------------------------------------------------------


def test_photos_redimensionnees_et_limitees_a_5(w):
    item = listing(w)
    url = f"{MINE}{item.id}/photos/"
    first = w.alice_client.post(url, {"image": make_image(3000, 2000)}, format="multipart")
    assert first.status_code == 201, first.data
    with Image.open(ListingPhoto.objects.get(pk=first.data["id"]).image.path) as img:
        assert max(img.size) == 1600
    for _ in range(4):
        assert (
            w.alice_client.post(url, {"image": make_image()}, format="multipart").status_code == 201
        )
    sixth = w.alice_client.post(url, {"image": make_image()}, format="multipart")
    assert sixth.status_code == 400
    assert "5 photos" in str(sixth.data)


def test_photo_invalide(w):
    item = listing(w)
    response = w.alice_client.post(f"{MINE}{item.id}/photos/", {}, format="multipart")
    assert response.status_code == 400


def test_photos_bloquees_quand_l_annonce_est_publiee(w):
    item = listing(w)
    photo = services.add_photo(item, make_image())
    Listing.objects.filter(pk=item.pk).update(status=ListingStatus.PUBLISHED)
    url = f"{MINE}{item.id}/photos/"
    assert w.alice_client.post(url, {"image": make_image()}, format="multipart").status_code == 400
    assert w.alice_client.delete(f"{url}{photo.id}/").status_code == 400


def test_supprimer_une_photo_efface_le_fichier(w):
    item = listing(w)
    photo = services.add_photo(item, make_image())
    path = photo.image.path
    url = f"{MINE}{item.id}/photos/"
    assert w.alice_client.delete(f"{url}{photo.id}/").status_code == 204
    assert not os.path.exists(path)
    assert w.alice_client.delete(f"{url}{photo.id}/").status_code == 404


def test_photo_d_une_autre_annonce_introuvable(w):
    mine, other = listing(w), listing(w, owner=w.bob)
    photo = services.add_photo(other, make_image())
    assert w.alice_client.delete(f"{MINE}{mine.id}/photos/{photo.id}/").status_code == 404
    assert ListingPhoto.objects.filter(pk=photo.pk).exists()


def test_photos_visibles_par_le_public(w):
    item = listing(w)
    services.add_photo(item, make_image(), order=1)
    Listing.objects.filter(pk=item.pk).update(status=ListingStatus.PUBLISHED)
    photos = APIClient().get(f"{PUBLIC}{item.id}/").data["photos"]
    assert len(photos) == 1 and photos[0]["image"].endswith(".jpg")


# --- Isolation et rôles ------------------------------------------------------------


def test_b_ne_voit_ni_ne_modifie_les_annonces_d_alice(w):
    item = listing(w)
    assert w.bob_client.get(MINE).data == []
    for method, suffix in (("get", ""), ("patch", ""), ("delete", ""), ("post", "submit/")):
        response = getattr(w.bob_client, method)(f"{MINE}{item.id}/{suffix}", {}, format="json")
        assert response.status_code == 404
    response = w.bob_client.post(
        f"{MINE}{item.id}/photos/", {"image": make_image()}, format="multipart"
    )
    assert response.status_code == 404
    item.refresh_from_db()
    assert item.status == ListingStatus.DRAFT


def test_agent_publie_pour_son_agriculteur(w):
    agent = UserFactory(roles=[Role.FIELD_AGENT])
    farmer = UserFactory(registered_by=agent)
    response = client_for(agent).post(MINE, payload(w, owner=farmer.id), format="json")
    assert response.status_code == 201
    assert Listing.objects.get(pk=response.data["id"]).owner == farmer
    response = client_for(agent).post(MINE, payload(w, owner=w.alice.id), format="json")
    assert response.status_code == 403


def test_direction_ne_publie_pas_d_annonce_a_son_nom(w):
    assert w.direction_client.post(MINE, payload(w), format="json").status_code == 403


@pytest.mark.parametrize("roles", [[Role.FARMER], [Role.SELLER], [Role.FIELD_AGENT]])
def test_validation_reservee_a_la_direction(w, roles):
    item = listing(w, status=ListingStatus.PENDING)
    client = client_for(UserFactory(roles=roles))
    assert client.get(REVIEW).status_code == 403
    assert client.post(f"{REVIEW}{item.id}/approve/").status_code == 403


def test_file_de_validation_de_la_direction(w):
    pending = listing(w, status=ListingStatus.PENDING)
    published = listing(w, status=ListingStatus.PUBLISHED)
    assert ids(w.direction_client.get(REVIEW)) == {pending.id}
    assert ids(w.direction_client.get(REVIEW, {"status": "published"})) == {published.id}
    assert w.direction_client.get(f"{REVIEW}999999/").status_code == 404


def test_textes_lisibles(w):
    item = listing(w)
    photo = services.add_photo(item, make_image(), order=2)
    assert str(item) == "Amhat de qualité"
    assert str(photo) == "Photo 2 – Amhat de qualité"


def test_administration_publier(client, w):
    item = listing(w, status=ListingStatus.PENDING)
    draft = listing(w)
    client.force_login(User.objects.create_superuser("46000008", "Oasis-Adrar-2026"))
    assert client.get("/admin/market/listing/").status_code == 200
    client.post(
        "/admin/market/listing/",
        {"action": "approve_listings", "_selected_action": [item.id, draft.id]},
    )
    item.refresh_from_db()
    draft.refresh_from_db()
    assert item.status == ListingStatus.PUBLISHED
    assert draft.status == ListingStatus.DRAFT  # un brouillon n'est pas publiable
