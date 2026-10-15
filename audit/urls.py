from rest_framework.routers import SimpleRouter

from . import views

app_name = "audit"

router = SimpleRouter()
router.register("audit", views.AuditLogViewSet, basename="audit")

urlpatterns = router.urls
