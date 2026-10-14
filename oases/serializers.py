from rest_framework import serializers

from .models import DateVariety, Oasis, OasisPhoto, Region


class RegionSerializer(serializers.ModelSerializer):
    oases_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Region
        fields = ["id", "slug", "name_ar", "name_fr", "order", "is_active", "oases_count"]
        read_only_fields = ["is_active"]


class RegionShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = ["id", "slug", "name_ar", "name_fr"]


class VarietyShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = DateVariety
        fields = ["id", "slug", "name_ar", "name_fr"]


class OasisShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Oasis
        fields = ["id", "slug", "name_ar", "name_fr"]


class DateVarietySerializer(serializers.ModelSerializer):
    oases = OasisShortSerializer(many=True, read_only=True)

    class Meta:
        model = DateVariety
        fields = [
            "id",
            "slug",
            "name_ar",
            "name_fr",
            "description_ar",
            "description_fr",
            "texture",
            "ripening_start_month",
            "ripening_end_month",
            "photo",
            "oases",
            "is_active",
        ]
        read_only_fields = ["is_active"]


class OasisPhotoSerializer(serializers.ModelSerializer):
    oasis = serializers.SlugRelatedField(slug_field="slug", queryset=Oasis.objects.all())

    class Meta:
        model = OasisPhoto
        fields = ["id", "oasis", "image", "caption_ar", "caption_fr", "order"]


class OasisSerializer(serializers.ModelSerializer):
    region = serializers.PrimaryKeyRelatedField(queryset=Region.objects.filter(is_active=True))
    region_detail = RegionShortSerializer(source="region", read_only=True)
    varieties = serializers.PrimaryKeyRelatedField(
        queryset=DateVariety.objects.filter(is_active=True), many=True, required=False
    )
    varieties_detail = VarietyShortSerializer(source="varieties", many=True, read_only=True)
    photos = OasisPhotoSerializer(many=True, read_only=True)

    class Meta:
        model = Oasis
        fields = [
            "id",
            "slug",
            "name_ar",
            "name_fr",
            "description_ar",
            "description_fr",
            "region",
            "region_detail",
            "latitude",
            "longitude",
            "varieties",
            "varieties_detail",
            "photos",
            "is_active",
        ]
        read_only_fields = ["is_active"]
