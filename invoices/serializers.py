from rest_framework import serializers

from core.fields import OwnRelatedField
from orders.models import Order

from .models import Invoice


class InvoiceSerializer(serializers.ModelSerializer):
    order = OwnRelatedField(Order)
    order_number = serializers.CharField(source="order.number", read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "number",
            "order",
            "order_number",
            "issue_date",
            "seller_snapshot",
            "customer_snapshot",
            "lines_snapshot",
            "subtotal",
            "delivery_fee",
            "discount",
            "total_amount",
            "status",
            "cancelled_at",
            "cancel_reason",
            "created_at",
        ]
        read_only_fields = [f for f in fields if f != "order"]
        # La règle « une seule facture valide par commande » est vérifiée par le service,
        # avec un message clair (sinon DRF ajoute son propre contrôle, au message générique).
        validators = []


class CancelInvoiceSerializer(serializers.Serializer):
    reason = serializers.CharField(help_text="Motif de l'annulation (le numéro reste utilisé).")
