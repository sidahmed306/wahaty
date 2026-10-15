"""Chiffres du tableau de bord, calculés à la demande (aucune table).

Chaque chiffre est pris sur les données **visibles** par l'utilisateur (filter_readable) :
la Direction voit tout, un agriculteur ou un vendeur ses données, un agent ses inscrits.
Les montants (ventes, dépenses, bénéfice) portent sur une période : par défaut, l'année
en cours jusqu'à aujourd'hui.
"""

from decimal import Decimal

from django.db.models import Count, F, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from accounts.models import AccountStatus, Role, User
from core.access import filter_readable, managed_farmers
from customers.models import Customer
from customers.stats import with_balance as customers_with_balance
from farms.models import Farm, Harvest, PalmGroup
from farms.totals import palm_totals, production_totals
from finance.models import Expense, Sale
from finance.summary import finance_summary
from inventory.models import Product, Supplier
from inventory.services import with_balance as suppliers_with_balance
from inventory.services import with_stock
from market.models import Listing, ListingStatus
from orders.models import CLOSED_STATUSES, Notification, Order, OrderStatus

ZERO = Decimal("0.00")


def _sum(queryset, field):
    return queryset.aggregate(total=Coalesce(Sum(field), ZERO))["total"]


def _readable(model, user, owner_field="owner"):
    return filter_readable(model.objects.all(), user, owner_field)


def money(user, date_from, date_to, owner=None):
    sales, expenses, orders = (_readable(m, user) for m in (Sale, Expense, Order))
    if owner is not None:
        sales, expenses, orders = (qs.filter(owner=owner) for qs in (sales, expenses, orders))
    data = finance_summary(sales, expenses, orders, date_from, date_to)
    keys = ("direct_sales_total", "orders_total", "sales_total", "expenses_total", "profit")
    return {key: data[key] for key in keys}


def palms_and_production(user):
    palms, total = palm_totals(
        _readable(PalmGroup, user, "farm__owner").filter(farm__is_active=True)
    )
    _, by_season = production_totals(
        _readable(Harvest, user, "farm__owner").filter(farm__is_active=True)
    )
    return {
        "farms": _readable(Farm, user).filter(is_active=True).count(),
        "palms": total,
        "palms_by_variety": [
            {"variety": p["variety"].name_fr, "variety_ar": p["variety"].name_ar, **_counts(p)}
            for p in palms
        ],
        "production_by_season": by_season,
    }


def _counts(row):
    return {k: row[k] for k in ("productive", "young", "total")}


def orders_figures(user):
    orders = _readable(Order, user).filter(is_active=True)
    counts = dict(orders.values_list("status").annotate(n=Count("id")))
    late = orders.exclude(status__in=CLOSED_STATUSES).filter(
        expected_delivery_date__lt=timezone.localdate()
    )
    return {
        "by_status": {status: counts.get(status, 0) for status in OrderStatus.values},
        "late": late.count(),
    }


def amounts_due(user):
    customers = customers_with_balance(_readable(Customer, user).filter(is_active=True))
    suppliers = suppliers_with_balance(_readable(Supplier, user).filter(is_active=True))
    return {
        "customers_owe": _sum(customers.filter(balance__gt=0), "balance"),
        "customer_advances": -_sum(customers.filter(balance__lt=0), "balance"),
        "suppliers_owed": _sum(suppliers, "balance"),
    }


def stock_figures(user):
    products = with_stock(_readable(Product, user).filter(is_active=True))
    priced = products.filter(sale_price__isnull=False)
    return {
        "products": products.count(),
        "low_stock": products.filter(
            low_stock_threshold__isnull=False, stock__lte=F("low_stock_threshold")
        ).count(),
        # Valeur au prix de vente conseillé (produits sans prix : non comptés).
        "stock_value": _sum(priced.annotate(value=F("stock") * F("sale_price")), "value"),
    }


def direction_dashboard(user, date_from, date_to):
    accounts = User.objects.filter(is_active=True)
    listings = Listing.objects.filter(is_active=True)
    return {
        "period": {"date_from": date_from, "date_to": date_to},
        "accounts": {
            "farmers": accounts.filter(roles__contains=[Role.FARMER]).count(),
            "sellers": accounts.filter(roles__contains=[Role.SELLER]).count(),
            "field_agents": accounts.filter(roles__contains=[Role.FIELD_AGENT]).count(),
            "pending": accounts.filter(status=AccountStatus.PENDING).count(),
            "suspended": accounts.filter(status=AccountStatus.SUSPENDED).count(),
        },
        **palms_and_production(user),
        "market": {
            "published": listings.filter(status=ListingStatus.PUBLISHED).count(),
            "pending": listings.filter(status=ListingStatus.PENDING).count(),
        },
        "orders": orders_figures(user),
        "stock": stock_figures(user),
        "amounts_due": amounts_due(user),
        "money": money(user, date_from, date_to),
    }


def personal_dashboard(user, date_from, date_to):
    data = {
        "period": {"date_from": date_from, "date_to": date_to},
        "roles": user.roles,
        "unread_notifications": Notification.objects.filter(
            user=user, read_at__isnull=True
        ).count(),
    }
    if user.has_role(Role.FARMER):
        data["farmer"] = {
            **palms_and_production(user),
            "money": money(user, date_from, date_to, owner=user),
        }
    if user.has_role(Role.SELLER):
        data["seller"] = {
            "customers": _readable(Customer, user).filter(is_active=True).count(),
            "orders": orders_figures(user),
            "stock": stock_figures(user),
            "amounts_due": amounts_due(user),
            "money": money(user, date_from, date_to, owner=user),
        }
    if user.has_role(Role.FIELD_AGENT):
        farmers = managed_farmers(user)
        data["field_agent"] = {
            "farmers": farmers.count(),
            "farmers_claimed": farmers.filter(claimed_at__isnull=False).count(),
            "farmers_pending": farmers.filter(status=AccountStatus.PENDING).count(),
            **palms_and_production(user),
        }
    return data
