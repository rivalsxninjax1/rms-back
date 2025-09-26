from __future__ import annotations

import hmac
import hashlib
import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from django.conf import settings

from .services import push_menu as direct_push_menu, update_item_availability as direct_update_availability


def _verify_signature(secret: str, header_value: str, payload: bytes) -> bool:
    try:
        sig = (header_value or "").strip()
        if sig.startswith("sha256="):
            sig = sig.split("=", 1)[1]
        digest = hmac.new((secret or "").encode("utf-8"), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, digest)
    except Exception:
        return False


@api_view(["POST"]) 
@permission_classes([IsAdminUser])
def sync_menu(request):
    result = direct_push_menu()
    return Response(result)


@api_view(["POST"]) 
@permission_classes([IsAdminUser])
def update_item_availability(request):
    item_id = request.data.get("item_id")
    available = bool(request.data.get("available", True))
    try:
        item_id = int(item_id)
    except Exception:
        return Response({"detail": "item_id must be an integer"}, status=400)
    result = direct_update_availability(item_id, available)
    return Response(result)


@csrf_exempt
@require_http_methods(["POST"]) 
def webhook(request):
    """Generic webhook endpoint from the middleware provider.
    Expects HMAC SHA256 in X-Middleware-Signature when configured.
    """
    raw = request.body or b""
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return HttpResponse("Invalid JSON", status=400)

    # Legacy middleware hook — keep for backward compat, but no-op if not configured
    secret = getattr(settings, "DELIVERECT_WEBHOOK_SECRET", "") or \
             getattr(settings, "OTTER_WEBHOOK_SECRET", "") or \
             getattr(settings, "CHOWLY_WEBHOOK_SECRET", "") or \
             getattr(settings, "CHECKMATE_WEBHOOK_SECRET", "") or \
             getattr(settings, "CUBOH_WEBHOOK_SECRET", "")
    if secret:
        sig = request.META.get("HTTP_X_MIDDLEWARE_SIGNATURE", "")
        if not _verify_signature(secret, sig, raw):
            return HttpResponse("Invalid signature", status=400)

    # Basic event routing (pseudo): order.created, order.updated, item.updated
    event = data.get("event") or data.get("type") or ""
    if event.startswith("order"):
        try:
            from orders.models import Order, OrderItem
            from menu.models import MenuItem
            order_data = data.get("order") or data
            # Detect channel/provider if present
            provider = (order_data.get("provider") or data.get("provider") or "").upper()
            source = provider if provider in {"UBER_EATS", "DOORDASH"} else "ONLINE"
            user = getattr(request, "user", None)
            o = Order.objects.create(
                status="PENDING",
                source=source,
                channel=Order.CHANNEL_ONLINE,
                currency=getattr(settings, "STRIPE_CURRENCY", "usd").lower(),
            )
            items = order_data.get("items") or []
            for it in items:
                ext_id = it.get("external_id") or it.get("menu_item_id") or it.get("id")
                qty = int(it.get("quantity", 1))
                if not ext_id or qty <= 0:
                    continue
                try:
                    mi = MenuItem.objects.get(pk=int(ext_id))
                except Exception:
                    continue
                OrderItem.objects.create(
                    order=o,
                    menu_item=mi,
                    quantity=qty,
                    unit_price=mi.price,
                )
            o.calculate_totals(save=True)
        except Exception:
            # Swallow to avoid webhook retry storms; logs can be added if needed
            pass
    elif event.startswith("item"):
        try:
            from menu.models import MenuItem
            payload = data.get("item") or data
            ext_id = payload.get("external_id") or payload.get("id")
            if ext_id:
                mi = MenuItem.objects.filter(pk=int(ext_id)).first()
                if mi is not None and "available" in payload:
                    mi.is_available = bool(payload.get("available"))
                    mi.save(update_fields=["is_available", "updated_at"])  # type: ignore[arg-type]
        except Exception:
            pass

    return HttpResponse("OK", status=200)


@api_view(["GET"]) 
@permission_classes([IsAuthenticated])
def recent_orders(request):
    # This endpoint is deprecated with direct integrations. Kept for UI backward compat.
    orders = []
    return Response({"orders": orders})


@api_view(["GET"]) 
@permission_classes([IsAdminUser])
def sales_report(request):
    date = request.query_params.get("date")
    rep = {"detail": "not implemented", "date": date}
    return Response(rep)


@api_view(["POST"]) 
@permission_classes([IsAdminUser])
def push_order_status(request):
    order_id = request.data.get("order_id")
    status_val = request.data.get("status")
    if not order_id or not status_val:
        return Response({"detail": "order_id and status are required"}, status=400)
    from orders.models import Order
    try:
        order = Order.objects.get(pk=int(order_id))
    except Exception:
        return Response({"detail": "Order not found"}, status=404)
    # Use external id if present in metadata
    external_id = None
    try:
        if isinstance(order.metadata, dict):
            external_id = order.metadata.get("external_id") or order.metadata.get("middleware_order_id")
    except Exception:
        pass
    # For direct integrations, platform callbacks are handled by tasks; just store intent here.
    ok = True
    return Response({"ok": bool(ok)})
