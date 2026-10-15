from django.contrib import admin

from .models import PlatformSettings


@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
    """Une seule ligne de réglages : on la modifie, on ne l'ajoute ni ne la supprime."""

    list_display = (
        "__str__",
        "premium_threshold",
        "new_customer_days",
        "loyal_min_orders",
        "loyal_period_days",
        "inactive_days",
    )

    def has_add_permission(self, request):
        return not PlatformSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
