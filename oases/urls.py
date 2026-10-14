from rest_framework.routers import SimpleRouter

from . import views

app_name = "oases"

router = SimpleRouter()
router.register("regions", views.RegionViewSet, basename="region")
router.register("oases", views.OasisViewSet, basename="oasis")
router.register("varieties", views.DateVarietyViewSet, basename="variety")
router.register("oasis-photos", views.OasisPhotoViewSet, basename="oasis-photo")

urlpatterns = router.urls
