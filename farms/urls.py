from rest_framework.routers import SimpleRouter

from . import views

app_name = "farms"

router = SimpleRouter()
router.register("farms", views.FarmViewSet, basename="farm")
router.register("palm-groups", views.PalmGroupViewSet, basename="palm-group")
router.register("harvests", views.HarvestViewSet, basename="harvest")

urlpatterns = router.urls
