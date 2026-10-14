"""T06 – Fermes, palmiers, récoltes : totaux exacts, isolation, agent limité à ses inscrits."""

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import Role
from farms.models import Farm, Harvest, PalmGroup
from oases.models import DateVariety, Oasis, Region
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

FARMS, PALMS, HARVESTS = "/api/farms/", "/api/palm-groups/", "/api/harvests/"


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


def ids(response):
    return {row["id"] for row in response.data}


@pytest.fixture
def w():
    """Jeu de données connu : Alice (2 variétés, 3 récoltes), Bob, un agent et ses inscrits."""
    atar = Region.objects.get(slug="atar")
    azougui = Oasis.objects.create(region=atar, name_ar="آزوكي", name_fr="Azougui")
    amhat = DateVariety.objects.create(
        name_ar="أمهات", name_fr="Amhat", ripening_start_month=7, ripening_end_month=8
    )
    tijib = DateVariety.objects.create(
        name_ar="تيجب", name_fr="Tijib", ripening_start_month=11, ripening_end_month=2
    )
    alice = UserFactory(full_name="Alice", roles=[Role.FARMER])
    bob = UserFactory(full_name="Bob", roles=[Role.FARMER, Role.SELLER])
    agent = UserFactory(roles=[Role.FIELD_AGENT])
    managed = UserFactory(full_name="Mohamed", registered_by=agent)
    claimed = UserFactory(full_name="Sidi", registered_by=agent, claimed_at=timezone.now())

    def farm(owner, name):
        return Farm.objects.create(owner=owner, oasis=azougui, name=name, created_by=owner)

    alice_farm = farm(alice, "Ferme d'Alice")
    PalmGroup.objects.create(farm=alice_farm, variety=amhat, productive_count=100, young_count=20)
    PalmGroup.objects.create(farm=alice_farm, variety=tijib, productive_count=30, young_count=10)
    for season, variety, kg, day in [
        (2025, amhat, "500.50", date(2025, 7, 20)),
        (2025, amhat, "250.00", date(2025, 8, 10)),
        (2025, tijib, "120.00", date(2025, 12, 1)),
        (2026, amhat, "900.00", date(2026, 7, 25)),
    ]:
        Harvest.objects.create(
            farm=alice_farm,
            variety=variety,
            season=season,
            harvest_date=day,
            quantity_kg=Decimal(kg),
            created_by=alice,
        )
    bob_farm = farm(bob, "Ferme de Bob")
    PalmGroup.objects.create(farm=bob_farm, variety=amhat, productive_count=7)
    return SimpleNamespace(
        azougui=azougui,
        amhat=amhat,
        tijib=tijib,
        alice=alice,
        bob=bob,
        agent=agent,
        managed=managed,
        claimed=claimed,
        alice_farm=alice_farm,
        bob_farm=bob_farm,
        managed_farm=farm(managed, "Ferme de Mohamed"),
        claimed_farm=farm(claimed, "Ferme de Sidi"),
    )


# --- Totaux ------------------------------------------------------------------


def test_totaux_de_palmiers_dans_la_liste(w):
    row = client_for(w.alice).get(FARMS).data[0]
    assert (row["productive_palms"], row["young_palms"], row["total_palms"]) == (130, 30, 160)


def test_ferme_sans_palmiers_a_zero(w):
    row = client_for(w.managed).get(FARMS).data[0]
    assert (row["productive_palms"], row["young_palms"], row["total_palms"]) == (0, 0, 0)


def test_resume_d_une_ferme(w):
    data = client_for(w.alice).get(f"{FARMS}{w.alice_farm.id}/summary/").data
    assert [
        (p["variety"]["name_fr"], p["productive"], p["young"], p["total"]) for p in data["palms"]
    ] == [
        ("Amhat", 100, 20, 120),
        ("Tijib", 30, 10, 40),
    ]
    assert data["palms_total"] == {"productive": 130, "young": 30, "total": 160}
    assert [
        (p["season"], p["variety"]["name_fr"], p["total_kg"], p["harvests_count"])
        for p in data["production"]
    ] == [
        (2026, "Amhat", "900.00", 1),
        (2025, "Amhat", "750.50", 2),
        (2025, "Tijib", "120.00", 1),
    ]
    assert data["production_by_season"] == [
        {"season": 2026, "total_kg": "900.00"},
        {"season": 2025, "total_kg": "870.50"},
    ]


def test_totaux_des_recoltes_avec_filtre_saison(w):
    data = client_for(w.alice).get(f"{HARVESTS}totals/", {"season": 2025}).data
    assert data["production_by_season"] == [{"season": 2025, "total_kg": "870.50"}]


def test_totaux_des_palmiers_toutes_fermes_visibles(w):
    data = client_for(w.alice).get(f"{PALMS}totals/").data
    assert data["palms_total"] == {"productive": 130, "young": 30, "total": 160}
    direction = client_for(UserFactory(roles=[Role.DIRECTION]))
    assert direction.get(f"{PALMS}totals/").data["palms_total"]["total"] == 167


def test_suppression_douce_exclue_des_totaux(w):
    client = client_for(w.alice)
    harvest = Harvest.objects.get(season=2026)
    assert client.delete(f"{HARVESTS}{harvest.id}/").status_code == 204
    harvest.refresh_from_db()
    assert harvest.is_active is False
    data = client.get(f"{FARMS}{w.alice_farm.id}/summary/").data
    assert data["production_by_season"] == [{"season": 2025, "total_kg": "870.50"}]
    group = PalmGroup.objects.get(farm=w.alice_farm, variety=w.tijib)
    assert client.delete(f"{PALMS}{group.id}/").status_code == 204
    assert client.get(FARMS).data[0]["total_palms"] == 120


def test_ferme_supprimee_cachee_avec_ses_lignes(w):
    client = client_for(w.alice)
    assert client.delete(f"{FARMS}{w.alice_farm.id}/").status_code == 204
    assert Farm.objects.filter(pk=w.alice_farm.pk).exists()
    assert client.get(FARMS).data == []
    assert client.get(PALMS).data == []
    assert client.get(HARVESTS).data == []


# --- Saisie et validation ----------------------------------------------------


def test_agriculteur_cree_sa_ferme_ses_palmiers_et_ses_recoltes(w):
    client = client_for(w.alice)
    farm = client.post(
        FARMS,
        {"name": "Nouvelle ferme", "oasis": w.azougui.id, "area_hectares": "2.50"},
        format="json",
    )
    assert farm.status_code == 201, farm.data
    assert farm.data["owner"] == w.alice.id and farm.data["created_by"] == w.alice.id
    palms = client.post(
        PALMS,
        {"farm": farm.data["id"], "variety": w.amhat.id, "productive_count": 12, "young_count": 3},
        format="json",
    )
    assert palms.status_code == 201, palms.data
    assert palms.data["total_count"] == 15
    harvest = client.post(
        HARVESTS,
        {
            "farm": farm.data["id"],
            "variety": w.amhat.id,
            "harvest_date": "2026-08-01",
            "quantity_kg": "80.5",
        },
        format="json",
    )
    assert harvest.status_code == 201, harvest.data
    assert harvest.data["season"] == 2026  # saison = année de récolte par défaut


def test_saison_a_cheval_sur_deux_annees(w):
    payload = {
        "farm": w.alice_farm.id,
        "variety": w.tijib.id,
        "harvest_date": "2026-01-15",
        "season": 2025,
        "quantity_kg": "40",
    }
    assert client_for(w.alice).post(HARVESTS, payload, format="json").status_code == 201


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"quantity_kg": "0"}, "quantity_kg"),
        ({"quantity_kg": "-5"}, "quantity_kg"),
        ({"harvest_date": str(date.today() + timedelta(days=3))}, "harvest_date"),
        ({"season": 2020}, "season"),
        ({"season": 1990}, "season"),
    ],
)
def test_recolte_invalide_refusee(w, changes, field):
    payload = {
        "farm": w.alice_farm.id,
        "variety": w.amhat.id,
        "harvest_date": "2026-07-01",
        "quantity_kg": "10",
        **changes,
    }
    response = client_for(w.alice).post(HARVESTS, payload, format="json")
    assert response.status_code == 400
    assert field in response.data


@pytest.mark.parametrize("field", ["productive_count", "young_count"])
def test_nombre_de_palmiers_negatif_refuse(w, field):
    payload = {"farm": w.alice_farm.id, "variety": w.amhat.id, field: -1}
    PalmGroup.objects.filter(farm=w.alice_farm).delete()
    response = client_for(w.alice).post(PALMS, payload, format="json")
    assert response.status_code == 400
    assert field in response.data


def test_meme_variete_deux_fois_dans_une_ferme_refusee(w):
    payload = {"farm": w.alice_farm.id, "variety": w.amhat.id, "productive_count": 1}
    response = client_for(w.alice).post(PALMS, payload, format="json")
    assert response.status_code == 400
    assert "variety" in response.data


def test_modifier_une_ligne_de_palmiers(w):
    group = PalmGroup.objects.get(farm=w.alice_farm, variety=w.amhat)
    response = client_for(w.alice).patch(
        f"{PALMS}{group.id}/", {"productive_count": 110}, format="json"
    )
    assert response.status_code == 200
    assert response.data["total_count"] == 130


def test_meme_nom_de_ferme_refuse(w):
    client = client_for(w.alice)
    response = client.post(FARMS, {"name": "ferme d'alice", "oasis": w.azougui.id}, format="json")
    assert response.status_code == 400
    other = Farm.objects.create(owner=w.alice, oasis=w.azougui, name="Autre", created_by=w.alice)
    response = client.patch(f"{FARMS}{other.id}/", {"name": "Ferme d'Alice"}, format="json")
    assert response.status_code == 400
    assert (
        client.patch(f"{FARMS}{other.id}/", {"area_hectares": "1"}, format="json").status_code
        == 200
    )


def test_oasis_desactivee_refusee(w):
    w.azougui.is_active = False
    w.azougui.save()
    response = client_for(w.alice).post(FARMS, {"name": "X", "oasis": w.azougui.id}, format="json")
    assert response.status_code == 400


# --- Isolation A / B -----------------------------------------------------------


def test_b_ne_voit_rien_d_alice(w):
    client = client_for(w.bob)
    assert ids(client.get(FARMS)) == {w.bob_farm.id}
    assert client.get(f"{FARMS}{w.alice_farm.id}/").status_code == 404
    assert client.get(f"{FARMS}{w.alice_farm.id}/summary/").status_code == 404
    assert all(row["farm"] == w.bob_farm.id for row in client.get(PALMS).data)
    assert client.get(HARVESTS).data == []
    harvest = Harvest.objects.filter(farm=w.alice_farm).first()
    assert client.get(f"{HARVESTS}{harvest.id}/").status_code == 404


def test_b_ne_modifie_rien_d_alice(w):
    client = client_for(w.bob)
    group = PalmGroup.objects.get(farm=w.alice_farm, variety=w.amhat)
    harvest = Harvest.objects.filter(farm=w.alice_farm).first()
    assert (
        client.patch(f"{FARMS}{w.alice_farm.id}/", {"name": "x"}, format="json").status_code == 404
    )
    assert (
        client.patch(f"{PALMS}{group.id}/", {"productive_count": 0}, format="json").status_code
        == 404
    )
    assert client.delete(f"{HARVESTS}{harvest.id}/").status_code == 404
    group.refresh_from_db()
    harvest.refresh_from_db()
    assert group.productive_count == 100 and harvest.is_active


def test_b_ne_saisit_pas_dans_la_ferme_d_alice(w):
    client = client_for(w.bob)
    payload = {
        "farm": w.alice_farm.id,
        "variety": w.tijib.id,
        "harvest_date": "2026-07-01",
        "quantity_kg": "1",
    }
    response = client.post(HARVESTS, payload, format="json")
    assert response.status_code == 400  # ferme « introuvable » pour Bob
    assert "farm" in response.data
    # ni en déplaçant sa propre ligne vers la ferme d'Alice
    group = PalmGroup.objects.get(farm=w.bob_farm)
    response = client.patch(f"{PALMS}{group.id}/", {"farm": w.alice_farm.id}, format="json")
    assert response.status_code == 400


def test_vendeur_seul_n_a_pas_acces(w):
    client = client_for(UserFactory(roles=[Role.SELLER]))
    assert client.get(FARMS).status_code == 403
    assert client.get(HARVESTS).status_code == 403


def test_direction_lit_tout_mais_ne_modifie_pas(w):
    client = client_for(UserFactory(roles=[Role.DIRECTION]))
    assert len(client.get(FARMS).data) == 4
    assert client.get(f"{FARMS}{w.alice_farm.id}/summary/").status_code == 200
    assert (
        client.patch(f"{FARMS}{w.alice_farm.id}/", {"name": "x"}, format="json").status_code == 403
    )
    assert (
        client.post(FARMS, {"name": "x", "oasis": w.azougui.id}, format="json").status_code == 403
    )


def test_filtres_fermes(w):
    client = client_for(UserFactory(roles=[Role.DIRECTION]))
    assert ids(client.get(FARMS, {"owner": w.alice.id})) == {w.alice_farm.id}
    assert len(client.get(FARMS, {"region": "atar"}).data) == 4
    assert client.get(FARMS, {"oasis": "autre"}).data == []
    assert len(client.get(HARVESTS, {"date_from": "2025-08-01", "date_to": "2025-12-31"}).data) == 2


# --- Agent de terrain ----------------------------------------------------------


def test_agent_ne_voit_que_les_fermes_de_ses_inscrits(w):
    assert ids(client_for(w.agent).get(FARMS)) == {w.managed_farm.id, w.claimed_farm.id}


def test_agent_cree_une_ferme_pour_son_agriculteur(w):
    payload = {"name": "Ferme 2", "oasis": w.azougui.id, "owner": w.managed.id}
    response = client_for(w.agent).post(FARMS, payload, format="json")
    assert response.status_code == 201
    farm = Farm.objects.get(pk=response.data["id"])
    assert farm.owner == w.managed and farm.created_by == w.agent


@pytest.mark.parametrize("cible", ["alice", "claimed"])
def test_agent_ne_cree_pas_pour_un_autre(w, cible):
    payload = {"name": "X", "oasis": w.azougui.id, "owner": getattr(w, cible).id}
    assert client_for(w.agent).post(FARMS, payload, format="json").status_code == 403


def test_agent_saisit_palmiers_et_recoltes_de_son_inscrit(w):
    client = client_for(w.agent)
    palms = client.post(
        PALMS,
        {"farm": w.managed_farm.id, "variety": w.amhat.id, "productive_count": 50},
        format="json",
    )
    assert palms.status_code == 201
    harvest = client.post(
        HARVESTS,
        {
            "farm": w.managed_farm.id,
            "variety": w.amhat.id,
            "harvest_date": "2026-07-10",
            "quantity_kg": "300",
        },
        format="json",
    )
    assert harvest.status_code == 201
    assert Harvest.objects.get(pk=harvest.data["id"]).created_by == w.agent
    assert client_for(w.managed).get(FARMS).data[0]["total_palms"] == 50


def test_agent_en_lecture_seule_apres_reprise(w):
    client = client_for(w.agent)
    assert client.get(f"{FARMS}{w.claimed_farm.id}/").status_code == 200
    assert (
        client.patch(f"{FARMS}{w.claimed_farm.id}/", {"name": "x"}, format="json").status_code
        == 403
    )
    payload = {"farm": w.claimed_farm.id, "variety": w.amhat.id, "productive_count": 5}
    assert client.post(PALMS, payload, format="json").status_code == 403


def test_agent_ne_saisit_pas_chez_alice(w):
    payload = {"farm": w.alice_farm.id, "variety": w.tijib.id, "productive_count": 5}
    assert client_for(w.agent).post(PALMS, payload, format="json").status_code == 400


def test_textes_lisibles(w):
    group = PalmGroup.objects.get(farm=w.alice_farm, variety=w.amhat)
    assert str(w.alice_farm) == "Ferme d'Alice"
    assert str(group) == "Ferme d'Alice – Amhat (120)"
    assert "500.50 kg" in str(Harvest.objects.get(quantity_kg=Decimal("500.50")))


@pytest.mark.parametrize("model", ["farm", "harvest"])
def test_pages_d_administration(client, w, model):
    from accounts.models import User

    client.force_login(User.objects.create_superuser("46000002", "Oasis-Adrar-2026"))
    assert client.get(f"/admin/farms/{model}/").status_code == 200
