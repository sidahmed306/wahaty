from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

admin.site.site_header = "TRC إرث النخيل – Direction"
admin.site.site_title = "TRC"


def health(request):
    """Réponse rapide pour Render (le service est vivant), sans toucher à la base."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health, name="health"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger"),
    path("api/", include("accounts.urls")),
    path("api/", include("oases.urls")),
    path("api/", include("farms.urls")),
    path("api/", include("finance.urls")),
    path("api/", include("inventory.urls")),
    path("api/", include("customers.urls")),
    path("api/", include("orders.urls")),
    path("api/", include("invoices.urls")),
    path("api/", include("market.urls")),
    path("api/", include("dashboard.urls")),
    path("api/", include("audit.urls")),
]

if settings.DEBUG:  # pragma: no cover – en local seulement : afficher les photos
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
