import pytest
from django.conf import settings
from django.db import connection


def test_projet_django_charge():
    assert settings.ROOT_URLCONF == "config.urls"


def test_base_est_postgresql():
    assert connection.vendor == "postgresql"


def test_tests_utilisent_la_base_locale_et_pas_neon():
    assert connection.settings_dict["HOST"] in ("localhost", "127.0.0.1")
    assert "neon.tech" not in connection.settings_dict["HOST"]


@pytest.mark.django_db
def test_connexion_postgresql():
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        assert cursor.fetchone() == (1,)
