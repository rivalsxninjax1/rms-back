from __future__ import annotations

from django.urls import path
from . import views
from . import views_platform as v2

app_name = "integrations"

urlpatterns = [
    # New direct provider webhooks
    path("ubereats/webhook/", v2.ubereats_webhook, name="ubereats_webhook"),
    path("doordash/webhook/", v2.doordash_webhook, name="doordash_webhook"),
    path("grubhub/webhook/", v2.grubhub_webhook, name="grubhub_webhook"),

    # Back-office APIs
    path("menu/sync/", views.sync_menu, name="sync_menu"),
    path("inventory/availability/", views.update_item_availability, name="inventory_availability"),
    path("orders/recent/", views.recent_orders, name="recent_orders"),
    path("reports/sales/", views.sales_report, name="sales_report"),
    path("order/status/", views.push_order_status, name="order_status"),
]
