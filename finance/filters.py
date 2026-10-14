import django_filters

from .models import Expense, Sale


class SaleFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="sale_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="sale_date", lookup_expr="lte")

    class Meta:
        model = Sale
        fields = ["owner", "farm", "variety", "date_from", "date_to"]


class ExpenseFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="expense_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="expense_date", lookup_expr="lte")

    class Meta:
        model = Expense
        fields = ["owner", "category", "farm", "date_from", "date_to"]
