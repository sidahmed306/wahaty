from datetime import date
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsDirection

from .services import direction_dashboard, personal_dashboard


class PeriodSerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)

    def validate(self, attrs):
        today = timezone.localdate()
        attrs.setdefault("date_from", date(today.year, 1, 1))
        attrs.setdefault("date_to", today)
        if attrs["date_from"] > attrs["date_to"]:
            raise serializers.ValidationError("date_from doit être avant date_to.")
        return attrs


def exact(value):
    """Montants en texte exact « 1234.50 » (jamais de float) et dates « AAAA-MM-JJ »."""
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: exact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [exact(v) for v in value]
    return value


class DashboardView(APIView):
    builder = None

    def get(self, request):
        period = PeriodSerializer(data=request.query_params)
        period.is_valid(raise_exception=True)
        data = type(self).builder(request.user, **period.validated_data)
        return Response(exact(data))


class DirectionDashboardView(DashboardView):
    """Tableau de bord de la Direction : comptes, fermes et palmiers, production, marché,
    commandes, stock, montants dus, ventes/dépenses/bénéfice sur la période
    (`?date_from=`, `?date_to=` ; par défaut : l'année en cours)."""

    permission_classes = [IsDirection]
    builder = direction_dashboard


class MyDashboardView(DashboardView):
    """Mon tableau de bord : une partie par rôle (agriculteur, vendeur, agent de terrain)."""

    permission_classes = [IsAuthenticated]
    builder = personal_dashboard
