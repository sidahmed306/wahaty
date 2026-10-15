from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, viewsets
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role, User
from core.access import can_read_for, can_write_for, filter_readable, is_direction
from core.mixins import OwnedQuerysetMixin, SoftDeleteMixin
from core.permissions import IsDirectionOrReadOnly, OwnerPermission, role_permission
from orders.models import Order

from .filters import ExpenseFilter, SaleFilter
from .models import Expense, ExpenseCategory, Sale
from .serializers import (
    ExpenseCategorySerializer,
    ExpenseSerializer,
    FinanceSummarySerializer,
    SaleSerializer,
)
from .summary import finance_summary

SalesAccess = role_permission(Role.FARMER, Role.FIELD_AGENT, Role.DIRECTION)
ExpensesAccess = role_permission(Role.FARMER, Role.SELLER, Role.FIELD_AGENT, Role.DIRECTION)


class ExpenseCategoryViewSet(SoftDeleteMixin, viewsets.ModelViewSet):
    """Catégories de dépenses : lecture pour tous, gestion par la Direction.

    Filtre : `?applies_to=farmer|seller|both`.
    """

    serializer_class = ExpenseCategorySerializer
    permission_classes = [IsDirectionOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["applies_to"]

    def get_queryset(self):
        qs = ExpenseCategory.objects.all()
        return qs if is_direction(self.request.user) else qs.filter(is_active=True)


class FinanceRecordViewSet(SoftDeleteMixin, OwnedQuerysetMixin, viewsets.ModelViewSet):
    """Base des ventes et dépenses : propriétaire, ferme du même propriétaire, saisi par."""

    filter_backends = [DjangoFilterBackend]

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)

    def check_relations(self, owner, data):
        farm = data.get("farm")
        if farm is not None and farm.owner_id != owner.pk:
            raise ValidationError({"farm": _("Cette ferme n'appartient pas à ce propriétaire.")})

    def perform_create(self, serializer):
        owner = self.get_owner_for_create()
        if not can_write_for(self.request.user, owner):
            raise PermissionDenied(_("Agriculteur introuvable ou non géré par vous."))
        self.check_relations(owner, serializer.validated_data)
        serializer.save(owner=owner, created_by=self.request.user)

    def perform_update(self, serializer):
        self.check_relations(serializer.instance.owner, serializer.validated_data)
        serializer.save()


class SaleViewSet(FinanceRecordViewSet):
    """Ventes directes de l'agriculteur. Le total (MRU) est calculé par le serveur.

    Filtres : `?farm=`, `?variety=`, `?date_from=`, `?date_to=`, `?owner=`.
    """

    queryset = Sale.objects.select_related("variety", "farm")
    serializer_class = SaleSerializer
    # Le rôle (SalesAccess) et can_write_for garantissent que le propriétaire est agriculteur.
    permission_classes = [SalesAccess, OwnerPermission]
    filterset_class = SaleFilter


class ExpenseViewSet(FinanceRecordViewSet):
    """Dépenses (agriculteur ou vendeur), en MRU.

    Filtres : `?category=`, `?farm=`, `?date_from=`, `?date_to=`, `?owner=`.
    """

    queryset = Expense.objects.select_related("category", "farm")
    serializer_class = ExpenseSerializer
    permission_classes = [ExpensesAccess, OwnerPermission]
    filterset_class = ExpenseFilter

    def check_relations(self, owner, data):
        super().check_relations(owner, data)
        category = data.get("category")
        if category is not None and not category.usable_by(owner):
            raise ValidationError(
                {"category": _("Cette catégorie ne correspond pas à votre activité.")}
            )


class SummaryQuerySerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    owner = serializers.IntegerField(required=False)

    def validate(self, attrs):
        if (
            attrs.get("date_from")
            and attrs.get("date_to")
            and attrs["date_from"] > attrs["date_to"]
        ):
            raise serializers.ValidationError(_("date_from doit être avant date_to."))
        return attrs


class FinanceSummaryView(APIView):
    """Bénéfice = ventes − dépenses, avec le détail par catégorie et par mois.

    Paramètres : `?date_from=AAAA-MM-JJ`, `?date_to=…`, `?owner=<id>` (Direction, agent).
    Sans `owner` : mes chiffres (la Direction : tous les utilisateurs ; l'agent : les siens).
    """

    permission_classes = [ExpensesAccess]

    @extend_schema(parameters=[SummaryQuerySerializer], responses=FinanceSummarySerializer)
    def get(self, request):
        params = SummaryQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        query = params.validated_data
        sales = filter_readable(Sale.objects.all(), request.user)
        expenses = filter_readable(Expense.objects.all(), request.user)
        orders = filter_readable(Order.objects.all(), request.user)
        if "owner" in query:
            owner = User.objects.filter(pk=query["owner"]).first()
            if not can_read_for(request.user, owner):
                raise NotFound(_("Utilisateur introuvable."))
            sales, expenses, orders = (qs.filter(owner=owner) for qs in (sales, expenses, orders))
        data = finance_summary(
            sales, expenses, orders, query.get("date_from"), query.get("date_to")
        )
        return Response(FinanceSummarySerializer(data).data)
