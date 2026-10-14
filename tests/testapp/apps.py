from django.apps import AppConfig


class TestAppConfig(AppConfig):
    """Application utilisée uniquement par les tests (jamais installée sur la plateforme)."""

    name = "tests.testapp"
    label = "testapp"
    default_auto_field = "django.db.models.BigAutoField"
