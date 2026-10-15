from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from .models import AccountStatus, Profile, Role, User


class RolesFormMixin(forms.ModelForm):
    """Rôles affichés en cases à cocher dans l'administration."""

    roles = forms.MultipleChoiceField(
        label="Rôles", choices=Role.choices, widget=forms.CheckboxSelectMultiple
    )


class UserCreationAdminForm(RolesFormMixin, AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("phone", "full_name", "roles")


class UserChangeAdminForm(RolesFormMixin, UserChangeForm):
    class Meta:
        model = User
        fields = (
            "phone",
            "password",
            "full_name",
            "preferred_language",
            "roles",
            "status",
            "is_active",
            "registered_by",
            "claimed_at",
            "is_staff",
            "is_superuser",
            "groups",
            "user_permissions",
        )


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    fields = ("oasis", "photo", "whatsapp", "address", "business_name")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserChangeAdminForm
    add_form = UserCreationAdminForm
    inlines = [ProfileInline]
    ordering = ("-date_joined",)
    list_display = ("phone", "full_name", "roles", "status", "is_active", "date_joined")
    list_filter = ("status", "is_active", "is_staff")
    search_fields = ("phone", "full_name")
    readonly_fields = ("date_joined", "last_login", "updated_at")
    actions = ["approve_accounts", "suspend_accounts"]

    def get_inlines(self, request, obj):
        # À la création, le profil est créé automatiquement (signals.py) : pas de formulaire.
        return self.inlines if obj else []

    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        ("Identité", {"fields": ("full_name", "preferred_language")}),
        ("Rôles et statut", {"fields": ("roles", "status", "is_active")}),
        ("Agent de terrain", {"fields": ("registered_by", "claimed_at")}),
        (
            "Accès administration",
            {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Dates", {"fields": ("date_joined", "last_login", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("phone", "full_name", "roles", "password1", "password2"),
            },
        ),
    )

    @admin.action(description="Valider les comptes sélectionnés")
    def approve_accounts(self, request, queryset):
        count = self._set_status(queryset, AccountStatus.APPROVED)
        self.message_user(request, f"{count} compte(s) validé(s).", messages.SUCCESS)

    @admin.action(description="Suspendre les comptes sélectionnés")
    def suspend_accounts(self, request, queryset):
        count = self._set_status(queryset.exclude(pk=request.user.pk), AccountStatus.SUSPENDED)
        self.message_user(request, f"{count} compte(s) suspendu(s).", messages.WARNING)

    @staticmethod
    def _set_status(queryset, status):
        # Un par un (et non queryset.update) : chaque changement passe par le journal d'audit.
        users = list(queryset)
        for user in users:
            user.status = status
            user.save(update_fields=["status", "updated_at"])
        return len(users)
