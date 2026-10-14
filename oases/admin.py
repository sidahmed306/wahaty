from django.contrib import admin

from .models import DateVariety, Oasis, OasisPhoto, Region


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("name_fr", "name_ar", "order", "is_active")
    list_editable = ("order", "is_active")
    search_fields = ("name_fr", "name_ar")
    prepopulated_fields = {"slug": ("name_fr",)}


class OasisPhotoInline(admin.TabularInline):
    model = OasisPhoto
    extra = 1
    fields = ("image", "caption_ar", "caption_fr", "order")


@admin.register(Oasis)
class OasisAdmin(admin.ModelAdmin):
    list_display = ("name_fr", "name_ar", "region", "is_active")
    list_filter = ("region", "is_active")
    search_fields = ("name_fr", "name_ar")
    prepopulated_fields = {"slug": ("name_fr",)}
    filter_horizontal = ("varieties",)
    inlines = [OasisPhotoInline]


@admin.register(DateVariety)
class DateVarietyAdmin(admin.ModelAdmin):
    list_display = (
        "name_fr",
        "name_ar",
        "texture",
        "ripening_start_month",
        "ripening_end_month",
        "is_active",
    )
    list_filter = ("texture", "is_active")
    search_fields = ("name_fr", "name_ar")
    prepopulated_fields = {"slug": ("name_fr",)}
