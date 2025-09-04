from __future__ import annotations

import json
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Any

import stripe
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse, HttpResponse
from django.shortcuts import resolve_url
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_POST, require_http_methods
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from menu.models import MenuItem
from .models import Order, OrderItem, StripePaymentIntent
from billing.models import Payment
from billing.serializers import OfflinePaymentCreateSerializer
from payments.post_payment import order_paid as signal_order_paid
from .services import (
    checkout_session_from_order,
    mark_order_as_paid,
    stripe_service,
)

logger = logging.getLogger(__name__)
stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")

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
        from loyalty.models import LoyaltyProfile  # canonical app path (label unchanged)
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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def offline_payment(request: HttpRequest) -> Response:
    """
    Record an offline payment for an order.
    Body: { order_id, method: 'cash'|'pos_card', amount, notes? }
    Requires authenticated user (recommended staff-only at router).
    """
    ser = OfflinePaymentCreateSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=400)
    data = ser.validated_data
    order_id = data['order_id']
    try:
        from orders.models import Order as CoreOrder
        order = CoreOrder.objects.get(id=int(order_id))
    except Exception:
        return Response({'detail': 'Order not found'}, status=404)

    # Create Payment
    pay = Payment.objects.create(
        order=order,
        amount=data['amount'],
        currency=(getattr(settings, 'STRIPE_CURRENCY', 'usd') or 'usd').upper(),
        method=data['method'],
        status='captured',
        external_ref=None,
        notes=str(data.get('notes') or ''),
        created_by=request.user,
    )

    # Mark order's payment_status (leave status transitions to UI/workflow)
    try:
        if hasattr(order, 'payment_status'):
            order.payment_status = 'COMPLETED'
            order.save(update_fields=['payment_status'])
    except Exception:
        pass

    # Emit order_paid for hooks (ticketing/invoice, etc.)
    try:
        signal_order_paid.send(sender=order.__class__, order=order, payment=pay, request=request)
    except Exception:
        logger.exception('Failed emitting order_paid for offline payment, order %s', order.id)

    return Response({'ok': True, 'payment_id': pay.id})

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
# Checkout landing pages (used by payments.services success/cancel)
# -----------------------------------------------------------------------------
@require_http_methods(["GET"])
def checkout_success(request: HttpRequest) -> HttpResponse:
    """Simple success page after Stripe redirects back.
    If webhooks are configured, the order/payment will be finalized there.
    """
    context: Dict[str, Any] = {"order": None, "invoice_url": None}
    # Optionally, if we ever include session_id in success_url, we could fetch more details here.
    try:
        from orders.models import Order as CoreOrder
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            last_order = CoreOrder.objects.filter(user=user).order_by("-created_at").first()
            context["order"] = last_order
    except Exception:
        pass
    # Render a lightweight template (present in payments/templates)
    from django.shortcuts import render
    return render(request, "payments/checkout_success.html", context)


@require_http_methods(["GET"])
def checkout_cancel(request: HttpRequest) -> HttpResponse:
    """Redirect back to cart when user cancels on Stripe."""
    from django.shortcuts import redirect
    return redirect("storefront:cart_full")


# -----------------------------------------------------------------------------
# Webhook (marks orders as paid)
# -----------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_payment_intent(request):
    """
    Create a Stripe Payment Intent for an order or custom amount.
    
    Expected payload:
    {
        "amount_cents": 1000,  # Required: amount in cents
        "currency": "usd",     # Optional: defaults to 'usd'
        "order_id": 123,       # Optional: associate with order
        "metadata": {...}      # Optional: additional metadata
    }
    """
    try:
        data = request.data
        amount_cents = data.get('amount_cents')
        
        if not amount_cents or not isinstance(amount_cents, int):
            return Response(
                {'error': 'amount_cents is required and must be an integer'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if amount_cents < 50:
            return Response(
                {'error': 'Amount must be at least $0.50 (50 cents)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        currency = data.get('currency', 'usd')
        order_id = data.get('order_id')
        metadata = data.get('metadata', {})
        
        # Get associated order if provided
        order = None
        if order_id:
            try:
                order = Order.objects.get(id=order_id, user=request.user)
            except Order.DoesNotExist:
                return Response(
                    {'error': 'Order not found or access denied'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Create payment intent
        payment_intent = stripe_service.create_payment_intent(
            amount_cents=amount_cents,
            currency=currency,
            order=order,
            user=request.user,
            metadata=metadata
        )
        
        return Response({
            'payment_intent_id': payment_intent.stripe_payment_intent_id,
            'client_secret': payment_intent.stripe_client_secret,
            'amount_cents': payment_intent.amount_cents,
            'currency': payment_intent.currency,
            'status': payment_intent.status,
        }, status=status.HTTP_201_CREATED)
        
    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error in create_payment_intent: {e}")
        return Response(
            {'error': 'Payment processing error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        logger.error(f"Unexpected error in create_payment_intent: {e}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_intent_status(request, payment_intent_id):
    """
    Get the status of a payment intent.
    """
    try:
        payment_intent = StripePaymentIntent.objects.get(
            stripe_payment_intent_id=payment_intent_id,
            user=request.user
        )
        
        return Response({
            'payment_intent_id': payment_intent.stripe_payment_intent_id,
            'status': payment_intent.status,
            'amount_cents': payment_intent.amount_cents,
            'currency': payment_intent.currency,
            'created_at': payment_intent.created_at,
            'confirmed_at': payment_intent.confirmed_at,
            'is_successful': payment_intent.is_successful(),
            'is_pending': payment_intent.is_pending(),
        })
        
    except StripePaymentIntent.DoesNotExist:
        return Response(
            {'error': 'Payment intent not found or access denied'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error retrieving payment intent status: {e}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_payment_intent(request, payment_intent_id):
    """
    Cancel a payment intent if possible.
    """
    try:
        payment_intent = StripePaymentIntent.objects.get(
            stripe_payment_intent_id=payment_intent_id,
            user=request.user
        )
        
        if not payment_intent.can_be_canceled():
            return Response(
                {'error': f'Payment intent cannot be canceled (status: {payment_intent.status})'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        success = stripe_service.cancel_payment_intent(payment_intent)
        
        if success:
            return Response({
                'message': 'Payment intent canceled successfully',
                'payment_intent_id': payment_intent.stripe_payment_intent_id,
                'status': payment_intent.status,
            })
        else:
            return Response(
                {'error': 'Failed to cancel payment intent'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    except StripePaymentIntent.DoesNotExist:
        return Response(
            {'error': 'Payment intent not found or access denied'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error canceling payment intent: {e}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@csrf_exempt
@require_http_methods(["POST"])
def stripe_webhook(request):
    """
    Handle Stripe webhooks with comprehensive signature verification and idempotency.
    
    This endpoint processes various Stripe events including:
    - payment_intent.succeeded
    - payment_intent.payment_failed
    - payment_intent.canceled
    - charge.dispute.created
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    
    # Verify webhook signature
    if not stripe_service.verify_webhook_signature(payload, sig_header):
        logger.error("Webhook signature verification failed")
        return HttpResponse(
            'Invalid signature',
            status=400,
            content_type='text/plain'
        )
    
    try:
        # Parse event data
        event_data = json.loads(payload.decode('utf-8'))
        event_type = event_data.get('type', 'unknown')
        event_id = event_data.get('id', 'unknown')
        
        logger.info(f"Processing Stripe webhook event: {event_type} (ID: {event_id})")
        
        # Process the webhook event
        success = stripe_service.process_webhook_event(event_data)
        
        if success:
            logger.info(f"Successfully processed webhook event: {event_type}")
            return HttpResponse(
                'Webhook processed successfully',
                status=200,
                content_type='text/plain'
            )
        else:
            logger.error(f"Failed to process webhook event {event_data.get('id')}")
            return HttpResponse(
                'Webhook processing failed',
                status=500,
                content_type='text/plain'
            )
            
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in webhook payload: {e}")
        return HttpResponse(
            'Invalid JSON payload',
            status=400,
            content_type='text/plain'
        )
    except Exception as e:
        logger.error(f"Unexpected error processing webhook: {e}")
        return HttpResponse(
            'Internal server error',
            status=500,
            content_type='text/plain'
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_analytics(request):
    """
    Get payment analytics for the specified date range.
    """
    from datetime import datetime, timedelta
    from django.utils import timezone
    
    # Parse date parameters
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    try:
        if start_date_str:
            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        else:
            start_date = timezone.now() - timedelta(days=30)
            
        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        else:
            end_date = timezone.now()
            
        analytics = stripe_service.get_payment_analytics(start_date, end_date)
        return Response(analytics)
        
    except ValueError as e:
        return Response({'error': f'Invalid date format: {e}'}, status=400)
    except Exception as e:
        logger.error(f"Error generating payment analytics: {e}")
        return Response({'error': 'Failed to generate analytics'}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_setup_intent(request):
    """
    Create a SetupIntent for saving payment methods.
    """
    try:
        customer_id = request.data.get('customer_id')
        usage = request.data.get('usage', 'off_session')
        
        setup_intent = stripe_service.create_setup_intent(customer_id, usage)
        return Response(setup_intent)
        
    except Exception as e:
        logger.error(f"Error creating SetupIntent: {e}")
        return Response({'error': 'Failed to create SetupIntent'}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def customer_payment_methods(request, customer_id):
    """
    Get all payment methods for a customer.
    """
    try:
        payment_methods = stripe_service.get_customer_payment_methods(customer_id)
        return Response({'payment_methods': payment_methods})
        
    except Exception as e:
        logger.error(f"Error retrieving payment methods: {e}")
        return Response({'error': 'Failed to retrieve payment methods'}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_receipt(request, order_id):
    """
    Generate and return a receipt PDF for an order.
    """
    try:
        from django.http import HttpResponse
        from orders.models import Order
        
        order = Order.objects.get(id=order_id)
        payment_intent = StripePaymentIntent.objects.filter(order=order).first()
        
        filename, pdf_content = stripe_service.generate_receipt_pdf(order, payment_intent)
        
        if not pdf_content:
            return Response({'error': 'Failed to generate receipt'}, status=500)
        
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    except Order.DoesNotExist:
        return Response({'error': 'Order not found'}, status=404)
    except Exception as e:
        logger.error(f"Error generating receipt: {e}")
        return Response({'error': 'Failed to generate receipt'}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_refund(request, payment_intent_id):
    """
    Create a refund for a payment intent.
    """
    try:
        payment_intent = StripePaymentIntent.objects.get(id=payment_intent_id)
        amount_cents = request.data.get('amount_cents')
        reason = request.data.get('reason', 'requested_by_customer')
        
        refund = stripe_service.create_refund(payment_intent, amount_cents, reason)
        
        return Response({
            'refund_id': refund.id,
            'stripe_refund_id': refund.stripe_refund_id,
            'amount': refund.amount_dollars,
            'status': refund.status,
            'reason': refund.reason,
        })
        
    except StripePaymentIntent.DoesNotExist:
        return Response({'error': 'Payment intent not found'}, status=404)
    except Exception as e:
        logger.error(f"Error creating refund: {e}")
        return Response({'error': 'Failed to create refund'}, status=500)


# Legacy webhook endpoint for backward compatibility
@csrf_exempt
@require_POST
def webhook(request: HttpRequest) -> HttpResponse:
    """Legacy webhook handler - redirects to new comprehensive handler."""
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
            # Create captured payment record
            try:
                Payment.objects.create(
                    order=order,
                    amount=getattr(order, 'total_cents', 0) / 100 if hasattr(order, 'total_cents') else getattr(order, 'total', 0),
                    currency=(settings.STRIPE_CURRENCY or 'usd').upper(),
                    method='stripe',
                    status='captured',
                    external_ref=str(payment_intent) if payment_intent else None,
                    notes='Stripe checkout.session.completed',
                )
            except Exception:
                logger.exception('Failed to create Billing Payment for order %s on checkout.session.completed', getattr(order, 'id', None))

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
                    # Create captured payment record
                    try:
                        Payment.objects.create(
                            order=order,
                            amount=getattr(order, 'total_cents', 0) / 100 if hasattr(order, 'total_cents') else getattr(order, 'total', 0),
                            currency=(settings.STRIPE_CURRENCY or 'usd').upper(),
                            method='stripe',
                            status='captured',
                            external_ref=str(pi_id),
                            notes='Stripe payment_intent.succeeded',
                        )
                    except Exception:
                        logger.exception('Failed to create Billing Payment for order %s on payment_intent.succeeded', getattr(order, 'id', None))

                    # Clear session cart for the user after successful payment
                    _clear_user_session_cart(order.created_by)
                    
            except Order.DoesNotExist:
                pass

    return HttpResponse(status=200)


def _clear_user_session_cart(user):
    """Clear cart data from all sessions belonging to a specific user using session management utility."""
    from django.contrib.auth.models import AnonymousUser
    import logging
    
    logger = logging.getLogger(__name__)
    
    if not user or isinstance(user, AnonymousUser):
        return
    
    try:
        # Use the SessionCartManager's class method for clearing user sessions
        from orders.session_utils import SessionCartManager
        cleared_count = SessionCartManager.clear_user_sessions(user)
        
        logger.info(f"Cleared cart data from {cleared_count} sessions for user {user.id}")
        
    except Exception as e:
        logger.error(f"Failed to clear user sessions for user {user.id}: {e}")
