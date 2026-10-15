from django.utils.translation import gettext as _
from rest_framework import serializers

from core.access import filter_readable
from core.fields import money_field, not_in_future
from core.money import CENT, MAX_MONEY, round_money
from farms.models import Farm
from oases.models import DateVariety
from oases.serializers import VarietyShortSerializer

from .models import Expense, ExpenseCategory, Sale


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ["id", "name_ar", "name_fr", "applies_to", "order", "is_active"]
        read_only_fields = ["is_active"]


class OwnedFinanceSerializer(serializers.ModelSerializer):
    """La ferme choisie doit être visible par l'utilisateur (sinon : « introuvable »)."""

    farm = serializers.PrimaryKeyRelatedField(
        queryset=Farm.objects.none(), required=False, allow_null=True
    )

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request is not None:
            fields["farm"].queryset = filter_readable(
                Farm.objects.filter(is_active=True), request.user
            )
        return fields


class SaleSerializer(OwnedFinanceSerializer):
    variety = serializers.PrimaryKeyRelatedField(
        queryset=DateVariety.objects.filter(is_active=True), required=False, allow_null=True
    )
    variety_detail = VarietyShortSerializer(source="variety", read_only=True)
    quantity_kg = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=CENT)
    unit_price = money_field(help_text="Prix au kg en MRU.")
    sale_date = serializers.DateField(validators=[not_in_future])

    class Meta:
        model = Sale
        fields = [
            "id",
            "owner",
            "farm",
            "variety",
            "variety_detail",
            "sale_date",
            "quantity_kg",
            "unit_price",
            "total_amount",
            "buyer_name",
            "notes",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["owner", "total_amount", "created_by", "created_at"]

    def validate(self, attrs):
        quantity = attrs.get("quantity_kg", getattr(self.instance, "quantity_kg", None))
        price = attrs.get("unit_price", getattr(self.instance, "unit_price", None))
        if round_money(quantity * price) > MAX_MONEY:
            raise serializers.ValidationError(_("Montant total trop élevé."))
        return attrs


class ExpenseSerializer(OwnedFinanceSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=ExpenseCategory.objects.filter(is_active=True)
    )
    category_detail = ExpenseCategorySerializer(source="category", read_only=True)
    amount = money_field(help_text="Montant en MRU.")
    expense_date = serializers.DateField(validators=[not_in_future])

    class Meta:
        model = Expense
        fields = [
            "id",
            "owner",
            "category",
            "category_detail",
            "farm",
            "expense_date",
            "amount",
            "description",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["owner", "created_by", "created_at"]


class CategoryTotalSerializer(serializers.Serializer):
    category = ExpenseCategorySerializer()
    total = serializers.DecimalField(max_digits=16, decimal_places=2)


class MonthTotalSerializer(serializers.Serializer):
    month = serializers.CharField(help_text="AAAA-MM")
    sales = serializers.DecimalField(max_digits=16, decimal_places=2)
    expenses = serializers.DecimalField(max_digits=16, decimal_places=2)
    profit = serializers.DecimalField(max_digits=16, decimal_places=2)


class FinanceSummarySerializer(serializers.Serializer):
    date_from = serializers.DateField(allow_null=True)
    date_to = serializers.DateField(allow_null=True)
    direct_sales_total = serializers.DecimalField(
        max_digits=16, decimal_places=2, help_text="Ventes directes (agriculteur)."
    )
    orders_total = serializers.DecimalField(
        max_digits=16, decimal_places=2, help_text="Commandes livrées (vendeur)."
    )
    sales_total = serializers.DecimalField(max_digits=16, decimal_places=2)
    expenses_total = serializers.DecimalField(max_digits=16, decimal_places=2)
    profit = serializers.DecimalField(max_digits=16, decimal_places=2)
    expenses_by_category = CategoryTotalSerializer(many=True)
    by_month = MonthTotalSerializer(many=True)
