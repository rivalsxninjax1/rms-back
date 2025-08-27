# FILE: orders/signals_cart.py
from __future__ import annotations
from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List, Tuple

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.db import transaction

from orders.models import Order, OrderItem
from menu.models import MenuItem


def _normalize_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalize any cart-like list to: [{ "id": <menu_item_id>, "quantity": int }, ...]
    Deduplicate by id and sum quantities.
    """
    bucket: Dict[int, int] = defaultdict(int)
    for raw in items or []:
        pid = raw.get("menu_item_id") or raw.get("menu_item") or raw.get("product") or raw.get("id")
        qty = raw.get("quantity") or raw.get("qty") or 1
        try:
            pid = int(pid)
            qty = int(qty)
        except Exception:
            continue
        if pid > 0 and qty > 0:
            bucket[pid] += qty
    return [{"id": k, "quantity": v} for k, v in bucket.items()]


def _fetch_price(mi_id: int) -> Decimal:
    mi = MenuItem.objects.get(pk=mi_id)
    return Decimal(str(getattr(mi, "price", 0)))


@receiver(user_logged_in)
def merge_session_cart_into_user_order(sender, request, user, **kwargs):
    """
    On login: merge session cart -> user's open PENDING Order.
    - Sum quantities
    - Create missing items
    - Keep unit prices in sync with MenuItem.price
    - Finally, clear the session cart
    """
    try:
        session_items = _normalize_items(request.session.get("cart", []))
        if not session_items:
            return

        with transaction.atomic():
            order = (
                Order.objects.select_for_update()
                .filter(created_by=user, status="PENDING", is_paid=False)
                .order_by("-id")
                .first()
            )
            if not order:
                order = Order.objects.create(
                    created_by=user,
                    status="PENDING",
                    currency=getattr(order, "currency", "usd") if order else "usd",
                )

            existing = {oi.menu_item_id: oi for oi in order.items.select_related("menu_item")}
            for it in session_items:
                pid, qty = int(it["id"]), int(it["quantity"])
                unit = _fetch_price(pid)
                if pid in existing:
                    oi = existing[pid]
                    oi.quantity = int(oi.quantity) + qty
                    oi.unit_price = unit
                    oi.save(update_fields=["quantity", "unit_price"])
                else:
                    OrderItem.objects.create(order=order, menu_item_id=pid, quantity=qty, unit_price=unit)

        # clear session cart after successful merge
        request.session["cart"] = []
        request.session.modified = True

    except Exception:
        # never block login
        pass


@receiver(user_logged_out)
def clear_cart_on_logout(sender, request, user, **kwargs):
    """
    On logout, clear the session cart so a new browser session starts at zero.
    (Your DB orders remain untouched.)
    """
    try:
        request.session["cart"] = []
        request.session.modified = True
    except Exception:
        pass
