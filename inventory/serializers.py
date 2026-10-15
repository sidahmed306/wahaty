from django.utils.translation import gettext as _
from rest_framework import serializers

from accounts.serializers import clean_phone
from core.fields import OwnRelatedField, money_field, not_in_future, quantity_field
from core.money import MAX_MONEY, round_money
from oases.models import DateVariety, Oasis

from .models import Product, Purchase, StockMovement, Supplier, SupplierPayment

READ_AMOUNT = {"max_digits": 16, "decimal_places": 2, "read_only": True}


class SupplierSerializer(serializers.ModelSerializer):
    oasis = serializers.PrimaryKeyRelatedField(
        queryset=Oasis.objects.filter(is_active=True), required=False, allow_null=True
    )
    purchases_total = serializers.DecimalField(**READ_AMOUNT)
    paid_total = serializers.DecimalField(**READ_AMOUNT)
    balance = serializers.DecimalField(help_text="Reste à payer (MRU).", **READ_AMOUNT)

    class Meta:
        model = Supplier
        fields = [
            "id",
            "owner",
            "name",
            "phone",
            "oasis",
            "notes",
            "purchases_total",
            "paid_total",
            "balance",
        ]
        read_only_fields = ["owner"]

    def validate_phone(self, value):
        return clean_phone(value) if value else value


class ProductSerializer(serializers.ModelSerializer):
    variety = serializers.PrimaryKeyRelatedField(
        queryset=DateVariety.objects.filter(is_active=True), required=False, allow_null=True
    )
    sale_price = money_field(min_value=0, required=False, allow_null=True)
    low_stock_threshold = quantity_field(min_value=0, required=False, allow_null=True)
    stock = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)
    is_low_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "owner",
            "name",
            "variety",
            "unit",
            "sale_price",
            "low_stock_threshold",
            "stock",
            "is_low_stock",
        ]
        read_only_fields = ["owner"]

    def get_is_low_stock(self, obj) -> bool:
        threshold = obj.low_stock_threshold
        return threshold is not None and getattr(obj, "stock", 0) <= threshold


class StockMovementSerializer(serializers.ModelSerializer):
    """Mouvement manuel : correction (+/−) ou perte, avec justification obligatoire."""

    product = OwnRelatedField(Product)
    product_name = serializers.CharField(source="product.name", read_only=True)
    kind = serializers.ChoiceField(
        choices=[(k, StockMovement.Kind(k).label) for k in StockMovement.MANUAL_KINDS]
    )
    quantity = quantity_field()
    note = serializers.CharField(help_text="Pourquoi ce mouvement ?")

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "product",
            "product_name",
            "kind",
            "quantity",
            "unit_cost",
            "purchase",
            "movement_date",
            "note",
            "created_by",
        ]
        read_only_fields = ["unit_cost", "purchase", "movement_date", "created_by"]

    def to_representation(self, instance):
        # En lecture, tous les types s'affichent (achat, livraison…), pas seulement les manuels.
        data = super().to_representation(instance)
        data["kind"] = instance.kind
        return data


class PurchaseLineSerializer(serializers.Serializer):
    product = OwnRelatedField(Product)
    quantity = quantity_field()
    unit_cost = money_field(help_text="Prix d'achat unitaire (MRU).")


class PurchaseLineReadSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = StockMovement
        fields = ["id", "product", "product_name", "quantity", "unit_cost"]


class PurchaseSerializer(serializers.ModelSerializer):
    supplier = OwnRelatedField(Supplier)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    purchase_date = serializers.DateField(validators=[not_in_future])
    lines = PurchaseLineSerializer(many=True, write_only=True, allow_empty=False)
    items = PurchaseLineReadSerializer(source="lines", many=True, read_only=True)

    class Meta:
        model = Purchase
        fields = [
            "id",
            "supplier",
            "supplier_name",
            "purchase_date",
            "reference",
            "lines",
            "items",
            "total_amount",
            "cancelled_at",
            "cancel_reason",
            "created_by",
            "created_at",
        ]
        read_only_fields = [
            "total_amount",
            "cancelled_at",
            "cancel_reason",
            "created_by",
            "created_at",
        ]

    def validate_lines(self, lines):
        total = sum(round_money(line["quantity"] * line["unit_cost"]) for line in lines)
        if total > MAX_MONEY:
            raise serializers.ValidationError(_("Montant total trop élevé."))
        return lines


class CancelPurchaseSerializer(serializers.Serializer):
    reason = serializers.CharField(help_text="Motif de l'annulation.")


class SupplierPaymentSerializer(serializers.ModelSerializer):
    supplier = OwnRelatedField(Supplier)
    purchase = OwnRelatedField(Purchase, required=False, allow_null=True)
    payment_date = serializers.DateField(validators=[not_in_future])
    amount = money_field()

    class Meta:
        model = SupplierPayment
        fields = [
            "id",
            "supplier",
            "purchase",
            "payment_date",
            "amount",
            "method",
            "reference",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["created_by", "created_at"]

    def validate(self, attrs):
        purchase = attrs.get("purchase")
        if purchase is not None:
            if purchase.supplier_id != attrs["supplier"].pk:
                raise serializers.ValidationError(
                    {"purchase": _("Cet achat ne vient pas de ce fournisseur.")}
                )
            if purchase.is_cancelled:
                raise serializers.ValidationError({"purchase": _("Cet achat est annulé.")})
        return attrs
