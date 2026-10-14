from django.contrib import admin

from .models import Farm, Harvest, PalmGroup


class PalmGroupInline(admin.TabularInline):
    model = PalmGroup
    extra = 0
    fields = ("variety", "productive_count", "young_count", "is_active")


@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "oasis", "area_hectares", "is_active")
    list_filter = ("oasis__region", "oasis", "is_active")
    search_fields = ("name", "owner__full_name", "owner__phone")
    raw_id_fields = ("owner", "created_by")
    inlines = [PalmGroupInline]


@admin.register(Harvest)
class HarvestAdmin(admin.ModelAdmin):
    list_display = ("farm", "variety", "season", "harvest_date", "quantity_kg", "is_active")
    list_filter = ("season", "variety", "is_active")
    search_fields = ("farm__name", "farm__owner__full_name")
    raw_id_fields = ("farm", "created_by")
    date_hierarchy = "harvest_date"
