from __future__ import annotations

from django.apps import AppConfig


class OrdersExtrasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "orders_extras"
    verbose_name = "Orders Extras (shim)"
