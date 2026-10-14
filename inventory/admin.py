from django.contrib import admin

from .models import Product, Purchase, StockMovement, Supplier, SupplierPayment


class ReadOnlyAdmin(admin.ModelAdmin):
    """Argent et stock : consultation seulement dans l'administration (les opérations passent
    par l'API, qui contrôle le stock et le reste à payer dans une transaction)."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Supplier)
class SupplierAdmin(ReadOnlyAdmin):
    list_display = ("name", "owner", "phone", "is_active")
    search_fields = ("name", "owner__full_name")


@admin.register(Product)
class ProductAdmin(ReadOnlyAdmin):
    list_display = ("name", "owner", "unit", "sale_price", "is_active")
    search_fields = ("name", "owner__full_name")


@admin.register(Purchase)
class PurchaseAdmin(ReadOnlyAdmin):
    list_display = ("purchase_date", "owner", "supplier", "total_amount", "cancelled_at")
    date_hierarchy = "purchase_date"


@admin.register(StockMovement)
class StockMovementAdmin(ReadOnlyAdmin):
    list_display = ("movement_date", "product", "kind", "quantity", "unit_cost")
    list_filter = ("kind",)


@admin.register(SupplierPayment)
class SupplierPaymentAdmin(ReadOnlyAdmin):
    list_display = ("payment_date", "owner", "supplier", "amount", "method", "is_active")
    list_filter = ("method",)
