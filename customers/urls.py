from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

app_name = "customers"

router = SimpleRouter()
router.register("customers", views.CustomerViewSet, basename="customer")
router.register("customer-payments", views.PaymentViewSet, basename="customer-payment")

urlpatterns = [
    path("settings/", views.PlatformSettingsView.as_view(), name="platform-settings"),
    *router.urls,
]
