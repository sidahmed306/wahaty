from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("dashboard/direction/", views.DirectionDashboardView.as_view(), name="direction"),
    path("dashboard/me/", views.MyDashboardView.as_view(), name="me"),
]
