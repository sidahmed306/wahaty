from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.signals import user_logged_in
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import RefreshToken

from core.images import validate_image_size
from oases.models import Oasis

from .authentication import check_account_status
from .models import SELF_SIGNUP_ROLES, Profile, Role, User, validate_roles
from .phone import normalize_phone


def clean_phone(value):
    try:
        return normalize_phone(value)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.messages) from exc


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    roles = serializers.ListField(
        child=serializers.ChoiceField(choices=SELF_SIGNUP_ROLES),
        allow_empty=False,
        help_text="« farmer », « seller » ou les deux.",
    )

    class Meta:
        model = User
        fields = ["id", "phone", "full_name", "password", "roles", "preferred_language", "status"]
        read_only_fields = ["id", "status"]

    def validate_phone(self, value):
        phone = clean_phone(value)
        if User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError("Ce numéro est déjà utilisé.")
        return phone

    def validate_roles(self, value):
        try:
            validate_roles(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return value

    def validate(self, attrs):
        candidate = User(phone=attrs.get("phone"), full_name=attrs.get("full_name"))
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages}) from exc
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class PhoneTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Connexion par téléphone + mot de passe ; le compte doit être validé."""

    def validate(self, attrs):
        try:
            attrs[self.username_field] = normalize_phone(attrs[self.username_field])
        except DjangoValidationError:
            pass  # numéro mal écrit : l'authentification échouera normalement (401)
        data = super().validate(attrs)
        check_account_status(self.user)
        # Signal standard de Django : met à jour last_login et inscrit la connexion au journal.
        user_logged_in.send(
            sender=self.user.__class__, request=self.context.get("request"), user=self.user
        )
        return data


class ApprovedTokenRefreshSerializer(TokenRefreshSerializer):
    """Rafraîchissement refusé si le compte a été suspendu entre-temps."""

    def validate(self, attrs):
        refresh = RefreshToken(attrs["refresh"])
        user_id = refresh.payload.get(jwt_settings.USER_ID_CLAIM)
        user = User.objects.filter(**{jwt_settings.USER_ID_FIELD: user_id}).first()
        if user is not None:
            check_account_status(user)
        return super().validate(attrs)


class ProfileSerializer(serializers.ModelSerializer):
    oasis = serializers.PrimaryKeyRelatedField(
        queryset=Oasis.objects.filter(is_active=True), allow_null=True, required=False
    )

    class Meta:
        model = Profile
        fields = ["oasis", "photo", "whatsapp", "address", "business_name"]
        read_only_fields = ["photo"]

    def validate_whatsapp(self, value):
        return clean_phone(value) if value else value


class ProfilePhotoSerializer(serializers.ModelSerializer):
    photo = serializers.ImageField(validators=[validate_image_size])

    class Meta:
        model = Profile
        fields = ["photo"]


class MeSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer()

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "full_name",
            "roles",
            "preferred_language",
            "status",
            "registered_by",
            "claimed_at",
            "date_joined",
            "profile",
        ]
        read_only_fields = [
            "id",
            "phone",
            "roles",
            "status",
            "registered_by",
            "claimed_at",
            "date_joined",
        ]

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", None)
        instance = super().update(instance, validated_data)
        if profile_data:
            for field, value in profile_data.items():
                setattr(instance.profile, field, value)
            instance.profile.save()
        return instance


class UserManageSerializer(serializers.ModelSerializer):
    """Vue Direction d'un compte : seuls le statut et l'activation sont modifiables."""

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "full_name",
            "roles",
            "preferred_language",
            "status",
            "is_active",
            "registered_by",
            "claimed_at",
            "date_joined",
            "last_login",
        ]
        read_only_fields = [f for f in fields if f not in ("status", "is_active")]


class ManagedFarmerSerializer(serializers.ModelSerializer):
    """Agriculteur vu par l'agent qui l'a inscrit."""

    can_edit = serializers.SerializerMethodField(
        help_text="Faux si l'agriculteur a repris la main."
    )

    class Meta:
        model = User
        fields = ["id", "phone", "full_name", "status", "claimed_at", "date_joined", "can_edit"]
        read_only_fields = fields

    def get_can_edit(self, obj):
        return obj.claimed_at is None


class AgentFarmerCreateSerializer(serializers.ModelSerializer):
    """Un agent de terrain inscrit un agriculteur (sans mot de passe : code de reprise)."""

    oasis = serializers.PrimaryKeyRelatedField(
        queryset=Oasis.objects.filter(is_active=True), required=False, allow_null=True
    )

    class Meta:
        model = User
        fields = ["id", "phone", "full_name", "preferred_language", "oasis", "status"]
        read_only_fields = ["id", "status"]

    def validate_phone(self, value):
        phone = clean_phone(value)
        if User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError("Ce numéro est déjà utilisé.")
        return phone

    def create(self, validated_data):
        oasis = validated_data.pop("oasis", None)
        user = User.objects.create_user(
            password=None,
            roles=[Role.FARMER],
            registered_by=self.context["request"].user,
            **validated_data,
        )
        if oasis:
            user.profile.oasis = oasis
            user.profile.save(update_fields=["oasis", "updated_at"])
        return user


class ClaimCodeSerializer(serializers.Serializer):
    claim_code = serializers.CharField(
        help_text="À remettre à l'agriculteur. Affiché une seule fois."
    )
    claim_code_expires_at = serializers.DateTimeField()


class ClaimAccountSerializer(serializers.Serializer):
    phone = serializers.CharField()
    code = serializers.CharField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_phone(self, value):
        return clean_phone(value)

    def validate(self, attrs):
        user = User.objects.filter(phone=attrs["phone"]).first()
        try:
            validate_password(attrs["password"], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages}) from exc
        return attrs


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()
