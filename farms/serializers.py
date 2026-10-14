from django.utils import timezone
from rest_framework import serializers

from core.access import filter_readable
from oases.models import DateVariety, Oasis
from oases.serializers import OasisShortSerializer, VarietyShortSerializer

from .models import Farm, Harvest, PalmGroup


class FarmSerializer(serializers.ModelSerializer):
    oasis = serializers.PrimaryKeyRelatedField(queryset=Oasis.objects.filter(is_active=True))
    oasis_detail = OasisShortSerializer(source="oasis", read_only=True)
    owner_name = serializers.CharField(source="owner.full_name", read_only=True)
    productive_palms = serializers.IntegerField(read_only=True)
    young_palms = serializers.IntegerField(read_only=True)
    total_palms = serializers.IntegerField(read_only=True)

    class Meta:
        model = Farm
        fields = [
            "id",
            "owner",
            "owner_name",
            "name",
            "oasis",
            "oasis_detail",
            "area_hectares",
            "latitude",
            "longitude",
            "productive_palms",
            "young_palms",
            "total_palms",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["owner", "created_by", "created_at"]


class FarmChildSerializer(serializers.ModelSerializer):
    """Base des palmiers et récoltes : la ferme choisie doit être visible par l'utilisateur.

    Une ferme d'un autre utilisateur répond « introuvable » : on ne révèle pas qu'elle existe.
    """

    farm = serializers.PrimaryKeyRelatedField(queryset=Farm.objects.none())
    variety = serializers.PrimaryKeyRelatedField(
        queryset=DateVariety.objects.filter(is_active=True)
    )
    variety_detail = VarietyShortSerializer(source="variety", read_only=True)

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request is not None:
            fields["farm"].queryset = filter_readable(
                Farm.objects.filter(is_active=True), request.user
            )
        return fields


class PalmGroupSerializer(FarmChildSerializer):
    total_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = PalmGroup
        fields = [
            "id",
            "farm",
            "variety",
            "variety_detail",
            "productive_count",
            "young_count",
            "total_count",
        ]

    def validate(self, attrs):
        farm = attrs.get("farm", getattr(self.instance, "farm", None))
        variety = attrs.get("variety", getattr(self.instance, "variety", None))
        duplicate = PalmGroup.objects.filter(farm=farm, variety=variety, is_active=True)
        if self.instance:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError(
                {"variety": "Cette variété existe déjà dans cette ferme : modifiez la ligne."}
            )
        return attrs


class HarvestSerializer(FarmChildSerializer):
    season = serializers.IntegerField(
        min_value=2000, max_value=2100, required=False, help_text="Par défaut : année de récolte."
    )

    class Meta:
        model = Harvest
        fields = [
            "id",
            "farm",
            "variety",
            "variety_detail",
            "season",
            "harvest_date",
            "quantity_kg",
            "notes",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["created_by", "created_at"]

    def validate_quantity_kg(self, value):
        if value <= 0:
            raise serializers.ValidationError("La quantité doit être supérieure à 0.")
        return value

    def validate_harvest_date(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError("La date de récolte ne peut pas être dans le futur.")
        return value

    def validate(self, attrs):
        harvest_date = attrs.get("harvest_date", getattr(self.instance, "harvest_date", None))
        season = attrs.get("season", getattr(self.instance, "season", None))
        if season is None:
            attrs["season"] = season = harvest_date.year
        # Une saison à cheval sur deux années (ex. nov. 2025 → fév. 2026) reste possible.
        if season not in (harvest_date.year, harvest_date.year - 1):
            raise serializers.ValidationError(
                {"season": "La saison doit être l'année de la récolte ou l'année précédente."}
            )
        return attrs


class PalmTotalsSerializer(serializers.Serializer):
    variety = VarietyShortSerializer()
    productive = serializers.IntegerField()
    young = serializers.IntegerField()
    total = serializers.IntegerField()


class ProductionLineSerializer(serializers.Serializer):
    season = serializers.IntegerField()
    variety = VarietyShortSerializer()
    total_kg = serializers.DecimalField(max_digits=14, decimal_places=2)
    harvests_count = serializers.IntegerField()


class SeasonTotalSerializer(serializers.Serializer):
    season = serializers.IntegerField()
    total_kg = serializers.DecimalField(max_digits=14, decimal_places=2)
