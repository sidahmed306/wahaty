"""Bénéfice = ventes − dépenses, calculé (jamais stocké) sur une période."""

from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import TruncMonth

from .models import ExpenseCategory

ZERO = Decimal("0.00")


def _total(queryset, field):
    return queryset.aggregate(total=Sum(field))["total"] or ZERO


def _by_month(queryset, date_field, amount_field):
    rows = (
        queryset.annotate(month=TruncMonth(date_field))
        .values("month")
        .annotate(total=Sum(amount_field))
    )
    return {row["month"].strftime("%Y-%m"): row["total"] for row in rows}


def _merge(*month_maps):
    merged = {}
    for month_map in month_maps:
        for month, total in month_map.items():
            merged[month] = merged.get(month, ZERO) + total
    return merged


def finance_summary(sales, expenses, orders, date_from=None, date_to=None):
    """Ventes = ventes directes (agriculteur) + commandes livrées (vendeur, Q5).

    `sales`, `expenses` et `orders` sont déjà filtrés (propriétaire, droits d'accès). Une
    commande compte à sa date de livraison.
    """
    from orders.models import OrderStatus

    sales = sales.filter(is_active=True)
    expenses = expenses.filter(is_active=True)
    orders = orders.filter(is_active=True, status=OrderStatus.DELIVERED)
    if date_from:
        sales = sales.filter(sale_date__gte=date_from)
        expenses = expenses.filter(expense_date__gte=date_from)
        orders = orders.filter(delivered_at__date__gte=date_from)
    if date_to:
        sales = sales.filter(sale_date__lte=date_to)
        expenses = expenses.filter(expense_date__lte=date_to)
        orders = orders.filter(delivered_at__date__lte=date_to)

    direct_sales_total = _total(sales, "total_amount")
    orders_total = _total(orders, "total_amount")
    sales_total = direct_sales_total + orders_total
    expenses_total = _total(expenses, "amount")

    category_rows = (
        expenses.values("category").annotate(total=Sum("amount")).order_by("-total", "category")
    )
    categories = ExpenseCategory.objects.in_bulk([r["category"] for r in category_rows])

    sales_months = _merge(
        _by_month(sales, "sale_date", "total_amount"),
        _by_month(orders, "delivered_at", "total_amount"),
    )
    expense_months = _by_month(expenses, "expense_date", "amount")
    months = sorted(set(sales_months) | set(expense_months))

    return {
        "date_from": date_from,
        "date_to": date_to,
        "direct_sales_total": direct_sales_total,
        "orders_total": orders_total,
        "sales_total": sales_total,
        "expenses_total": expenses_total,
        "profit": sales_total - expenses_total,
        "expenses_by_category": [
            {"category": categories[r["category"]], "total": r["total"]} for r in category_rows
        ],
        "by_month": [
            {
                "month": m,
                "sales": sales_months.get(m, ZERO),
                "expenses": expense_months.get(m, ZERO),
                "profit": sales_months.get(m, ZERO) - expense_months.get(m, ZERO),
            }
            for m in months
        ],
    }
