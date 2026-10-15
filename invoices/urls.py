from rest_framework.routers import SimpleRouter

from . import views

app_name = "invoices"

router = SimpleRouter()
router.register("invoices", views.InvoiceViewSet, basename="invoice")

urlpatterns = router.urls
