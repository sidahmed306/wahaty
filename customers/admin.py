from django.contrib import admin

from inventory.admin import ReadOnlyAdmin

from .models import Customer, Payment


@admin.register(Customer)
class CustomerAdmin(ReadOnlyAdmin):
    list_display = ("name", "owner", "phone", "city", "is_active")
    search_fields = ("name", "phone", "owner__full_name")


@admin.register(Payment)
class PaymentAdmin(ReadOnlyAdmin):
    list_display = ("payment_date", "owner", "customer", "amount", "method", "is_active")
    list_filter = ("method",)
