from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Wahaty – Direction"
admin.site.site_title = "Wahaty"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("accounts.urls")),
]
