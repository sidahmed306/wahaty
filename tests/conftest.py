import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from tests.factories import UserFactory


@pytest.fixture(autouse=True)
def clear_cache():
    """Remet à zéro le compteur de tentatives de connexion entre deux tests."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def media_tmp(settings, tmp_path):
    """Les photos des tests vont dans un dossier temporaire, effacé après."""
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def auth_client(user):
    from rest_framework_simplejwt.tokens import RefreshToken

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client
