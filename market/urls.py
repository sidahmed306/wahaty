from rest_framework.routers import SimpleRouter

from . import views

app_name = "market"

router = SimpleRouter()
router.register("market/listings", views.PublicListingViewSet, basename="public-listing")
router.register("market/my-listings", views.MyListingViewSet, basename="my-listing")
router.register("market/review", views.ListingReviewViewSet, basename="listing-review")

urlpatterns = router.urls
