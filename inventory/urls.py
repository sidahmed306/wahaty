from rest_framework.routers import SimpleRouter

from . import views

app_name = "inventory"

router = SimpleRouter()
router.register("suppliers", views.SupplierViewSet, basename="supplier")
router.register("products", views.ProductViewSet, basename="product")
router.register("stock-movements", views.StockMovementViewSet, basename="stock-movement")
router.register("purchases", views.PurchaseViewSet, basename="purchase")
router.register("supplier-payments", views.SupplierPaymentViewSet, basename="supplier-payment")

urlpatterns = router.urls
