from __future__ import annotations

from typing import Any, Dict, Optional
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from .providers.ubereats import UberEatsClient
from .providers.doordash import DoorDashClient
from .models import ExternalOrder, SyncLog


def _log(provider: str, event: str, success: bool, message: str = "", payload: Optional[Dict[str, Any]] = None):
    SyncLog.objects.create(provider=provider, event=event, success=success, message=message or "", payload=payload or {})


def push_menu():
    from menu.models import MenuItem
    items = MenuItem.objects.filter(is_active=True)
    payload = {
        "items": [
            {
                "id": str(mi.id),
                "name": mi.name,
                "price": float(mi.price),
                "available": bool(getattr(mi, "is_available", True)),
            }
            for mi in items
        ]
    }
    ue = UberEatsClient()
    dd = DoorDashClient()
    r1 = ue.push_menu(payload)
    _log("UBEREATS", "push_menu", r1.ok, r1.error or "", payload)
    r2 = dd.push_menu(payload)
    _log("DOORDASH", "push_menu", r2.ok, r2.error or "", payload)
    return {"ubereats": r1.__dict__, "doordash": r2.__dict__}


def update_item_availability(item_id: int, available: bool):
    payload = {"id": str(item_id), "available": bool(available)}
    ue = UberEatsClient(); dd = DoorDashClient()
    r1 = ue.push_menu({"items": [payload]})
    _log("UBEREATS", "update_item", r1.ok, r1.error or "", payload)
    r2 = dd.push_menu({"items": [payload]})
    _log("DOORDASH", "update_item", r2.ok, r2.error or "", payload)
    return {"ubereats": r1.__dict__, "doordash": r2.__dict__}


def _create_order_from_payload(provider: str, ext_id: str, data: Dict[str, Any]):
    from orders.models import Order, OrderItem
    from menu.models import MenuItem
    with transaction.atomic():
        # Deduplicate by external id
        ext, created = ExternalOrder.objects.select_for_update().get_or_create(
            provider=provider,
            external_id=str(ext_id),
            defaults={"status": str(data.get("status") or "pending"), "last_payload": data, "order_id": None},
        )
        if ext.order_id:
            return ext.order
        o = Order.objects.create(
            status="PENDING",
            source=provider,
            channel=Order.CHANNEL_ONLINE,
            currency=getattr(settings, "STRIPE_CURRENCY", "usd").lower(),
            metadata={"external_id": ext_id, "provider": provider},
        )
        items = data.get("items") or []
        for it in items:
            raw_id = it.get("menu_item_id") or it.get("id") or it.get("external_id")
            qty = int(it.get("quantity", 1))
            if not raw_id or qty <= 0:
                continue
            try:
                mi = MenuItem.objects.get(pk=int(raw_id))
            except Exception:
                continue
            OrderItem.objects.create(order=o, menu_item=mi, quantity=qty, unit_price=mi.price)
        o.calculate_totals(save=True)
        ext.order = o
        ext.last_payload = data
        ext.save(update_fields=["order", "last_payload", "updated_at"])
        return o


def handle_webhook(provider: str, event: str, data: Dict[str, Any]):
    try:
        if event in ("order.created", "order_updated", "order_created", "order.new"):
            ext_id = str(data.get("id") or data.get("order_id") or data.get("external_id"))
            if not ext_id:
                _log(provider, event, False, "Missing external id", data)
                return {"ok": False, "detail": "missing external id"}
            o = _create_order_from_payload(provider, ext_id, data)
            _log(provider, event, True, f"Created/linked order {o.id}", {"external_id": ext_id})
            return {"ok": True, "order_id": o.id}
        elif event in ("order.status", "order_status_updated"):
            ext_id = str(data.get("id") or data.get("order_id") or "")
            status = str(data.get("status") or "").lower()
            if not ext_id or not status:
                return {"ok": False, "detail": "missing fields"}
            try:
                ext = ExternalOrder.objects.get(provider=provider, external_id=ext_id)
                o = ext.order
                # Map status values
                mapping = {
                    "pending": "PENDING",
                    "accepted": "CONFIRMED",
                    "preparing": "IN_PROGRESS",
                    "ready": "SERVED",
                    "completed": "COMPLETED",
                    "cancelled": "CANCELLED",
                }
                o.status = mapping.get(status, o.status)
                o.save(update_fields=["status", "updated_at"])
                ext.status = status
                ext.last_payload = data
                ext.save(update_fields=["status", "last_payload", "updated_at"])
                _log(provider, event, True, f"Updated order {o.id} -> {o.status}")
                return {"ok": True}
            except ExternalOrder.DoesNotExist:
                _log(provider, event, False, f"External order not found: {ext_id}")
                return {"ok": False, "detail": "unknown external id"}
    except Exception as e:
        _log(provider, event, False, f"Exception: {e}", data)
        return {"ok": False, "detail": "exception"}

