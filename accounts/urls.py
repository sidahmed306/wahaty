from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

app_name = "accounts"

router = SimpleRouter()
router.register("users", views.UserManageViewSet, basename="user")
router.register("agent/farmers", views.ManagedFarmerViewSet, basename="managed-farmer")

urlpatterns = [
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/refresh/", views.RefreshView.as_view(), name="refresh"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/claim/", views.ClaimAccountView.as_view(), name="claim"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    path("auth/me/photo/", views.MePhotoView.as_view(), name="me-photo"),
    *router.urls,
]
