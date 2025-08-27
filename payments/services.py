# FILE: payments/services.py
from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple, List, Dict, Any

from io import BytesIO

import stripe
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.db import transaction

from payments.models import Payment
from orders.models import Order
from engagement.models import OrderExtras
from engagement.services import (
    get_pending_tip_for_user,
    best_loyalty_discount_for_user,
    choose_better_discount,
    clear_pending_tips_for_user,
)

logger = logging.getLogger(__name__)
stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")


# ---------------------------
# Money / URL helpers
# ---------------------------
def _currency() -> str:
    # keep API compatible with your existing codebase
    return getattr(settings, "CURRENCY", getattr(settings, "STRIPE_CURRENCY", "usd")).lower()


def _money_cents(amount: Decimal) -> int:
    q = Decimal(amount or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int((q * 100).to_integral_value())


def _success_url(order: Order) -> str:
    return getattr(settings, "SITE_URL", "").rstrip("/") + reverse("payments:checkout-success")


def _cancel_url(order: Order) -> str:
    return getattr(settings, "SITE_URL", "").rstrip("/") + reverse("payments:checkout-cancel")


# ---------------------------
# Order extras (uses engagement.OrderExtras rows)
# ---------------------------
def _get_extra_amount(order: Order, name: str) -> Decimal:
    """
    Fetch a single extra by name (e.g., 'tip', 'coupon_discount', 'loyalty_discount').
    Returns Decimal('0.00') if not found.
    """
    try:
        row = OrderExtras.objects.filter(order=order, name=name).order_by("-id").first()
        return Decimal(str(row.amount)) if row else Decimal("0.00")
    except Exception:
        logger.exception("Failed to read OrderExtras '%s' for order %s", name, getattr(order, "id", None))
        return Decimal("0.00")


def _set_extra_amount(order: Order, name: str, amount: Decimal) -> None:
    """
    Upsert a single extra by name.
    """
    try:
        obj, _ = OrderExtras.objects.get_or_create(order=order, name=name, defaults={"amount": Decimal("0.00")})
        if Decimal(str(obj.amount)) != Decimal(str(amount)):
            obj.amount = Decimal(str(amount)).quantize(Decimal("0.01"))
            obj.save(update_fields=["amount"])
    except Exception:
        logger.exception("Failed to save OrderExtras '%s' for order %s", name, getattr(order, "id", None))


# ---------------------------
# Totals
# ---------------------------
def compute_order_total(order: Order) -> Tuple[Decimal, Decimal]:
    """
    Returns (subtotal, tax) for the order items only (no tips/discounts).
    Implementations may vary; keep API stable.
    """
    subtotal = Decimal("0.00")
    for it in order.items.all():
        unit = Decimal(str(getattr(it, "unit_price", 0) or 0))
        qty = int(getattr(it, "quantity", 0) or 0)
        subtotal += (unit * qty)
    subtotal = subtotal.quantize(Decimal("0.01"))
    tax_rate = Decimal(str(getattr(settings, "SALES_TAX_RATE", 0) or 0))  # e.g. 0.075
    tax = (subtotal * tax_rate).quantize(Decimal("0.01"))
    return subtotal, tax


def _build_line_items(order: Order, tip_amount: Decimal) -> List[Dict[str, Any]]:
    """
    Build Stripe Checkout line_items:
    - One "Order #<id>" items line (subtotal+tax)
    - "Tip" as a separate positive line item if > 0
    Loyalty/coupon discount is passed via Checkout 'discounts' because Stripe does NOT allow negative unit_amount.
    """
    subtotal, tax = compute_order_total(order)
    lines: List[Dict[str, Any]] = [{
        "price_data": {
            "currency": _currency(),
            "product_data": {"name": f"Order #{order.id}"},
            "unit_amount": _money_cents(subtotal + tax),
        },
        "quantity": 1,
    }]
    if tip_amount and Decimal(tip_amount) > 0:
        lines.append({
            "price_data": {
                "currency": _currency(),
                "product_data": {"name": "Tip"},
                "unit_amount": _money_cents(Decimal(tip_amount)),
            },
            "quantity": 1,
        })
    return lines


def _apply_best_discount(order: Order, loyalty_amount: Decimal, coupon_amount: Decimal) -> Tuple[Dict[str, Any], Decimal, str]:
    """
    Create a one-off Stripe Coupon for amount_off = chosen discount (if any)
    and return (discounts_param, chosen_amount, source_label) for Checkout Session.
    """
    amount, source = choose_better_discount(loyalty_amount, coupon_amount)
    if amount <= 0:
        return {}, Decimal("0.00"), "none"

    # Create or reuse a short-lived coupon
    try:
        coupon = stripe.Coupon.create(
            amount_off=_money_cents(amount),
            currency=_currency(),
            duration="once",
            name=f"{source.title()} discount",
        )
        return {"discounts": [{"coupon": coupon["id"]}]}, amount, source
    except Exception:
        logger.exception("Failed to create Stripe coupon; proceeding without discount")
        return {}, Decimal("0.00"), "none"


# ---------------------------
# Stripe Checkout
# ---------------------------
def create_checkout_session(order: Order):
    """
    Builds a Stripe Checkout Session with items + tip + best discount (loyalty vs coupon).
    Stores resolved numbers as OrderExtras rows so invoices/receipts show correct lines.
    """
    success_url = _success_url(order)
    cancel_url = _cancel_url(order)

    # Resolve tip from PendingTip or existing extras
    user = getattr(order, "user", None) or getattr(order, "created_by", None)
    tip_amount = _get_extra_amount(order, "tip")
    if tip_amount <= 0:
        # fall back to pending tip recorder
        pending = get_pending_tip_for_user(user)
        if pending > 0:
            tip_amount = pending
            _set_extra_amount(order, "tip", tip_amount)

    # Loyalty vs Coupon (exclude tips from base)
    subtotal, tax = compute_order_total(order)
    loyalty_amount, loyalty_msg = best_loyalty_discount_for_user(user, subtotal=subtotal + tax)
    coupon_amount = _get_extra_amount(order, "coupon_discount")  # if your flow saves coupon elsewhere, adapt here

    discounts_param, chosen_amount, chosen_source = _apply_best_discount(order, loyalty_amount, coupon_amount)
    if chosen_source == "loyalty" and loyalty_msg:
        _set_extra_amount(order, "loyalty_discount", chosen_amount)
    elif chosen_source == "coupon":
        _set_extra_amount(order, "coupon_discount", chosen_amount)

    # Build line items (tip shown as its own line)
    line_items = _build_line_items(order, tip_amount)

    # Create the session
    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=line_items,
        metadata={"order_id": str(order.id)},
        client_reference_id=str(order.id),
        success_url=success_url,
        cancel_url=cancel_url,
        **(discounts_param or {}),
    )

    # Update Payment record if present
    try:
        pay, _ = Payment.objects.get_or_create(order=order, defaults={"provider": getattr(Payment, "PROVIDER_STRIPE", "stripe")})
        pay.stripe_session_id = session.get("id")
        pay.stripe_checkout_url = session.get("url")
        pay.currency = _currency()
        pay.save(update_fields=["stripe_session_id", "stripe_checkout_url", "currency"])
    except Exception:
        logger.exception("Failed to link Payment to Stripe Session for order %s", order.id)

    # Persist final numbers for invoice/receipt lines (excluding tips from base)
    try:
        final_total = (subtotal + tax - (chosen_amount or Decimal("0.00"))).quantize(Decimal("0.01"))
        _set_extra_amount(order, "final_total_excl_tip", final_total)
    except Exception:
        logger.exception("Failed to save final totals for order %s", order.id)

    return session


# ---------------------------
# Invoice PDF (optional)
# ---------------------------
def generate_order_invoice_pdf(order: Order) -> tuple[str, bytes] | tuple[None, None]:
    """
    Create a minimal invoice PDF that includes a 'Tip' line and discounts from OrderExtras.
    Plug into your existing pipeline; left simple to avoid breaking current PDF styling.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except Exception:
        logger.warning("reportlab not installed; skipping invoice PDF generation")
        return None, None

    subtotal, tax = compute_order_total(order)
    tip = _get_extra_amount(order, "tip")
    loyalty = _get_extra_amount(order, "loyalty_discount")
    coupon = _get_extra_amount(order, "coupon_discount")
    final_total = _get_extra_amount(order, "final_total_excl_tip") or (subtotal + tax)

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800

    def line(txt: str) -> None:
        nonlocal y
        c.drawString(50, y, txt)
        y -= 16

    line(f"Invoice for Order #{order.id}")
    line("")
    line(f"Items Subtotal: {subtotal}")
    line(f"Tax: {tax}")
    if coupon > 0:
        line(f"Coupon Discount: -{coupon}")
    if loyalty > 0:
        line(f"Loyalty Discount: -{loyalty}")
    if tip > 0:
        line(f"Tip: {tip}")
    line(f"Total (excl. tip): {final_total}")
    line(f"Grand Total: {(final_total + tip).quantize(Decimal('0.01'))}")
    c.showPage()
    c.save()

    filename = f"invoice_order_{order.id}.pdf"
    return filename, buf.getvalue()


def save_invoice_pdf_file(order: Order) -> Optional[str]:
    try:
        filename, pdf_bytes = generate_order_invoice_pdf(order)
        if not filename or not pdf_bytes:
            return None
        if hasattr(order, "invoice_pdf"):
            from django.core.files.base import ContentFile
            if not order.invoice_pdf:
                order.invoice_pdf.save(filename, ContentFile(pdf_bytes), save=True)
        return filename
    except Exception as e:
        logger.exception("Failed to save invoice PDF: %s", e)
        return None


# ---------------------------
# Payment finalization hook (needed by payments/views.py)
# ---------------------------
def mark_paid(order: Order, stripe_event: Optional[dict[str, Any]] = None) -> None:
    """
    Finalize order after Stripe confirms payment (webhook or success handler).
    - Mark as PAID / is_paid
    - Set paid_at
    - Clear user's pending tips
    - Do not modify other features (invoices, coupons, RMS admin, etc.)
    """
    if not order:
        return
    if getattr(order, "is_paid", False):
        # idempotent
        return

    with transaction.atomic():
        # Mark paid
        if hasattr(order, "is_paid"):
            order.is_paid = True
        if hasattr(order, "status"):
            order.status = "PAID"
        if hasattr(order, "paid_at"):
            order.paid_at = timezone.now()
        order.save(update_fields=[f for f in ["is_paid", "status", "paid_at"] if hasattr(order, f)])

        # Clear pending tips for this user
        user = getattr(order, "user", None) or getattr(order, "created_by", None)
        try:
            clear_pending_tips_for_user(user)
        except Exception:
            logger.exception("Failed to clear pending tips for user after payment (order %s)", order.id)

        # Optionally persist a final invoice PDF
        try:
            save_invoice_pdf_file(order)
        except Exception:
            logger.exception("Failed to save invoice for order %s", order.id)
