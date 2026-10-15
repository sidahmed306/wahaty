from django.contrib import admin, messages

from . import services
from .models import Listing, ListingPhoto


class ListingPhotoInline(admin.TabularInline):
    model = ListingPhoto
    extra = 0
    fields = ("image", "order")


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    """La Direction peut aussi publier ici (action « Publier »). Le refus avec motif se fait
    par l'API, qui prévient le vendeur."""

    list_display = ("title", "owner", "variety", "oasis", "price_per_kg", "status", "is_active")
    list_filter = ("status", "variety", "oasis__region", "is_active")
    search_fields = ("title", "owner__full_name", "owner__phone")
    raw_id_fields = ("owner", "reviewed_by")
    readonly_fields = ("status", "published_at", "reviewed_by", "rejection_reason")
    inlines = [ListingPhotoInline]
    actions = ["approve_listings"]

    @admin.action(description="Publier les annonces en attente sélectionnées")
    def approve_listings(self, request, queryset):
        done = 0
        for listing in queryset:
            try:
                services.approve(listing, request.user)
                done += 1
            except services.ListingError:
                pass
        self.message_user(request, f"{done} annonce(s) publiée(s).", messages.SUCCESS)
