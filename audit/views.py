import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers, viewsets
from rest_framework.pagination import PageNumberPagination

from core.permissions import IsDirection

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.full_name", read_only=True, default=None)
    acting_for_name = serializers.CharField(
        source="acting_for.full_name", read_only=True, default=None
    )

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "created_at",
            "user",
            "user_name",
            "acting_for",
            "acting_for_name",
            "action",
            "object_type",
            "object_id",
            "object_repr",
            "changes",
            "ip_address",
        ]
        read_only_fields = fields


class AuditLogFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = AuditLog
        fields = [
            "user",
            "acting_for",
            "action",
            "object_type",
            "object_id",
            "date_from",
            "date_to",
        ]


class AuditPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Journal d'audit (Direction, lecture seule). Filtres : `?user=`, `?action=`,
    `?object_type=orders.Order`, `?object_id=`, `?date_from=`, `?date_to=`."""

    queryset = AuditLog.objects.select_related("user", "acting_for")
    serializer_class = AuditLogSerializer
    permission_classes = [IsDirection]
    filter_backends = [DjangoFilterBackend]
    filterset_class = AuditLogFilter
    pagination_class = AuditPagination
