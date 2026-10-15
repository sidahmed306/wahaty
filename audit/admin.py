from django.contrib import admin

from inventory.admin import ReadOnlyAdmin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(ReadOnlyAdmin):
    list_display = ("created_at", "user", "acting_for", "action", "object_type", "object_repr")
    list_filter = ("action", "object_type")
    search_fields = ("object_repr", "object_id", "user__full_name", "user__phone")
    date_hierarchy = "created_at"
