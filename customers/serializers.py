from rest_framework import serializers

from accounts.serializers import clean_phone
from core.fields import OwnRelatedField, money_field, not_in_future
from core.models import PlatformSettings

from .models import Customer, Payment
from .segments import Segment

READ_AMOUNT = {"max_digits": 16, "decimal_places": 2, "read_only": True}


class CustomerSerializer(serializers.ModelSerializer):
    orders_count = serializers.IntegerField(read_only=True)
    first_order_date = serializers.DateField(read_only=True)
    last_order_date = serializers.DateField(read_only=True)
    total_purchased = serializers.DecimalField(**READ_AMOUNT)
    paid_total = serializers.DecimalField(**READ_AMOUNT)
    balance = serializers.DecimalField(
        help_text="Dette (MRU) : commandes livrées − paiements. Négatif = avance.", **READ_AMOUNT
    )
    segment = serializers.ChoiceField(choices=Segment.choices, read_only=True)

    class Meta:
        model = Customer
        fields = [
            "id",
            "owner",
            "name",
            "phone",
            "whatsapp",
            "address",
            "city",
            "notes",
            "orders_count",
            "first_order_date",
            "last_order_date",
            "total_purchased",
            "paid_total",
            "balance",
            "segment",
            "created_at",
        ]
        read_only_fields = ["owner", "created_at"]

    def validate_phone(self, value):
        if not value:
            return value
        phone = clean_phone(value)
        request = self.context["request"]
        same = Customer.objects.filter(owner=request.user, phone=phone, is_active=True)
        if self.instance:
            same = same.exclude(pk=self.instance.pk)
        if same.exists():
            raise serializers.ValidationError("Vous avez déjà un client avec ce numéro.")
        return phone

    def validate_whatsapp(self, value):
        return clean_phone(value) if value else value


class PaymentSerializer(serializers.ModelSerializer):
    customer = OwnRelatedField(Customer)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    payment_date = serializers.DateField(validators=[not_in_future])
    amount = money_field()

    class Meta:
        model = Payment
        fields = [
            "id",
            "customer",
            "customer_name",
            "payment_date",
            "amount",
            "method",
            "reference",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["created_by", "created_at"]


class PlatformSettingsSerializer(serializers.ModelSerializer):
    premium_threshold = money_field(min_value=0)

    class Meta:
        model = PlatformSettings
        fields = [
            "premium_threshold",
            "new_customer_days",
            "loyal_min_orders",
            "loyal_period_days",
            "inactive_days",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]
        extra_kwargs = {
            name: {"min_value": 1}
            for name in (
                "new_customer_days",
                "loyal_min_orders",
                "loyal_period_days",
                "inactive_days",
            )
        }
