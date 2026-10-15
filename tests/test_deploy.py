"""T14 – Mise en ligne : Swagger, adresse de santé, CORS, données de démonstration."""

from io import StringIO

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from oases.models import DateVariety, Oasis

pytestmark = pytest.mark.django_db


def test_documentation_swagger_et_schema():
    client = APIClient()
    assert client.get("/api/docs/").status_code == 200
    schema = client.get("/api/schema/")
    assert schema.status_code == 200
    assert b"/api/market/listings/" in schema.content
    assert b"jwtAuth" in schema.content  # bouton « Authorize » avec le jeton


def test_schema_sans_aucun_avertissement(tmp_path):
    # Échoue s'il manque une description (champ non typé, vue sans sérialiseur…).
    call_command("spectacular", "--file", str(tmp_path / "schema.yml"), "--fail-on-warn")
    assert (tmp_path / "schema.yml").stat().st_size > 10_000


def test_adresse_de_sante():
    response = APIClient().get("/api/health/")
    assert response.status_code == 200 and response.json() == {"status": "ok"}


def test_cors_seulement_pour_le_site_trc(settings):
    settings.CORS_ALLOWED_ORIGINS = ["https://trc.pages.dev"]
    client = APIClient()
    ok = client.get("/api/varieties/", HTTP_ORIGIN="https://trc.pages.dev")
    assert ok["Access-Control-Allow-Origin"] == "https://trc.pages.dev"
    other = client.get("/api/varieties/", HTTP_ORIGIN="https://site-pirate.example")
    assert "Access-Control-Allow-Origin" not in other


def test_visiteur_ne_voit_aucune_donnee_privee():
    from django.contrib.auth.models import AnonymousUser

    from core.access import filter_readable
    from farms.models import Farm

    assert not filter_readable(Farm.objects.all(), AnonymousUser()).exists()
    assert APIClient().get("/api/farms/").status_code == 401


def test_donnees_de_demonstration_relancables():
    out = StringIO()
    call_command("seed_demo", stdout=out)
    call_command("seed_demo", stdout=out)
    assert "Démonstration prête." in out.getvalue()
    assert Oasis.objects.count() == 4
    assert DateVariety.objects.count() == 9
    chinguetti = Oasis.objects.get(region__slug="chinguetti")
    assert chinguetti.name_ar == "واحة شنقيط" and chinguetti.latitude is not None
    assert chinguetti.varieties.count() == 6
    # Visible sur le site public.
    data = APIClient().get("/api/oases/", {"region": "chinguetti"}).data
    assert [o["name_fr"] for o in data] == ["Oasis de Chinguetti"]
