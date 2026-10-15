from django.http import HttpResponse
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from core.mixins import SellerMixin

from . import services
from .models import Invoice
from .pdf import invoice_pdf
from .serializers import CancelInvoiceSerializer, InvoiceSerializer


def invoice_error(exc):
    return ValidationError({"detail": str(exc)})


class InvoiceViewSet(
    SellerMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Factures du vendeur.

    - Créer : `POST /invoices/` avec `order` (commande confirmée ou plus avancée).
    - PDF bilingue : `GET /invoices/{id}/pdf/`.
    - Annuler : `POST /invoices/{id}/cancel/` (le numéro reste utilisé : pas de trou).
    - Filtres : `?status=`, `?year=`, `?order=`.
    """

    queryset = Invoice.objects.select_related("order")
    serializer_class = InvoiceSerializer
    filterset_fields = ["status", "year", "order"]

    def perform_create(self, serializer):
        try:
            serializer.instance = services.create_invoice(
                serializer.validated_data["order"], self.request.user
            )
        except services.InvoiceError as exc:
            raise invoice_error(exc) from exc

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        invoice = self.get_object()
        body = CancelInvoiceSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            invoice = services.cancel_invoice(invoice, body.validated_data["reason"])
        except services.InvoiceError as exc:
            raise invoice_error(exc) from exc
        return Response(self.get_serializer(invoice).data)

    @action(detail=True)
    def pdf(self, request, pk=None):
        """Télécharger la facture en PDF (français + arabe)."""
        invoice = self.get_object()
        response = HttpResponse(invoice_pdf(invoice), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{invoice.number}.pdf"'
        return response
