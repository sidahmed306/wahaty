from django.contrib import admin

from inventory.admin import ReadOnlyAdmin

from .models import Invoice, InvoiceSequence


@admin.register(Invoice)
class InvoiceAdmin(ReadOnlyAdmin):
    list_display = ("number", "owner", "issue_date", "total_amount", "status")
    list_filter = ("status", "year")
    search_fields = ("number", "owner__full_name")


@admin.register(InvoiceSequence)
class InvoiceSequenceAdmin(ReadOnlyAdmin):
    list_display = ("owner", "year", "last_number")
