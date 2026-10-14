"""T05 – Profil : oasis de rattachement et photo."""

import pytest
from PIL import Image

from oases.models import Oasis, Region
from tests.images import make_image

pytestmark = pytest.mark.django_db

ME, PHOTO = "/api/auth/me/", "/api/auth/me/photo/"


@pytest.fixture
def azougui():
    return Oasis.objects.create(
        region=Region.objects.get(slug="atar"), name_ar="آزوكي", name_fr="Azougui"
    )


def test_choisir_son_oasis(auth_client, user, azougui):
    response = auth_client.patch(ME, {"profile": {"oasis": azougui.id}}, format="json")
    assert response.status_code == 200, response.data
    user.profile.refresh_from_db()
    assert user.profile.oasis == azougui


def test_oasis_desactivee_refusee(auth_client, azougui):
    azougui.is_active = False
    azougui.save()
    response = auth_client.patch(ME, {"profile": {"oasis": azougui.id}}, format="json")
    assert response.status_code == 400


def test_photo_de_profil(auth_client, user):
    response = auth_client.put(PHOTO, {"photo": make_image(2400, 1200)}, format="multipart")
    assert response.status_code == 200, response.data
    user.profile.refresh_from_db()
    first_path = user.profile.photo.path
    with Image.open(first_path) as img:
        assert img.size == (1600, 800)
    # Remplacer : l'ancienne photo est effacée.
    auth_client.put(PHOTO, {"photo": make_image(name="nouvelle.png")}, format="multipart")
    import os

    assert not os.path.exists(first_path)
    assert auth_client.delete(PHOTO).status_code == 204
    user.profile.refresh_from_db()
    assert not user.profile.photo


def test_photo_de_profil_invalide(auth_client):
    assert auth_client.put(PHOTO, {}, format="multipart").status_code == 400


def test_photo_de_profil_sans_connexion(api_client, db):
    assert api_client.put(PHOTO, {"photo": make_image()}, format="multipart").status_code == 401
