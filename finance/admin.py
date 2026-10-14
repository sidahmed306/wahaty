from django.contrib import admin

from .models import Expense, ExpenseCategory, Sale


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name_fr", "name_ar", "applies_to", "order", "is_active")
    list_editable = ("order", "is_active")
    list_filter = ("applies_to", "is_active")


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("sale_date", "owner", "variety", "quantity_kg", "unit_price", "total_amount")
    list_filter = ("variety", "is_active")
    search_fields = ("owner__full_name", "owner__phone", "buyer_name")
    raw_id_fields = ("owner", "farm", "created_by")
    readonly_fields = ("total_amount",)
    date_hierarchy = "sale_date"


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("expense_date", "owner", "category", "amount", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("owner__full_name", "owner__phone", "description")
    raw_id_fields = ("owner", "farm", "created_by")
    date_hierarchy = "expense_date"
