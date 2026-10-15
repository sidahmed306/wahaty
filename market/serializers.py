from rest_framework import serializers

from accounts.serializers import clean_phone
from core.fields import money_field, quantity_field
from oases.models import DateVariety, Oasis
from oases.serializers import OasisShortSerializer, RegionShortSerializer, VarietyShortSerializer

from .models import Listing, ListingPhoto


class ListingPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingPhoto
        fields = ["id", "image", "order"]


class ListingOasisSerializer(OasisShortSerializer):
    region = RegionShortSerializer(read_only=True)

    class Meta(OasisShortSerializer.Meta):
        fields = [*OasisShortSerializer.Meta.fields, "region"]


class PublicListingSerializer(serializers.ModelSerializer):
    """Ce que voit le public : pas d'identifiant ni de donnée privée du vendeur."""

    variety = VarietyShortSerializer(read_only=True)
    oasis = ListingOasisSerializer(read_only=True)
    seller_name = serializers.SerializerMethodField()
    photos = ListingPhotoSerializer(many=True, read_only=True)
    whatsapp_link = serializers.CharField(read_only=True)
    phone_link = serializers.CharField(read_only=True)

    class Meta:
        model = Listing
        fields = [
            "id",
            "title",
            "description",
            "language",
            "variety",
            "oasis",
            "price_per_kg",
            "quantity_kg",
            "seller_name",
            "contact_phone",
            "whatsapp_link",
            "phone_link",
            "photos",
            "published_at",
        ]
        read_only_fields = fields

    def get_seller_name(self, obj):
        return obj.owner.profile.business_name or obj.owner.full_name


class MyListingSerializer(PublicListingSerializer):
    """Annonce vue (et modifiée) par son propriétaire, ou relue par la Direction."""

    variety = serializers.PrimaryKeyRelatedField(
        queryset=DateVariety.objects.filter(is_active=True)
    )
    variety_detail = VarietyShortSerializer(source="variety", read_only=True)
    oasis = serializers.PrimaryKeyRelatedField(queryset=Oasis.objects.filter(is_active=True))
    oasis_detail = ListingOasisSerializer(source="oasis", read_only=True)
    language = serializers.ChoiceField(
        choices=Listing._meta.get_field("language").choices,
        required=False,
        help_text="Par défaut : langue préférée du vendeur.",
    )
    price_per_kg = money_field()
    quantity_kg = quantity_field()
    contact_phone = serializers.CharField(
        required=False, help_text="Par défaut : téléphone du compte."
    )
    whatsapp_phone = serializers.CharField(required=False, allow_blank=True)
    is_editable = serializers.BooleanField(read_only=True)

    class Meta(PublicListingSerializer.Meta):
        fields = [
            *PublicListingSerializer.Meta.fields,
            "owner",
            "variety_detail",
            "oasis_detail",
            "whatsapp_phone",
            "status",
            "rejection_reason",
            "is_editable",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "owner",
            "seller_name",
            "whatsapp_link",
            "phone_link",
            "photos",
            "status",
            "rejection_reason",
            "published_at",
            "created_at",
        ]

    def validate_contact_phone(self, value):
        return clean_phone(value)

    def validate_whatsapp_phone(self, value):
        return clean_phone(value) if value else value


class RejectSerializer(serializers.Serializer):
    reason = serializers.CharField(help_text="Motif du refus, envoyé au vendeur.")


class PhotoUploadSerializer(serializers.Serializer):
    image = serializers.ImageField()
    order = serializers.IntegerField(min_value=0, required=False, default=0)
