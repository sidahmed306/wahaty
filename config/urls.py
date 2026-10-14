from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Wahaty – Direction"
admin.site.site_title = "Wahaty"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("accounts.urls")),
    path("api/", include("oases.urls")),
]

if settings.DEBUG:  # pragma: no cover – en local seulement : afficher les photos
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
