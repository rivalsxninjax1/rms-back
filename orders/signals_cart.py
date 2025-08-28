# orders/signals_cart.py
from __future__ import annotations
from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.db import transaction

from orders.models import Order, OrderItem
from menu.models import MenuItem


def _session_items(request) -> List[Dict[str, Any]]:
    items = request.session.get("cart") or []
    if not isinstance(items, list):
        items = []
    # Normalize to [{id:int, quantity:int}]
    norm = []
    for row in items:
        try:
            pid = int(row.get("id"))
            qty = int(row.get("quantity"))
            if qty > 0:
                norm.append({"id": pid, "quantity": qty})
        except Exception:
            continue
    return norm


def _upsert_order_item(order: Order, menu_item_id: int, qty: int):
    mi = MenuItem.objects.select_related(None).get(pk=menu_item_id)
    oi, created = OrderItem.objects.get_or_create(
        order=order, menu_item=mi, defaults={"quantity": qty, "unit_price": mi.price}
    )
    if not created:
        oi.quantity = max(1, int(oi.quantity) + int(qty))
    oi.unit_price = mi.price  # always sync current price snapshot
    oi.save(update_fields=["quantity", "unit_price"])


@receiver(user_logged_in)
def merge_cart_on_login(sender, request, user, **kwargs):
    """
    On login:
      - Ensure user has a single open PENDING Order (their "saved cart").
      - Merge guest session cart into that order.
      - Mirror merged items back into session cart so UI shows them.
    """
    try:
        session_items = _session_items(request)
        with transaction.atomic():
            order, _ = Order.objects.select_for_update().get_or_create(
                user=user, status=Order.STATUS_PENDING, defaults={"currency": "NPR"}
            )
            for row in session_items:
                _upsert_order_item(order, row["id"], row["quantity"])

            # Mirror back to session
            new_session = []
            for oi in order.items.select_related("menu_item").all():
                new_session.append({"id": oi.menu_item_id, "quantity": int(oi.quantity)})
            request.session["cart"] = new_session
            request.session.modified = True
    except Exception:
        # Never block login
        pass


@receiver(user_logged_out)
def clear_cart_on_logout(sender, request, user, **kwargs):
    """
    On logout, clear the session cart so a new browser session starts at zero.
    (DB orders remain untouched.)
    """
    try:
        request.session["cart"] = []
        request.session.modified = True
    except Exception:
        pass
