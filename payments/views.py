# payments/views.py
from __future__ import annotations
import json
import logging
from typing import Any, Dict, Optional

import stripe
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction, IntegrityError
from django.http import HttpRequest, HttpResponse, JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from orders.models import Order
from payments.models import StripeEvent
from payments.services import (
    create_checkout_session,
    mark_paid,
    save_invoice_pdf_file,
)

logger = logging.getLogger(__name__)
stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")


# ---------------- Checkout session (keeps your URL) ---------------- #

@login_required
def create_checkout_session_view(request: HttpRequest, order_id: int):
    """
    GET  -> 302 redirect to Stripe Checkout
    POST -> JSON { url: "..." } for SPA usage
    Uses the DB order only (Step 1 already made DB the source of truth).
    """
    qs = Order.objects.filter(pk=order_id)
    # Multi-tenant safety: respect created_by if present
    if hasattr(Order, "created_by_id"):
        qs = qs.filter(created_by=request.user)
    order = get_object_or_404(qs)

    session = create_checkout_session(order)

    if request.method == "GET":
        url = getattr(session, "url", None)
        if not url:
            return HttpResponseRedirect(reverse("payments:checkout_success"))
        return HttpResponseRedirect(url)
    return JsonResponse({"url": getattr(session, "url", None)}, status=201)


# ---------------- Stripe webhook (fast + idempotent) --------------- #

def _get_webhook_secret() -> str:
    sec = (getattr(settings, "STRIPE_WEBHOOK_SECRET", "") or "").strip()
    if not sec:
        logger.error("STRIPE_WEBHOOK_SECRET missing in settings/.env")
    return sec

@csrf_exempt
def stripe_webhook(request: HttpRequest) -> HttpResponse:
    """
    Signature-verified, idempotent, and FAST:
    - Verify signature
    - Insert StripeEvent (unique by event_id)
    - Handle minimal logic (mark_paid)
    - ALWAYS return 200 immediately (prevents 'Broken pipe')
    """
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    endpoint_secret = _get_webhook_secret()

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        logger.warning("Invalid webhook: %s", e)
        return HttpResponse(status=400)

    event_id = event.get("id")
    event_type = event.get("type")
    obj = event.get("data", {}).get("object", {}) or {}

    # Idempotency store
    try:
        with transaction.atomic():
            StripeEvent.objects.create(
                event_id=event_id,
                event_type=event_type,
                payload=json.dumps(event),
            )
    except IntegrityError:
        # Already processed -> ACK again
        return HttpResponse(status=200)

    # Lightweight routing
    try:
        if event_type in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            _on_checkout_session_completed(obj)
        elif event_type == "payment_intent.succeeded":
            _on_payment_intent_succeeded(obj)
        # else ignore
    except Exception:
        logger.exception("Error handling Stripe event %s", event_type)

    return HttpResponse(status=200)


def _on_checkout_session_completed(session: Dict[str, Any]) -> None:
    """
    Main success path. Uses metadata.order_id or client_reference_id.
    Updates Payment + Order via mark_paid (includes paid_at/status/is_paid).
    """
    order_id = (session.get("metadata") or {}).get("order_id") or session.get("client_reference_id")
    if not order_id:
        logger.warning("checkout.session.completed without order_id/client_reference_id")
        return
    try:
        order = Order.objects.get(pk=int(order_id))
    except Exception:
        logger.warning("Order %s not found for checkout.session.completed", order_id)
        return

    payment_intent_id = session.get("payment_intent") or ""
    session_id = session.get("id") or ""
    mark_paid(order, payment_intent_id=payment_intent_id, session_id=session_id)


def _on_payment_intent_succeeded(intent: Dict[str, Any]) -> None:
    """
    Optional secondary path if you rely on PI metadata.
    """
    order_id = (intent.get("metadata") or {}).get("order_id")
    if not order_id:
        return
    try:
        order = Order.objects.get(pk=int(order_id))
    except Exception:
        return
    payment_intent_id = intent.get("id") or intent.get("payment_intent") or ""
    mark_paid(order, payment_intent_id=payment_intent_id, session_id=None)


# ---------------- Success / Cancel (keeps your templates) ---------- #

def _verify_and_mark_paid_if_needed(session_id: Optional[str]) -> Optional[Order]:
    """
    Small helper for success page: if webhook hasn't marked the order yet,
    verify the session with Stripe and mark paid as a fallback.
    Returns the Order (if found) or None.
    """
    if not session_id:
        return None
    try:
        session = stripe.checkout.Session.retrieve(session_id, expand=["payment_intent"])
    except Exception as e:
        logger.info("Unable to retrieve Checkout Session %s: %s", session_id, e)
        return None

    order_id = (session.get("metadata") or {}).get("order_id") or session.get("client_reference_id")
    if not order_id:
        return None
    try:
        order = Order.objects.get(pk=int(order_id))
    except Exception:
        return None

    # If not already marked by webhook, mark it now (fallback)
    is_paid = bool(getattr(order, "is_paid", False) or getattr(order, "status", "") == "PAID")
    if not is_paid and str(session.get("payment_status")) == "paid":
        try:
            pi = session.get("payment_intent")
            pi_id = (pi.get("id") if isinstance(pi, dict) else str(pi)) or ""
            mark_paid(order, payment_intent_id=pi_id, session_id=str(session.get("id") or ""))
        except Exception:
            logger.exception("Fallback mark_paid failed for order %s", order.id)
    return order


def checkout_success(request: HttpRequest):
    """
    Render success page. We:
      - Try to verify the session_id and (if needed) mark the order paid (fallback).
      - Generate/attach invoice url if available.
      - Clear the session cart (DB order remains as the paid record).
    """
    order = None
    invoice_url = None
    try:
        session_id = request.GET.get("session_id")
        if session_id:
            order = _verify_and_mark_paid_if_needed(session_id) or order
        # Also try via ?order=<id> for robustness
        if not order:
            oid = int(request.GET.get("order") or 0)
            if oid:
                order = Order.objects.filter(pk=oid).first()
        if order:
            try:
                save_invoice_pdf_file(order)  # idempotent
                if getattr(order, "invoice_pdf", None):
                    invoice_url = order.invoice_pdf.url
            except Exception:
                pass
    except Exception:
        pass

    # Clear server-side session cart (best-effort)
    try:
        request.session["cart"] = []
        request.session.modified = True
    except Exception:
        pass

    # Use your existing storefront success template if you prefer;
    # keeping a payments-scoped template is also fine.
    return render(request, "storefront/checkout_success.html", {"order": order, "invoice_url": invoice_url})


def checkout_cancel(request: HttpRequest):
    return render(request, "storefront/checkout_cancel.html")
