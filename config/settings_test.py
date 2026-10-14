"""
Réglages utilisés uniquement par les tests automatiques (pytest).

La plateforme utilise la base Neon (DATABASE_URL) ; les tests utilisent le
PostgreSQL local de Postgres.app (TEST_DATABASE_URL), pour ne jamais toucher
aux données réelles ni consommer les heures gratuites de Neon.
"""

from .settings import *  # noqa: F403
from .settings import INSTALLED_APPS, env

# Application factice (table « Note ») pour tester l'isolation des données.
INSTALLED_APPS = [*INSTALLED_APPS, "tests.testapp"]

DATABASES = {"default": env.db("TEST_DATABASE_URL")}

# Hachage rapide pour accélérer les tests (jamais utilisé par la plateforme).
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
