from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse, HttpResponse
from django.shortcuts import resolve_url
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_POST

from menu.models import MenuItem
from .models import Order, OrderItem

# Optional DB-managed discount rules (admin-manageable)
try:
    from orders.models import DiscountRule  # type: ignore
except Exception:
    DiscountRule = None  # type: ignore

try:
    import stripe  # type: ignore
except Exception:  # pragma: no cover
    stripe = None  # graceful fallback if library not installed


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _to_cents(amount: Decimal | int | float) -> int:
    d = Decimal(str(amount or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int((d * 100).to_integral_value(rounding=ROUND_HALF_UP))


def _price_cents_from_menu(item: MenuItem) -> int:
    return _to_cents(Decimal(str(item.price or 0)))


def _rank_tip_cents_for_user(user) -> int:
    """
    Admin-configured DEFAULT tip (integer cents) based on the user's loyalty rank.
    IMPORTANT: This is ONLY a default/suggestion. If the client sends a tip, we
    ALWAYS respect the client's choice (including zero).
    """
    try:
        from loyality.models import LoyaltyProfile  # app name as in INSTALLED_APPS
        if not (user and getattr(user, "is_authenticated", False)):
            return 0
        lp = LoyaltyProfile.objects.select_related("rank").filter(user=user).first()
        if lp and lp.rank and lp.rank.is_active:
            return int(lp.rank.tip_cents or 0)
        return 0
    except Exception:
        return 0


def _db_threshold_discount_cents(subtotal_cents: int) -> int:
    """
    If orders.DiscountRule exists, choose the best active rule for the subtotal.
    Business rule: apply the **largest** discount where subtotal ≥ threshold.
    """
    if not DiscountRule:
        return 0
    try:
        rules = (
            DiscountRule.objects.filter(is_active=True, threshold_cents__lte=subtotal_cents)
            .order_by("-discount_cents")
            .values_list("discount_cents", flat=True)
        )
        return int(rules[0]) if rules else 0
    except Exception:
        return 0


def _builtin_threshold_discount_cents(subtotal_cents: int) -> int:
    """
    Built-in fallback if DB rules are absent.
     - ≥ 200000¢ → 10000¢
     - ≥ 300000¢ → 20000¢
    """
    if subtotal_cents >= 300000:
        return 20000
    if subtotal_cents >= 200000:
        return 10000
    return 0


def _threshold_discount_cents(subtotal_cents: int) -> int:
    db = _db_threshold_discount_cents(subtotal_cents)
    return db if db > 0 else _builtin_threshold_discount_cents(subtotal_cents)


def _success_url(request: HttpRequest) -> str:
    return request.build_absolute_uri(resolve_url("/my-orders/"))


def _cancel_url(request: HttpRequest) -> str:
    return request.build_absolute_uri(resolve_url("/cart/"))


def _persist_order(
    user,
    currency: str,
    delivery: str,
    db_items: List[MenuItem],
    qty_by_id: Dict[int, int],
    tip_cents: int,
    discount_cents: int,
    stripe_session_id: str = "",
    stripe_payment_intent: str = "",
    status: str = "created",
) -> Order:
    """
    Create an Order + OrderItems snapshot using authoritative DB prices.
    """
    subtotal_cents = 0
    order = Order.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        currency=(currency or "usd").lower(),
        delivery=delivery,
        tip_cents=max(0, int(tip_cents)),
        discount_cents=max(0, int(discount_cents)),
        subtotal_cents=0,  # fill later
        total_cents=0,     # fill later
        stripe_session_id=stripe_session_id or "",
        stripe_payment_intent=stripe_payment_intent or "",
        status=status,
        meta={},
    )

    # Snapshot items
    for m in db_items:
        qty = int(qty_by_id.get(m.id, 0))
        if qty <= 0:
            continue
        unit_cents = _price_cents_from_menu(m)
        line_total = unit_cents * qty
        subtotal_cents += line_total
        OrderItem.objects.create(
            order=order,
            menu_item_id=m.id,
            name=m.name,
            unit_amount_cents=unit_cents,
            quantity=qty,
            line_total_cents=line_total,
        )

    total_cents = max(0, subtotal_cents + order.tip_cents - order.discount_cents)
    order.subtotal_cents = subtotal_cents
    order.total_cents = total_cents
    order.save(update_fields=["subtotal_cents", "total_cents"])
    return order


# -----------------------------------------------------------------------------
# Checkout
# -----------------------------------------------------------------------------

@login_required
@require_POST
@csrf_protect
def checkout(request: HttpRequest) -> JsonResponse:
    """
    Create a Stripe Checkout Session (or simulate if keys not provided).
    Server is authoritative for pricing.

    Request JSON:
      { items: [{id, qty}], tip_cents, discount_cents, delivery }
    """
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"detail": "Invalid JSON body."}, status=400)

    items: List[dict] = payload.get("items") or []
    client_tip_raw = payload.get("tip_cents", None)
    client_discount_raw = payload.get("discount_cents", 0)
    delivery: str = (payload.get("delivery") or "DINE_IN").upper()

    if not isinstance(items, list) or not items:
        return JsonResponse({"detail": "No items to checkout."}, status=400)

    # Validate quantities
    qty_by_id: Dict[int, int] = {}
    for x in items:
        try:
            i = int(x.get("id"))
            q = int(x.get("qty") or 0)
            if q > 0:
                qty_by_id[i] = qty_by_id.get(i, 0) + q
        except Exception:
            pass
    if not qty_by_id:
        return JsonResponse({"detail": "Quantities are invalid."}, status=400)

    # Authoritative items from DB
    db_items = list(MenuItem.objects.filter(id__in=qty_by_id.keys(), is_available=True))
    if len(db_items) != len(qty_by_id):
        return JsonResponse({"detail": "Some items are unavailable."}, status=400)

    # Compute subtotal (authoritative)
    subtotal_cents = sum(_price_cents_from_menu(m) * qty_by_id.get(m.id, 0) for m in db_items)

    # TIP: client override respected; otherwise default to rank-based suggestion
    if client_tip_raw is None:
        tip_cents = max(0, _rank_tip_cents_for_user(request.user))
    else:
        try:
            tip_cents = max(0, int(client_tip_raw or 0))
        except Exception:
            tip_cents = 0

    # DISCOUNT: sum of client-provided fixed discount + threshold rule
    try:
        client_discount = max(0, int(client_discount_raw or 0))
    except Exception:
        client_discount = 0
    discount_cents = client_discount + max(0, _threshold_discount_cents(subtotal_cents))

    currency = (settings.STRIPE_CURRENCY or "usd").lower()

    # Simulated mode (no Stripe keys)
    if not settings.STRIPE_SECRET_KEY or stripe is None:
        order = _persist_order(
            user=request.user,
            currency=currency,
            delivery=delivery,
            db_items=db_items,
            qty_by_id=qty_by_id,
            tip_cents=tip_cents,
            discount_cents=discount_cents,
            status="paid",
        )
        return JsonResponse(
            {
                "ok": True,
                "mode": "simulated",
                "subtotal_cents": order.subtotal_cents,
                "tip_cents": order.tip_cents,
                "discount_cents": order.discount_cents,
                "total_cents": order.total_cents,
                "paid": True,
                "redirect_url": _success_url(request),
                "order_id": order.id,
            }
        )

    # Real Stripe checkout
    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY  # type: ignore[attr-defined]

        # Build Stripe line items with server price_data
        line_items_for_stripe: List[dict] = []
        for m in db_items:
            qty = qty_by_id.get(m.id, 0)
            if qty <= 0:
                continue
            price_cents = _price_cents_from_menu(m)
            line_items_for_stripe.append(
                {
                    "quantity": qty,
                    "price_data": {
                        "currency": currency,
                        "unit_amount": price_cents,
                        "product_data": {
                            "name": m.name,
                            "description": (m.description or "")[:500],
                        },
                    },
                }
            )

        # Add tip as a separate positive line item (fixed amount)
        if tip_cents > 0:
            line_items_for_stripe.append(
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": currency,
                        "unit_amount": tip_cents,
                        "product_data": {"name": "Tip"},
                    },
                }
            )

        # Persist discount info in metadata (Stripe doesn't allow negative line items)
        metadata = {
            "user_id": str(getattr(request.user, "id", "")),
            "delivery": delivery,
            "tip_cents": str(tip_cents),
            "discount_cents": str(discount_cents),
            "subtotal_cents": str(subtotal_cents),
        }

        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=line_items_for_stripe,
            success_url=_success_url(request),
            cancel_url=_cancel_url(request),
            metadata=metadata,
            currency=currency,
        )

        # Persist order as created (pending payment)
        order = _persist_order(
            user=request.user,
            currency=currency,
            delivery=delivery,
            db_items=db_items,
            qty_by_id=qty_by_id,
            tip_cents=tip_cents,
            discount_cents=discount_cents,
            stripe_session_id=session.id,
            status="created",
        )

        return JsonResponse({"ok": True, "redirect_url": session.url, "order_id": order.id})
    except Exception as e:
        return JsonResponse({"detail": f"Stripe error: {e}"}, status=400)


# -----------------------------------------------------------------------------
# Webhook (marks orders as paid)
# -----------------------------------------------------------------------------

@csrf_exempt
@require_POST
def webhook(request: HttpRequest) -> HttpResponse:
    if not settings.STRIPE_WEBHOOK_SECRET or stripe is None:
        # If webhook not configured, acknowledge to avoid retries in dev
        return HttpResponse(status=200)

    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY  # type: ignore[attr-defined]
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    except Exception:
        return HttpResponse(status=400)

    etype = event.get("type")
    data = event.get("data", {}).get("object", {})

    # checkout.session.completed → mark order paid and clear cart
    if etype == "checkout.session.completed":
        session_id = data.get("id", "")
        payment_intent = data.get("payment_intent", "") or ""
        try:
            order = Order.objects.get(stripe_session_id=session_id)
            if payment_intent and not order.stripe_payment_intent:
                order.stripe_payment_intent = str(payment_intent)
            order.status = "paid"
            order.save(update_fields=["status", "stripe_payment_intent"])
            
            # Clear session cart for the user after successful payment
            _clear_user_session_cart(order.created_by)
            
        except Order.DoesNotExist:
            pass

    # payment_intent.succeeded (redundant safety)
    if etype == "payment_intent.succeeded":
        pi_id = data.get("id", "")
        if pi_id:
            try:
                order = Order.objects.get(stripe_payment_intent=pi_id)
                if order.status != "paid":
                    order.status = "paid"
                    order.save(update_fields=["status"])
                    
                    # Clear session cart for the user after successful payment
                    _clear_user_session_cart(order.created_by)
                    
            except Order.DoesNotExist:
                pass

    return HttpResponse(status=200)


def _clear_user_session_cart(user):
    """
    Clear the session cart for a specific user after successful payment.
    This is called from the webhook handler when payment is confirmed.
    """
    if not user:
        return
        
    try:
        from django.contrib.sessions.models import Session
        from django.contrib.auth.models import AnonymousUser
        
        # For authenticated users, we need to find their active sessions
        # and clear the cart data from those sessions
        if user and not isinstance(user, AnonymousUser):
            # Get all active sessions
            sessions = Session.objects.filter(expire_date__gte=timezone.now())
            
            for session in sessions:
                try:
                    session_data = session.get_decoded()
                    # Check if this session belongs to our user
                    if session_data.get('_auth_user_id') == str(user.id):
                        # Clear cart-related session data
                        if 'cart' in session_data:
                            del session_data['cart']
                        if 'cart_last_activity' in session_data:
                            del session_data['cart_last_activity']
                        if 'cart_last_modified' in session_data:
                            del session_data['cart_last_modified']
                        if '_cart_init_done' in session_data:
                            del session_data['_cart_init_done']
                        
                        # Save the updated session
                        session.session_data = session.encode(session_data)
                        session.save()
                except Exception:
                    # Skip sessions that can't be decoded or updated
                    continue
                    
    except Exception:
        # Fail silently - cart clearing is not critical for payment processing
        pass
