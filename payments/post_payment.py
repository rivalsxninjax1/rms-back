# FILE: payments/post_payment.py
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional, Iterable

from django.conf import settings
from django.core.mail import send_mail
from django.dispatch import Signal

logger = logging.getLogger(__name__)

# Public signal that other apps (RMS / kitchen) can listen to.
# Receivers get kwargs: order, payment, request (optional)
order_paid: Signal = Signal()

# ---------- Helpers ----------

def _num(x) -> Decimal:
    try:
        from decimal import Decimal as D
        return x if isinstance(x, D) else D(str(x))
    except Exception:
        return Decimal("0")

def _iter_items(order) -> Iterable:
    try:
        return order.items.select_related("menu_item").all()
    except Exception:
        try:
            return order.items.all()
        except Exception:
            return []

def _menu_item_name(mi) -> str:
    try:
        return getattr(mi, "name", f"Item {getattr(mi, 'id', '')}")
    except Exception:
        return "Item"

def _customer_email(order) -> Optional[str]:
    # Try common places: order.email, order.customer.email, order.created_by.email, order.user.email
    for path in ("email", "customer.email", "created_by.email", "user.email"):
        try:
            obj = order
            for attr in path.split("."):
                obj = getattr(obj, attr, None)
                if obj is None:
                    break
            if obj:
                s = str(obj).strip()
                if "@" in s:
                    return s
        except Exception:
            continue
    return None

# ---------- Stock decrement ----------

def decrement_stock_for_order(order) -> None:
    """
    Best-effort stock decrement.
    Looks for one of: menu_item.decrement_stock(qty), menu_item.stock, menu_item.quantity_in_stock, menu_item.available_quantity.
    Never lets stock go < 0. Completely silent if model doesn't support stock.
    """
    changed_any = False
    for it in _iter_items(order):
        qty = int(getattr(it, "quantity", 0) or 0)
        if qty <= 0:
            continue
        mi = getattr(it, "menu_item", None)
        if mi is None:
            continue

        try:
            # Method first (best)
            dec = getattr(mi, "decrement_stock", None)
            if callable(dec):
                dec(qty)
                changed_any = True
                continue

            # Common numeric fields
            for field in ("stock", "quantity_in_stock", "available_quantity"):
                if hasattr(mi, field):
                    cur = int(getattr(mi, field) or 0)
                    new_val = max(0, cur - qty)
                    if new_val != cur:
                        setattr(mi, field, new_val)
                        mi.save(update_fields=[field])
                        changed_any = True
                    break  # only one field is used
        except Exception:
            logger.exception("Failed to decrement stock for menu_item=%s", getattr(mi, "id", None))

    if changed_any:
        logger.info("Stock decremented for order #%s", getattr(order, "id", None))

# ---------- Email receipt ----------

def email_receipt(order, payment=None) -> None:
    """
    Sends a simple text receipt to the customer, if email is available and email is configured.
    """
    try:
        to_email = _customer_email(order)
        if not to_email:
            return

        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "") or getattr(settings, "SERVER_EMAIL", "")
        if not from_email:
            # email not configured
            return

        lines = [f"Thank you for your order #{order.id}!", ""]
        total = Decimal("0.00")
        for it in _iter_items(order):
            qty = int(getattr(it, "quantity", 0) or 0)
            unit = _num(getattr(it, "unit_price", 0) or 0)
            name = _menu_item_name(getattr(it, "menu_item", None))
            line = unit * qty
            total += line
            lines.append(f"- {name} x {qty} @ {unit} = {line}")

        # Add order-level amounts if present
        try:
            tip = _num(getattr(order, "tip_amount", 0) or 0)
            if tip > 0:
                lines.append(f"Tip: {tip}")
        except Exception:
            pass
        try:
            disc = _num(getattr(order, "discount_amount", 0) or 0)
            if disc > 0:
                lines.append(f"Discount: -{disc}")
        except Exception:
            pass

        # Prefer order.grand_total()
        try:
            grand_total = getattr(order, "grand_total", None)
            if callable(grand_total):
                grand_total = _num(grand_total())
            else:
                grand_total = _num(getattr(order, "total", total) or total)
        except Exception:
            grand_total = total

        lines.append("")
        lines.append(f"Total paid: {grand_total} {getattr(settings, 'STRIPE_CURRENCY', 'usd').upper()}")

        # Receipt footer
        site = getattr(settings, "SITE_URL", "")
        if site:
            lines.append("")
            lines.append(f"View your order: {site}")

        subject = f"Receipt for Order #{order.id}"
        body = "\n".join(lines)

        send_mail(subject, body, from_email, [to_email], fail_silently=True)
    except Exception:
        logger.exception("Failed sending receipt email for order #%s", getattr(order, "id", None))

# ---------- Kitchen / RMS signal ----------

def emit_kitchen_signal(order, payment=None, request=None) -> None:
    """
    Broadcast a signal that an order has been paid.
    RMS/kitchen apps can listen and generate tickets, prints, screens, etc.
    """
    try:
        order_paid.send(sender=order.__class__, order=order, payment=payment, request=request)
    except Exception:
        logger.exception("Failed emitting order_paid signal for order #%s", getattr(order, "id", None))

# ---------- Orchestrator ----------

def run_post_payment_hooks(order, payment=None, request=None) -> None:
    """
    Execute all post-payment steps. Each step is fully guarded.
    Idempotency: callers should ensure this is only run when the order transitions to PAID.
    """
    # Immediate synchronous tasks (critical for order flow)
    decrement_stock_for_order(order)
    emit_kitchen_signal(order, payment=payment, request=request)
    
    # Async tasks for non-critical post-payment processing
    try:
        from .tasks import (
            send_order_confirmation_email_task,
            send_staff_notification_task,
            sync_order_to_pos_task,
            record_payment_analytics_task,
            process_loyalty_rewards_task,
            update_inventory_levels_task
        )
        
        # Queue async tasks
        order_id = order.id
        payment_data = {
            'payment_method_type': getattr(payment, 'payment_method_type', 'unknown') if payment else 'unknown'
        }
        
        # Send confirmation emails
        send_order_confirmation_email_task.delay(order_id)
        send_staff_notification_task.delay(order_id)
        
        # POS integration
        sync_order_to_pos_task.delay(order_id)
        
        # Analytics and loyalty
        record_payment_analytics_task.delay(order_id, payment_data)
        process_loyalty_rewards_task.delay(order_id)
        
        # Inventory management (additional to immediate stock decrement)
        update_inventory_levels_task.delay(order_id)
        
        logger.info(f"Queued async post-payment tasks for order {order_id}")
        
    except ImportError:
        # Fallback to synchronous processing if Celery is not available
        logger.info("Celery not available, falling back to synchronous email processing")
        email_receipt(order, payment=payment)
