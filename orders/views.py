from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.mixins import SellerMixin

from . import services
from .filters import OrderFilter
from .models import Notification, Order, OrderStatusHistory
from .serializers import NotificationSerializer, OrderSerializer, StatusChangeSerializer


def order_error(exc):
    return ValidationError({"detail": str(exc)})


class OrderViewSet(
    SellerMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Commandes du vendeur. Une commande ne se supprime pas : on l'annule.

    - Changer le statut : `POST /orders/{id}/status/` avec `status` (et `cancel_reason`).
    - Filtres : `?status=`, `?customer=`, `?late=true`, `?date_from=`, `?date_to=`,
      `?expected_from=`, `?expected_to=`.
    """

    queryset = (
        Order.objects.filter(is_active=True)
        .select_related("customer")
        .prefetch_related(
            "items__product",
            Prefetch("history", queryset=OrderStatusHistory.objects.select_related("changed_by")),
        )
    )
    serializer_class = OrderSerializer
    filterset_class = OrderFilter

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        try:
            serializer.instance = services.create_order(
                owner=self.request.user,
                customer=data.pop("customer"),
                items=data.pop("items"),
                user=self.request.user,
                **data,
            )
        except services.OrderError as exc:
            raise order_error(exc) from exc
        self.reload(serializer)

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        try:
            services.update_order(
                serializer.instance, self.request.user, items=data.pop("items", None), **data
            )
        except services.OrderError as exc:
            raise order_error(exc) from exc
        self.reload(serializer)

    @action(detail=True, methods=["post"], url_path="status")
    def change_status(self, request, pk=None):
        """Faire avancer la commande : reçue → confirmée → préparée → en livraison → livrée,
        ou annulée (jusqu'à « préparée »). Toute autre transition est refusée."""
        order = self.get_object()
        body = StatusChangeSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        try:
            services.change_status(
                order,
                data["status"],
                request.user,
                note=data["note"],
                cancel_reason=data["cancel_reason"],
            )
        except services.OrderError as exc:
            raise order_error(exc) from exc
        return Response(self.get_serializer(self.get_queryset().get(pk=order.pk)).data)


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Mes notifications (rappels de livraison, retards, stocks bas). Filtre : `?unread=true`."""

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # génération de la documentation
            return Notification.objects.none()
        qs = Notification.objects.filter(user=self.request.user).select_related("order")
        if self.request.query_params.get("unread") == "true":
            qs = qs.filter(read_at__isnull=True)
        return qs

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        """Marquer une notification comme lue."""
        notification = self.get_queryset().filter(pk=pk).first()
        if notification is None:
            return Response(status=404)
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        """Tout marquer comme lu."""
        count = self.get_queryset().filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response({"marked": count})
