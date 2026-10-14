from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

app_name = "finance"

router = SimpleRouter()
router.register("expense-categories", views.ExpenseCategoryViewSet, basename="expense-category")
router.register("sales", views.SaleViewSet, basename="sale")
router.register("expenses", views.ExpenseViewSet, basename="expense")

urlpatterns = [
    path("finance/summary/", views.FinanceSummaryView.as_view(), name="summary"),
    *router.urls,
]
