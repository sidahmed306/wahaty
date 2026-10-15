from django.contrib import admin

from inventory.admin import ReadOnlyAdmin

from .models import Notification, Order, OrderItem, OrderStatusHistory


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("product", "quantity", "unit_price", "line_total")


class HistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    can_delete = False
    readonly_fields = ("from_status", "to_status", "changed_by", "changed_at", "note")


@admin.register(Order)
class OrderAdmin(ReadOnlyAdmin):
    list_display = (
        "number",
        "owner",
        "customer",
        "status",
        "order_date",
        "expected_delivery_date",
        "total_amount",
    )
    list_filter = ("status",)
    search_fields = ("number", "customer__name", "owner__full_name")
    date_hierarchy = "order_date"
    inlines = [OrderItemInline, HistoryInline]


@admin.register(Notification)
class NotificationAdmin(ReadOnlyAdmin):
    list_display = ("day", "user", "kind", "message_fr", "read_at")
    list_filter = ("kind",)
