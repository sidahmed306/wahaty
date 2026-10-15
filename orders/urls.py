from rest_framework.routers import SimpleRouter

from . import views

app_name = "orders"

router = SimpleRouter()
router.register("orders", views.OrderViewSet, basename="order")
router.register("notifications", views.NotificationViewSet, basename="notification")

urlpatterns = router.urls
