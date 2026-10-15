"""Commande seed_varieties : les 9 variétés du flyer TRC, avec photo, relançable sans doublon."""

from io import StringIO

import pytest
from django.core.management import call_command

from oases.models import DateVariety

pytestmark = pytest.mark.django_db


def run(*args):
    out = StringIO()
    call_command("seed_varieties", *args, stdout=out)
    return out.getvalue()


def test_cree_les_neuf_varietes_avec_photo():
    output = run()
    assert "9 variétés prêtes (9 nouvelles)" in output
    varieties = DateVariety.objects.order_by("slug")
    assert varieties.count() == 9
    salmedina = DateVariety.objects.get(slug="salmedina")
    assert salmedina.name_ar == "سلمدينة"
    assert salmedina.description_fr and salmedina.description_ar
    assert (salmedina.ripening_start_month, salmedina.ripening_end_month) == (6, 8)
    assert salmedina.photo.name.endswith(".jpg")  # photo convertie en JPEG
    assert all(v.photo for v in varieties)
    honey = DateVariety.objects.get(slug="miel-de-dattes")
    assert (honey.ripening_start_month, honey.ripening_end_month) == (1, 12)
    assert DateVariety.objects.get(slug="tmar-mfassas").texture == "soft"


def test_relancer_ne_cree_pas_de_doublon_ni_ne_change_les_photos():
    run()
    before = dict(DateVariety.objects.values_list("slug", "photo"))
    DateVariety.objects.filter(slug="hmar").update(description_fr="modifié")
    output = run()
    assert "(0 nouvelles)" in output
    assert DateVariety.objects.count() == 9
    assert DateVariety.objects.get(slug="hmar").description_fr != "modifié"
    assert dict(DateVariety.objects.values_list("slug", "photo")) == before


def test_photo_manquante_ou_option_photos_remplace(media_tmp):
    run()
    sekani = DateVariety.objects.get(slug="sekani")
    sekani.photo.storage.delete(sekani.photo.name)  # fichier perdu (ex. nouveau stockage)
    old_names = dict(DateVariety.objects.values_list("slug", "photo"))
    run()
    sekani.refresh_from_db()
    assert sekani.photo.storage.exists(sekani.photo.name)
    run("--photos")
    new_names = dict(DateVariety.objects.values_list("slug", "photo"))
    assert all(new_names[slug] != old_names[slug] for slug in new_names if slug != "sekani")
