from django.utils import timezone
from rest_framework import serializers

from core.fields import OwnRelatedField, money_field, not_in_future, quantity_field
from customers.models import Customer
from inventory.models import Product

from .models import Notification, Order, OrderItem, OrderStatus, OrderStatusHistory


class OrderItemWriteSerializer(serializers.Serializer):
    product = OwnRelatedField(Product)
    quantity = quantity_field()
    unit_price = money_field(
        min_value=0, required=False, help_text="Par défaut : prix de vente du produit."
    )

    def validate(self, attrs):
        if "unit_price" not in attrs:
            if attrs["product"].sale_price is None:
                raise serializers.ValidationError(
                    {"unit_price": "Ce produit n'a pas de prix de vente : indiquez le prix."}
                )
            attrs["unit_price"] = attrs["product"].sale_price
        return attrs


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "product", "product_name", "quantity", "unit_price", "line_total"]


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source="changed_by.full_name", read_only=True)

    class Meta:
        model = OrderStatusHistory
        fields = ["from_status", "to_status", "changed_by", "changed_by_name", "changed_at", "note"]


class OrderSerializer(serializers.ModelSerializer):
    customer = OwnRelatedField(Customer)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    order_date = serializers.DateField(required=False, validators=[not_in_future])
    delivery_fee = money_field(min_value=0, required=False)
    discount = money_field(min_value=0, required=False)
    items = OrderItemWriteSerializer(many=True, write_only=True, allow_empty=False)
    lines = OrderItemSerializer(source="items", many=True, read_only=True)
    history = OrderStatusHistorySerializer(many=True, read_only=True)
    is_late = serializers.BooleanField(read_only=True)
    days_late = serializers.IntegerField(read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "number",
            "customer",
            "customer_name",
            "status",
            "order_date",
            "expected_delivery_date",
            "delivered_at",
            "is_late",
            "days_late",
            "delivery_address",
            "items",
            "lines",
            "subtotal",
            "delivery_fee",
            "discount",
            "total_amount",
            "cancel_reason",
            "notes",
            "history",
            "created_at",
        ]
        read_only_fields = [
            "number",
            "status",
            "delivered_at",
            "subtotal",
            "total_amount",
            "cancel_reason",
            "created_at",
        ]

    def validate(self, attrs):
        order_date = attrs.get(
            "order_date", getattr(self.instance, "order_date", None) or timezone.localdate()
        )
        expected = attrs.get(
            "expected_delivery_date", getattr(self.instance, "expected_delivery_date", None)
        )
        if expected and expected < order_date:
            raise serializers.ValidationError(
                {"expected_delivery_date": "La livraison ne peut pas être avant la commande."}
            )
        return attrs


class StatusChangeSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=OrderStatus.choices)
    note = serializers.CharField(required=False, allow_blank=True, default="")
    cancel_reason = serializers.CharField(required=False, allow_blank=True, default="")


class NotificationSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.number", read_only=True, default=None)

    class Meta:
        model = Notification
        fields = [
            "id",
            "kind",
            "order",
            "order_number",
            "product",
            "day",
            "message_ar",
            "message_fr",
            "read_at",
            "created_at",
        ]
        read_only_fields = fields
