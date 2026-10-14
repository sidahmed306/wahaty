"""T05 – Régions, oasis, variétés : lecture publique, gestion par la Direction, photos."""

from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from PIL import Image
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import Role
from core.images import MAX_SIDE_PX, validate_image_size
from oases.models import DateVariety, Oasis, OasisPhoto, Region
from tests.factories import UserFactory
from tests.images import make_image

pytestmark = pytest.mark.django_db

REGIONS, OASES, VARIETIES, PHOTOS = (
    "/api/regions/",
    "/api/oases/",
    "/api/varieties/",
    "/api/oasis-photos/",
)


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


@pytest.fixture
def direction():
    return client_for(UserFactory(roles=[Role.DIRECTION]))


@pytest.fixture
def anon():
    return APIClient()


@pytest.fixture
def data():
    atar = Region.objects.get(slug="atar")
    chinguetti = Region.objects.get(slug="chinguetti")
    amhat = DateVariety.objects.create(
        name_ar="أمهات",
        name_fr="Amhat",
        texture="soft",
        ripening_start_month=7,
        ripening_end_month=8,
    )
    tijib = DateVariety.objects.create(
        name_ar="تيجب",
        name_fr="Tijib",
        texture="dry",
        ripening_start_month=11,
        ripening_end_month=2,
    )
    azougui = Oasis.objects.create(region=atar, name_ar="آزوكي", name_fr="Azougui")
    azougui.varieties.add(amhat)
    oasis_chinguetti = Oasis.objects.create(
        region=chinguetti, name_ar="واحة شنقيط", name_fr="Oasis de Chinguetti"
    )
    oasis_chinguetti.varieties.add(amhat, tijib)
    hidden = Oasis.objects.create(region=atar, name_ar="مخفية", name_fr="Cachée", is_active=False)
    return SimpleNamespace(
        atar=atar,
        chinguetti=chinguetti,
        amhat=amhat,
        tijib=tijib,
        azougui=azougui,
        oasis_chinguetti=oasis_chinguetti,
        hidden=hidden,
    )


def slugs(response):
    return {row["slug"] for row in response.data}


# --- Régions de l'Adrar --------------------------------------------------------


def test_regions_de_l_adrar_creees_au_depart(anon):
    response = anon.get(REGIONS)
    assert response.status_code == 200
    assert [(r["name_fr"], r["name_ar"]) for r in response.data] == [
        ("Atar", "أطار"),
        ("Chinguetti", "شنقيط"),
        ("Ouadane", "وادان"),
        ("Aoujeft", "أوجفت"),
    ]


def test_nombre_d_oasis_actives_par_region(anon, data):
    counts = {r["slug"]: r["oases_count"] for r in anon.get(REGIONS).data}
    assert counts == {"atar": 1, "chinguetti": 1, "ouadane": 0, "aoujeft": 0}


# --- Lecture publique ----------------------------------------------------------


def test_lecture_sans_compte(anon, data):
    assert slugs(anon.get(OASES)) == {"azougui", "oasis-de-chinguetti"}
    detail = anon.get(f"{OASES}azougui/")
    assert detail.status_code == 200
    assert detail.data["name_ar"] == "آزوكي"
    assert detail.data["region_detail"]["slug"] == "atar"
    assert detail.data["varieties_detail"][0]["name_fr"] == "Amhat"
    assert anon.get(f"{VARIETIES}tijib/").data["oases"][0]["slug"] == "oasis-de-chinguetti"


def test_elements_desactives_caches_au_public(anon, data):
    assert anon.get(f"{OASES}cachee/").status_code == 404


def test_direction_voit_aussi_les_desactives(direction, data):
    assert "cachee" in slugs(direction.get(OASES))


def test_lecture_avec_compte_agriculteur(data):
    assert client_for(UserFactory()).get(OASES).status_code == 200


# --- Écriture réservée à la Direction ------------------------------------------


@pytest.mark.parametrize(
    "roles", [[Role.FARMER], [Role.SELLER], [Role.FIELD_AGENT], [Role.FARMER, Role.SELLER]]
)
def test_ecriture_refusee_aux_non_admins(data, roles):
    client = client_for(UserFactory(roles=roles))
    payload = {"name_ar": "س", "name_fr": "X", "region": data.atar.id}
    assert client.post(OASES, payload, format="json").status_code == 403
    assert client.patch(f"{OASES}azougui/", {"name_fr": "Y"}, format="json").status_code == 403
    assert client.delete(f"{OASES}azougui/").status_code == 403
    assert client.post(REGIONS, {"name_ar": "س", "name_fr": "X"}, format="json").status_code == 403
    assert client.delete(f"{VARIETIES}amhat/").status_code == 403
    data.azougui.refresh_from_db()
    assert data.azougui.name_fr == "Azougui" and data.azougui.is_active


def test_ecriture_refusee_sans_compte(anon, data):
    response = anon.post(REGIONS, {"name_ar": "س", "name_fr": "X"}, format="json")
    assert response.status_code == 401


def test_ajout_d_une_oasis_sans_changer_le_code(direction, anon, data):
    response = direction.post(
        OASES,
        {
            "name_ar": "ترجيت",
            "name_fr": "Terjit",
            "region": Region.objects.get(slug="aoujeft").id,
            "description_fr": "Oasis avec source d'eau chaude.",
            "latitude": "20.250000",
            "longitude": "-13.080000",
            "varieties": [data.amhat.id],
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    assert response.data["slug"] == "terjit"
    public = anon.get(OASES, {"region": "aoujeft"})
    assert slugs(public) == {"terjit"}


def test_ajout_d_une_region_sans_changer_le_code(direction, anon):
    response = direction.post(REGIONS, {"name_ar": "أطار الجديدة", "name_fr": "Atar Nord"})
    assert response.status_code == 201
    assert "atar-nord" in slugs(anon.get(REGIONS))


def test_ajout_d_une_variete(direction):
    response = direction.post(
        VARIETIES,
        {
            "name_ar": "لكصبه",
            "name_fr": "Lagsiba",
            "texture": "semi_dry",
            "ripening_start_month": 7,
            "ripening_end_month": 9,
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    assert response.data["slug"] == "lagsiba"


def test_modification_par_la_direction(direction, data):
    response = direction.patch(
        f"{OASES}azougui/", {"description_ar": "واحة تاريخية"}, format="json"
    )
    assert response.status_code == 200
    data.azougui.refresh_from_db()
    assert data.azougui.description_ar == "واحة تاريخية"


def test_suppression_douce(direction, anon, data):
    assert direction.delete(f"{OASES}azougui/").status_code == 204
    data.azougui.refresh_from_db()
    assert data.azougui.is_active is False  # toujours en base
    assert anon.get(f"{OASES}azougui/").status_code == 404
    assert direction.get(f"{OASES}azougui/").status_code == 200


def test_region_utilisee_ne_peut_pas_etre_effacee_vraiment(data):
    with pytest.raises(Exception), transaction.atomic():  # noqa: B017 – ProtectedError
        data.atar.delete()


# --- Validation (bilingue obligatoire, GPS, mois) ------------------------------


@pytest.mark.parametrize("missing", ["name_ar", "name_fr"])
def test_nom_arabe_et_francais_obligatoires(direction, data, missing):
    payload = {"name_ar": "س", "name_fr": "X", "region": data.atar.id}
    payload.pop(missing)
    response = direction.post(OASES, payload, format="json")
    assert response.status_code == 400
    assert missing in response.data


@pytest.mark.parametrize(
    ("field", "value"), [("latitude", "95"), ("longitude", "-200"), ("latitude", "abc")]
)
def test_gps_invalide_refuse(direction, data, field, value):
    payload = {"name_ar": "س", "name_fr": "X", "region": data.atar.id, field: value}
    response = direction.post(OASES, payload, format="json")
    assert response.status_code == 400
    assert field in response.data


@pytest.mark.parametrize("month", [0, 13])
def test_mois_invalide_refuse(direction, month):
    payload = {
        "name_ar": "س",
        "name_fr": "X",
        "ripening_start_month": month,
        "ripening_end_month": 5,
    }
    response = direction.post(VARIETIES, payload, format="json")
    assert response.status_code == 400
    assert "ripening_start_month" in response.data


def test_meme_nom_dans_la_meme_region_refuse(direction, data):
    payload = {"name_ar": "آزوكي", "name_fr": "Azougui", "region": data.atar.id}
    assert direction.post(OASES, payload, format="json").status_code == 400


def test_oasis_dans_une_region_desactivee_refusee(direction):
    region = Region.objects.create(name_ar="قديمة", name_fr="Ancienne", is_active=False)
    payload = {"name_ar": "س", "name_fr": "X", "region": region.id}
    response = direction.post(OASES, payload, format="json")
    assert response.status_code == 400
    assert "region" in response.data


def test_base_refuse_mois_et_gps_hors_limites(data):
    with pytest.raises(IntegrityError), transaction.atomic():
        DateVariety.objects.create(
            name_ar="خطأ", name_fr="Erreur", ripening_start_month=13, ripening_end_month=1
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        Oasis.objects.create(region=data.atar, name_ar="خطأ", name_fr="Erreur", latitude=91)


def test_identifiant_web_unique(data):
    other = Oasis.objects.create(region=data.chinguetti, name_ar="آزوكي ٢", name_fr="Azougui")
    assert other.slug == "azougui-2"


# --- Filtres -------------------------------------------------------------------


def test_filtres_oasis(anon, data):
    assert slugs(anon.get(OASES, {"region": "chinguetti"})) == {"oasis-de-chinguetti"}
    assert slugs(anon.get(OASES, {"variety": "amhat"})) == {"azougui", "oasis-de-chinguetti"}
    assert slugs(anon.get(OASES, {"variety": "tijib"})) == {"oasis-de-chinguetti"}
    assert slugs(anon.get(OASES, {"search": "آزو"})) == {"azougui"}
    assert slugs(anon.get(OASES, {"search": "chinguetti"})) == {"oasis-de-chinguetti"}


def test_filtres_varietes(anon, data):
    assert slugs(anon.get(VARIETIES, {"oasis": "azougui"})) == {"amhat"}
    assert slugs(anon.get(VARIETIES, {"texture": "dry"})) == {"tijib"}
    assert slugs(anon.get(VARIETIES, {"search": "تيج"})) == {"tijib"}


@pytest.mark.parametrize(
    ("month", "expected"),
    [(7, {"amhat"}), (8, {"amhat"}), (9, set()), (11, {"tijib"}), (1, {"tijib"}), (2, {"tijib"})],
)
def test_filtre_saison_y_compris_a_cheval_sur_deux_annees(anon, data, month, expected):
    assert slugs(anon.get(VARIETIES, {"in_season": month})) == expected
    for variety in (data.amhat, data.tijib):
        assert variety.is_in_season(month) == (variety.slug in expected)


# --- Photos --------------------------------------------------------------------


def test_photo_redimensionnee_et_publique(direction, anon, data):
    response = direction.post(
        PHOTOS,
        {
            "oasis": "azougui",
            "image": make_image(3000, 2000),
            "caption_fr": "Palmeraie",
            "order": 1,
        },
        format="multipart",
    )
    assert response.status_code == 201, response.data
    photo = OasisPhoto.objects.get(pk=response.data["id"])
    with Image.open(photo.image.path) as img:
        assert max(img.size) == MAX_SIDE_PX
        assert img.format == "JPEG"
    listed = anon.get(PHOTOS, {"oasis": "azougui"})
    assert [p["id"] for p in listed.data] == [photo.id]
    assert anon.get(f"{OASES}azougui/").data["photos"][0]["caption_fr"] == "Palmeraie"


def test_photo_petite_non_agrandie_et_png_transparent_accepte(direction, data):
    response = direction.post(
        PHOTOS,
        {"oasis": "azougui", "image": make_image(400, 300, mode="RGBA")},
        format="multipart",
    )
    assert response.status_code == 201
    with Image.open(OasisPhoto.objects.get().image.path) as img:
        assert img.size == (400, 300)


def test_fichier_qui_n_est_pas_une_image_refuse(direction, data):
    from django.core.files.uploadedfile import SimpleUploadedFile

    fake = SimpleUploadedFile("virus.jpg", b"pas une image", content_type="image/jpeg")
    response = direction.post(PHOTOS, {"oasis": "azougui", "image": fake}, format="multipart")
    assert response.status_code == 400
    assert "image" in response.data


def test_image_trop_lourde_refusee():
    with pytest.raises(ValidationError):
        validate_image_size(SimpleNamespace(size=6 * 1024 * 1024))
    validate_image_size(SimpleNamespace(size=1024))


def test_photo_refusee_aux_non_admins(data):
    client = client_for(UserFactory())
    response = client.post(PHOTOS, {"oasis": "azougui", "image": make_image()}, format="multipart")
    assert response.status_code == 403


def test_suppression_d_une_photo_efface_le_fichier(direction, data):
    photo = OasisPhoto.objects.create(oasis=data.azougui, image=make_image())
    path = photo.image.path
    assert direction.delete(f"{PHOTOS}{photo.id}/").status_code == 204
    assert not OasisPhoto.objects.exists()
    import os

    assert not os.path.exists(path)


def test_photos_d_une_oasis_desactivee_cachees(anon, direction, data):
    OasisPhoto.objects.create(oasis=data.hidden, image=make_image())
    assert anon.get(PHOTOS).data == []
    assert len(direction.get(PHOTOS).data) == 1


def test_photo_d_une_variete(direction, anon, data):
    response = direction.patch(
        f"{VARIETIES}amhat/", {"photo": make_image(2000, 2000)}, format="multipart"
    )
    assert response.status_code == 200, response.data
    data.amhat.refresh_from_db()
    with Image.open(data.amhat.photo.path) as img:
        assert img.size == (MAX_SIDE_PX, MAX_SIDE_PX)
    assert anon.get(f"{VARIETIES}amhat/").data["photo"].endswith(".jpg")


def test_textes_lisibles(data):
    assert str(data.atar) == "Atar"
    assert str(data.amhat) == "Amhat"
    assert str(data.azougui) == "Azougui"
    photo = OasisPhoto(oasis=data.azougui, order=2)
    assert str(photo) == "Photo 2 – Azougui"


# --- Administration (Direction) ------------------------------------------------


@pytest.mark.parametrize("model", ["region", "oasis", "datevariety"])
def test_pages_d_administration(client, data, model):
    from accounts.models import User

    client.force_login(User.objects.create_superuser("46000001", "Oasis-Adrar-2026"))
    assert client.get(f"/admin/oases/{model}/").status_code == 200
    assert client.get(f"/admin/oases/{model}/add/").status_code == 200
