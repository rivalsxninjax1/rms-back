from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Tuple, Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
import json as _json
import hmac as _hmac
import hashlib as _hashlib
import logging as _logging

from .models import Order, OrderItem
from menu.models import MenuItem

# Optional imports (safe stubs if absent)
try:
    from payments.services import create_checkout_session, save_invoice_pdf_file
except Exception:  # pragma: no cover
    def create_checkout_session(order: Order):
        class _Dummy: url = None
        return _Dummy()
    def save_invoice_pdf_file(order: Order):  # noqa
        return None

try:
    from coupons.services import find_active_coupon, compute_discount_for_order  # type: ignore
except Exception:  # pragma: no cover
    def find_active_coupon(code: str): return None
    def compute_discount_for_order(order: Order, coupon, user):
        return False, Decimal("0.00"), "coupon service missing"

# NOTE:
# Use the canonical loyalty services. The loyalty app encapsulates the
# tip-based loyalty logic. If unavailable, fall back to safe stubs.
try:
    from loyalty.services import get_available_reward_for_user, reserve_reward_for_order  # type: ignore
except Exception:  # pragma: no cover
    def get_available_reward_for_user(user): return None
    def reserve_reward_for_order(reward, order: Order): return None

# Reservations.Table for dine-in mapping (optional)
try:
    from reservations.models import Table as RMSTable
except Exception:  # pragma: no cover
    RMSTable = None


# ---------- Helpers ----------
def _currency() -> str:
    return getattr(settings, "STRIPE_CURRENCY", "usd").lower()

def _fetch_menu_item(mi_id: int) -> Tuple[str, Decimal]:
    try:
        mi = MenuItem.objects.get(pk=mi_id)
        price = Decimal(str(getattr(mi, "price", 0)))
        return (mi.name, price)
    except MenuItem.DoesNotExist:
        raise ValueError(f"Menu item with ID {mi_id} does not exist")

def _normalize_items(items_in: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalizes a list of items ensuring id>0 and quantity>0.
    NOTE: This intentionally drops non-positive quantities and is NOT used
    for delta updates (e.g., -1). Guest decrement path parses manually.
    """
    out: List[Dict[str, Any]] = []
    for raw in items_in or []:
        pid = raw.get("menu_item_id") or raw.get("menu_item") or raw.get("product") or raw.get("id")
        qty = raw.get("quantity") or raw.get("qty") or 1
        modifiers = raw.get("modifiers", [])
        try:
            pid = int(pid); qty = int(qty)
        except Exception:
            continue
        if pid > 0 and qty > 0:
            item = {"id": pid, "quantity": qty}
            if modifiers and isinstance(modifiers, list):
                item["modifiers"] = modifiers
            out.append(item)
    return out

def _cart_get(request) -> List[Dict[str, Any]]:
    from .session_utils import SessionCartManager
    manager = SessionCartManager(request)
    return manager.get_cart_items()

def _cart_set(request, items: List[Dict[str, Any]]):
    from .session_utils import SessionCartManager
    manager = SessionCartManager(request)
    manager.set_cart_data(items)

def _cart_meta_get(request) -> Dict[str, Any]:
    from .session_utils import SessionCartManager
    manager = SessionCartManager(request)
    return manager.get_cart_meta()

def _cart_meta_set(request, meta: Dict[str, Any]):
    from .session_utils import SessionCartManager
    manager = SessionCartManager(request)
    manager.set_cart_meta(meta)

def _enrich(items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Decimal]:
    from .cache_utils import get_menu_items_batch_cached, get_modifiers_batch_cached
    
    if not items:
        return [], Decimal("0")
    
    # Collect all menu item and modifier IDs
    menu_item_ids = [int(it["id"]) for it in items]
    all_modifier_ids = set()
    for it in items:
        modifiers = it.get("modifiers", [])
        for mod in modifiers:
            if mod.get("id"):
                all_modifier_ids.add(int(mod["id"]))
    
    # Batch fetch from cache/database
    menu_items_cache = get_menu_items_batch_cached(menu_item_ids)
    modifier_cache = get_modifiers_batch_cached(list(all_modifier_ids))
    
    enriched: List[Dict[str, Any]] = []
    subtotal = Decimal("0")
    
    for it in items:
        pid = int(it["id"])
        qty = int(it.get("quantity", 0))
        modifiers = it.get("modifiers", [])
        
        # Use cached menu item data
        menu_item_data = menu_items_cache.get(pid)
        if not menu_item_data:
            continue  # Skip invalid items
            
        name, unit, image_url = menu_item_data
        
        # Calculate modifier price using cached data
        modifier_price = Decimal("0.00")
        modifier_names = []
        for mod_data in modifiers:
            mod_id = mod_data.get("id")
            if mod_id:
                mod_id = int(mod_id)
                if mod_id in modifier_cache:
                    mod_name, mod_price = modifier_cache[mod_id]
                    modifier_price += mod_price
                    modifier_names.append(mod_name)
        
        item_unit_price = unit + modifier_price
        line = item_unit_price * qty
        subtotal += line
        
        enriched_item = {
            "id": pid,
            "name": name,
            "quantity": qty,
            "unit_price": str(unit),
            "modifier_price": str(modifier_price),
            "total_unit_price": str(item_unit_price),
            "line_total": str(line),
        }
        
        if image_url:
            enriched_item["image"] = image_url
        
        if modifiers:
            enriched_item["modifiers"] = modifiers
            enriched_item["modifier_names"] = modifier_names
            
        enriched.append(enriched_item)
    return enriched, subtotal

# Align by explicit RMS Table id (preferred), else by number
def _align_table_by_id(order: Order, table_id: int) -> bool:
    if not RMSTable or not table_id:
        return False
    try:
        tbl = RMSTable.objects.select_related("location").get(id=table_id, is_active=True)
    except Exception:
        return False
    # Set number if numeric
    try:
        order.table_number = int(getattr(tbl, "table_number", "") or 0) or None
    except Exception:
        pass
    order.external_order_id = f"TBL:{tbl.id}"
    label_loc = getattr(tbl.location, "name", getattr(tbl.location, "title", ""))
    label = f"{label_loc} — Table {getattr(tbl, 'table_number', '')}".strip(" —")
    if not getattr(order, "notes", ""):
        order.notes = label
    return True

def _align_table_by_number(order: Order, table_number_input: Optional[int]) -> None:
    if not table_number_input:
        return
    try:
        tn = str(int(table_number_input))
    except Exception:
        return
    if RMSTable is None:
        order.table_number = int(tn)
        return
    tbl = RMSTable.objects.filter(table_number=tn, is_active=True).select_related("location").first()
    order.table_number = int(tn)
    if not tbl:
        return
    order.external_order_id = f"TBL:{tbl.id}"
    label_loc = getattr(tbl.location, "name", getattr(tbl.location, "title", ""))
    label = f"{label_loc} — Table {tbl.table_number}".strip(" —")
    if not getattr(order, "notes", ""):
        order.notes = label


# ---------- Session cart endpoints (guest) and DB cart (auth) ----------
@method_decorator(csrf_exempt, name='dispatch')
class SessionCartViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get_permissions(self):
        """Override to ensure AllowAny for all actions"""
        return [AllowAny()]

    def list(self, request):
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            from menu.models import MenuItem
            order = (
                Order.objects.filter(user=user, status="PENDING")
                .prefetch_related("items__menu_item")
                .first()
            )
            items = []
            if order:
                for it in order.items.all():
                    pid = getattr(it, "menu_item_id", None)
                    qty = int(getattr(it, "quantity", 0))
                    name, unit = _fetch_menu_item(pid)
                    
                    # Get menu item image
                    image_url = None
                    try:
                        menu_item = MenuItem.objects.get(id=pid)
                        if menu_item.image:
                            image_url = menu_item.image.url
                    except MenuItem.DoesNotExist:
                        pass
                    
                    item_data = {
                        "id": pid,
                        "name": name,
                        "quantity": qty,
                        "unit_price": str(unit),
                        "line_total": str((unit * qty).quantize(Decimal("0.01"))),
                    }
                    
                    if image_url:
                        item_data["image"] = image_url
                    
                    items.append(item_data)
            subtotal = sum(Decimal(i["unit_price"]) * i["quantity"] for i in items) if items else Decimal("0.00")
            
            # Get tip amount from session
            tip_amount = Decimal(str(request.session.get("cart_tip_amount", 0)))
            
            # Calculate grand total
            grand_total = subtotal + tip_amount
            
            return Response({
                "items": items, 
                "subtotal": str(subtotal), 
                "tip_amount": str(tip_amount),
                "grand_total": str(grand_total),
                "currency": _currency(), 
                "meta": _cart_meta_get(request)
            })

        items = _normalize_items(_cart_get(request))
        enriched, subtotal = _enrich(items)
        meta = _cart_meta_get(request)
        
        # Get tip amount from session
        tip_amount = Decimal(str(request.session.get("cart_tip_amount", 0)))
        
        # Calculate grand total
        grand_total = subtotal + tip_amount
        
        return Response({
            "items": enriched, 
            "subtotal": str(subtotal), 
            "tip_amount": str(tip_amount),
            "grand_total": str(grand_total),
            "currency": _currency(), 
            "meta": meta
        })

    def create(self, request):
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            with transaction.atomic():
                order = (
                    Order.objects.select_for_update()
                    .filter(user=user, status="PENDING")
                    .prefetch_related("items__menu_item")
                    .first()
                )
                if not order:
                    order = Order.objects.create(user=user, status="PENDING", currency=_currency())
                items = _normalize_items(request.data.get("items", []))
                order.items.all().delete()
                for it in items:
                    pid = int(it["id"]); qty = int(it["quantity"])
                    modifiers = it.get("modifiers", [])
                    _, unit = _fetch_menu_item(pid)
                    OrderItem.objects.create(order=order, menu_item_id=pid, quantity=qty, unit_price=unit, modifiers=modifiers)
                resp_items = []
                for it in order.items.all():
                    pid = it.menu_item_id; qty = int(it.quantity); name, unit = _fetch_menu_item(pid)
                    resp_items.append({
                        "id": pid, "name": name, "quantity": qty,
                        "unit_price": str(unit), "line_total": str((unit*qty).quantize(Decimal("0.01")))
                    })
                subtotal = sum(Decimal(i["unit_price"]) * i["quantity"] for i in resp_items) if resp_items else Decimal("0.00")
                
                # Get tip amount from session
                tip_amount = Decimal(str(request.session.get("cart_tip_amount", 0)))
                
                # Calculate grand total
                grand_total = subtotal + tip_amount
                
                return Response({
                    "status": "ok", 
                    "items": resp_items, 
                    "subtotal": str(subtotal),
                    "tip_amount": str(tip_amount),
                    "grand_total": str(grand_total),
                    "currency": _currency()
                })

        items = _normalize_items(request.data.get("items", []))
        _cart_set(request, items)
        enriched, subtotal = _enrich(items)
        
        # Get tip amount from session
        tip_amount = Decimal(str(request.session.get("cart_tip_amount", 0)))
        
        # Calculate grand total
        grand_total = subtotal + tip_amount
        
        return Response({
            "status": "ok", 
            "items": enriched, 
            "subtotal": str(subtotal),
            "tip_amount": str(tip_amount),
            "grand_total": str(grand_total),
            "currency": _currency()
        })

    @action(methods=["post"], detail=False, url_path="items", permission_classes=[AllowAny])
    def add_item(self, request):
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            # ---- AUTH: support +/- deltas (including negative)
            pid = request.data.get("menu_item_id") or request.data.get("id")
            qty = request.data.get("quantity") or 1
            modifiers = request.data.get("modifiers", [])
            try:
                pid = int(pid); qty = int(qty)
            except Exception:
                return Response({"detail": "Invalid id/quantity."}, status=400)
            
            # Validate menu item exists
            try:
                _, unit = _fetch_menu_item(pid)
            except ValueError:
                return Response({"detail": "Menu item not found."}, status=400)
                
            with transaction.atomic():
                order = (
                    Order.objects.select_for_update()
                    .filter(user=user, status="PENDING")
                    .prefetch_related("items__menu_item")
                    .first()
                )
                if not order:
                    order = Order.objects.create(user=user, status="PENDING", currency=_currency())
                existing = {oi.menu_item_id: oi for oi in order.items.all()}
                if pid in existing:
                    oi = existing[pid]
                    oi.quantity = max(0, qty)  # Set quantity instead of adding
                    if oi.quantity == 0:
                        oi.delete()
                    else:
                        oi.unit_price = unit
                        if modifiers:
                            oi.modifiers = modifiers
                        oi.save(update_fields=["quantity", "unit_price", "modifiers"])
                else:
                    if qty > 0:
                        OrderItem.objects.create(order=order, menu_item_id=pid, quantity=qty, unit_price=unit, modifiers=modifiers)
                items = []
                for it in order.items.all():
                    p = it.menu_item_id; q = int(it.quantity); name, u = _fetch_menu_item(p)
                    items.append({"id": p, "name": name, "quantity": q, "unit_price": str(u), "line_total": str((u*q).quantize(Decimal("0.01")))})
                subtotal = str(sum(Decimal(i["unit_price"]) * i["quantity"] for i in items))
                return Response({"items": items, "subtotal": subtotal, "currency": _currency()})

        # ---- GUEST/SESSION: accept negative deltas properly (FIX)
        # Parse payload directly (do NOT use _normalize_items which drops <=0)
        try:
            pid = int(request.data.get("menu_item_id") or request.data.get("id") or 0)
            qty = int(request.data.get("quantity", 1))
            modifiers = request.data.get("modifiers", [])
        except Exception:
            return Response({"detail": "Invalid id/quantity."}, status=400)
        if pid <= 0:
            return Response({"detail": "Invalid id."}, status=400)
            
        # Validate menu item exists
        try:
            _fetch_menu_item(pid)
        except ValueError:
            return Response({"detail": "Menu item not found."}, status=400)

        items = list(_cart_get(request))  # raw session items: [{"id":..,"quantity":..}, ...]
        # Coerce types and ensure structure
        norm_items: List[Dict[str, Any]] = []
        for it in items:
            try:
                item_dict = {"id": int(it.get("id")), "quantity": int(it.get("quantity", 0))}
                if "modifiers" in it:
                    item_dict["modifiers"] = it["modifiers"]
                norm_items.append(item_dict)
            except Exception:
                continue

        found = False
        for it in norm_items:
            if it["id"] == pid:
                it["quantity"] = max(0, qty)  # Set quantity instead of adding
                if modifiers:
                    it["modifiers"] = modifiers
                found = True
                break

        if not found and qty > 0:
            new_item = {"id": pid, "quantity": qty}
            if modifiers:
                new_item["modifiers"] = modifiers
            norm_items.append(new_item)

        # Drop zeros
        norm_items = [it for it in norm_items if it["quantity"] > 0]
        
        _cart_set(request, norm_items)

        enriched, subtotal = _enrich(norm_items)
        return Response({"items": enriched, "subtotal": str(subtotal), "currency": _currency()})

    @action(methods=["post"], detail=False, url_path="items/remove", permission_classes=[AllowAny])
    def remove_item(self, request):
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            pid = request.data.get("menu_item_id") or request.data.get("id")
            try:
                pid = int(pid)
            except Exception:
                return Response({"detail": "Invalid id."}, status=400)
            with transaction.atomic():
                order = (
                Order.objects.select_for_update()
                .filter(user=user, status="PENDING")
                .prefetch_related("items__menu_item")
                .first()
            )
                if order:
                    order.items.filter(menu_item_id=pid).delete()
                items = []
                if order:
                    for it in order.items.all():
                        p = it.menu_item_id; q = int(it.quantity); name, u = _fetch_menu_item(p)
                        items.append({"id": p, "name": name, "quantity": q, "unit_price": str(u), "line_total": str((u*q).quantize(Decimal("0.01")))})
                subtotal = str(sum(Decimal(i["unit_price"]) * i["quantity"] for i in items) if items else Decimal("0.00"))
                return Response({"items": items, "subtotal": subtotal, "currency": _currency()})

        pid = request.data.get("menu_item_id") or request.data.get("id")
        try:
            pid = int(pid)
        except Exception:
            pid = 0
        items = [it for it in _normalize_items(_cart_get(request)) if it["id"] != pid]
        _cart_set(request, items)
        enriched, subtotal = _enrich(items)
        return Response({"items": enriched, "subtotal": str(subtotal), "currency": _currency()})

    @action(methods=["post"], detail=False, url_path="meta", permission_classes=[AllowAny])
    def set_meta(self, request):
        allowed = {"DINE_IN", "UBER_EATS", "DOORDASH"}
        meta = _cart_meta_get(request)
        st = str(request.data.get("service_type", "")).upper().strip()
        if st == "UBEREATS":
            st = "UBER_EATS"
        if st and st in allowed:
            meta["service_type"] = st
        table = request.data.get("table_number") or request.data.get("table_num")
        if table:
            try:
                meta["table_number"] = int(table)
            except Exception:
                pass
        _cart_meta_set(request, meta)
        return Response({"status": "ok", "meta": meta})

    @action(methods=["post"], detail=False, url_path="reset_session", permission_classes=[AllowAny])
    def reset_session(self, request):
        """Clear all cart-related session data using the new session management utility."""
        try:
            from .session_utils import get_session_cart_manager
            
            # Use the new session cart manager
            cart_manager = get_session_cart_manager(request)
            
            # Ensure session exists
            if not cart_manager.ensure_session_exists():
                return Response({
                    "status": "error",
                    "message": "Session initialization failed"
                }, status=500)
            
            # Clear cart using the session manager
            success = cart_manager.clear_cart(reinitialize=True)
            
            if not success:
                return Response({
                    "status": "error",
                    "message": "Failed to reset session cart"
                }, status=500)
            
            return Response({
                "status": "ok", 
                "message": "Cart cleared successfully",
                "timestamp": timezone.now().isoformat()
            })
            
        except Exception as e:
            return Response({
                "status": "error",
                "message": "Failed to reset session cart"
            }, status=500)

    @action(methods=["post"], detail=False, url_path="merge", permission_classes=[IsAuthenticated])
    def merge(self, request):
        session_items = _normalize_items(_cart_get(request))
        if not session_items:
            return Response({"status": "noop", "detail": "empty session cart"})

        with transaction.atomic():
            order = (
                Order.objects.select_for_update()
                .filter(user=request.user, status="PENDING")
                .order_by("-id").first()
            )
            if not order:
                order = Order.objects.create(user=request.user, status="PENDING", currency=_currency())

            # Get all existing order items
            existing_items = list(order.items.select_related("menu_item"))
            
            for it in session_items:
                pid, qty = int(it["id"]), int(it["quantity"])
                modifiers = it.get("modifiers", [])
                _, unit = _fetch_menu_item(pid)
                
                # Look for exact match (same menu item + same modifiers)
                matching_item = None
                for oi in existing_items:
                    if (oi.menu_item_id == pid and 
                        self._modifiers_match(oi.modifiers or [], modifiers)):
                        matching_item = oi
                        break
                
                if matching_item:
                    # Sum quantities for exact matches
                    matching_item.quantity = int(matching_item.quantity) + qty
                    matching_item.unit_price = unit
                    matching_item.save(update_fields=["quantity", "unit_price"])
                else:
                    # Create new item for different modifier combinations
                    new_item = OrderItem.objects.create(
                        order=order, 
                        menu_item_id=pid, 
                        quantity=qty, 
                        unit_price=unit, 
                        modifiers=modifiers
                    )
                    existing_items.append(new_item)

            _cart_set(request, [])

        return Response({"status": "ok", "order_id": order.id})
    
    def _modifiers_match(self, modifiers1, modifiers2):
        """Check if two modifier lists are equivalent."""
        # Normalize both lists - sort by modifier ID for comparison
        def normalize_modifiers(mods):
            if not mods:
                return []
            # Sort by modifier ID to ensure consistent comparison
            return sorted(mods, key=lambda x: x.get('id', 0) if isinstance(x, dict) else str(x))
        
        norm1 = normalize_modifiers(modifiers1)
        norm2 = normalize_modifiers(modifiers2)
        
        return norm1 == norm2

    @action(methods=["get"], detail=False, url_path="modifiers", permission_classes=[AllowAny])
    def get_modifiers(self, request):
        """Get available modifiers/extras for cart items."""
        from menu.models import ModifierGroup, Modifier
        
        # Get cart items to find relevant modifiers
        user = getattr(request, "user", None)
        menu_item_ids = []
        
        if user and getattr(user, "is_authenticated", False):
            order = (
                Order.objects.filter(user=user, status="PENDING")
                .prefetch_related("items__menu_item")
                .first()
            )
            if order:
                menu_item_ids = [item.menu_item_id for item in order.items.all()]
        else:
            items = _normalize_items(_cart_get(request))
            menu_item_ids = [int(item["id"]) for item in items]
        
        # Get modifier groups for these menu items
        modifier_groups = ModifierGroup.objects.filter(
            menu_item_id__in=menu_item_ids
        ).prefetch_related('modifiers').order_by('sort_order')
        
        result = []
        for group in modifier_groups:
            modifiers = []
            for modifier in group.modifiers.filter(is_available=True).order_by('sort_order'):
                modifiers.append({
                    "id": modifier.id,
                    "name": modifier.name,
                    "price": str(modifier.price),
                })
            
            if modifiers:  # Only include groups that have available modifiers
                result.append({
                    "id": group.id,
                    "name": group.name,
                    "menu_item_id": group.menu_item_id,
                    "is_required": group.is_required,
                    "min_select": group.min_select,
                    "max_select": group.max_select,
                    "modifiers": modifiers,
                })
        
        return Response({"modifier_groups": result})

    @action(methods=["get"], detail=False, url_path="cart-expiration", permission_classes=[AllowAny])
    def cart_expiration(self, request):
        """Check if cart has expired and return expiration info."""
        from django.utils import timezone
        from datetime import timedelta
        
        # Cart expires after 30 minutes of inactivity
        CART_EXPIRATION_MINUTES = 30
        
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            # For authenticated users, check DB cart (pending order)
            order = (
                Order.objects.filter(user=user, status="PENDING")
                .first()
            )
            if not order:
                return Response({"expired": True, "has_items": False})
            
            # Check if order was updated recently
            expiration_time = order.updated_at + timedelta(minutes=CART_EXPIRATION_MINUTES)
            is_expired = timezone.now() > expiration_time
            has_items = order.items.exists()
            
            return Response({
                "expired": is_expired,
                "has_items": has_items,
                "expiration_time": expiration_time.isoformat(),
                "minutes_remaining": max(0, int((expiration_time - timezone.now()).total_seconds() / 60))
            })
        else:
            # For session carts, check session timestamp
            cart_items = _cart_get(request)
            has_items = len(cart_items) > 0
            
            # Get last cart modification time from session
            last_modified = request.session.get("cart_last_modified")
            if not last_modified:
                # If no timestamp, consider it expired if it has items
                return Response({"expired": has_items, "has_items": has_items})
            
            try:
                from datetime import datetime
                last_modified_dt = datetime.fromisoformat(last_modified.replace('Z', '+00:00'))
                expiration_time = last_modified_dt + timedelta(minutes=CART_EXPIRATION_MINUTES)
                is_expired = timezone.now() > expiration_time
                
                return Response({
                    "expired": is_expired,
                    "has_items": has_items,
                    "expiration_time": expiration_time.isoformat(),
                    "minutes_remaining": max(0, int((expiration_time - timezone.now()).total_seconds() / 60))
                })
            except Exception:
                # If timestamp parsing fails, consider expired
                return Response({"expired": True, "has_items": has_items})


# ---------- Orders / Checkout ----------
class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all().order_by("-id")

    def get_permissions(self):
        if self.action in ("list", "retrieve", "create", "update", "partial_update", "destroy"):
            return [IsAuthenticated()]
        return [AllowAny()]

    try:
        from .serializers import OrderReadSerializer  # type: ignore
        read_serializer = OrderReadSerializer
    except Exception:
        read_serializer = None

    def get_queryset(self):
        qs = super().get_queryset()
        user = getattr(self.request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            return qs.filter(user=user)
        return qs.none()

    def list(self, request, *args, **kwargs):
        if self.read_serializer:
            ser = self.read_serializer(self.get_queryset(), many=True)
            return Response(ser.data)
        data = []
        for o in self.get_queryset():
            items = []
            for it in o.items.all():
                line_total = (Decimal(str(it.unit_price)) * int(it.quantity)).quantize(Decimal("0.01"))
                items.append({
                    "menu_item": getattr(it, "menu_item_id", None),
                    "quantity": it.quantity,
                    "unit_price": str(it.unit_price),
                    "line_total": str(line_total),
                })
            total = o.grand_total()
            data.append({
                "id": o.id,
                "status": o.status,
                "is_paid": o.is_paid,
                "source": o.source,
                "table_number": o.table_number,
                "external_order_id": o.external_order_id,
                "tip_amount": str(o.tip_amount),
                "discount_amount": str(o.discount_amount),
                "discount_code": o.discount_code,
                "items": items,
                "total": str(total),
                "created_at": timezone.localtime(getattr(o, "created_at", timezone.now())),
            })
        return Response(data)

    def create(self, request, *args, **kwargs):
        """
        Build an Order for checkout (DB cart only):
          - Auth required
          - Optional: service_type, table_id (preferred), table_number (fallback), coupon_code
          - Returns Stripe checkout_url
        """
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return Response({"detail": "Authentication required for checkout."}, status=401)

        body_source_raw = (request.data.get("service_type") or request.data.get("source") or "").upper().strip()
        if body_source_raw == "UBEREATS":
            body_source_raw = "UBER_EATS"
        source = body_source_raw if body_source_raw in {"DINE_IN", "UBER_EATS", "DOORDASH"} else "DINE_IN"

        # accept table_id from cart select; fallback to table_number
        table_id = request.data.get("table_id")
        try:
            table_id = int(table_id) if table_id not in (None, "",) else None
        except Exception:
            table_id = None

        table_number = request.data.get("table_number") or request.data.get("table_num")

        tip_percent = request.data.get("tip_percent")
        tip_amount_custom = request.data.get("tip_amount") or request.data.get("tip_custom")
        coupon_code = (request.data.get("coupon") or request.data.get("coupon_code") or "").strip()

        with transaction.atomic():
            order = (
                Order.objects.filter(user=user, status="PENDING")
                .prefetch_related("items__menu_item").first()
            )
            if not order:
                order = Order(user=user, status="PENDING", currency=_currency())
                order.save()

            if not order.items.exists():
                return Response({"detail": "Your cart is empty. Please add items before checkout."}, status=400)

            # Source + Table alignment (id first, else number)
            order.source = source
            aligned = False
            if source == "DINE_IN" and table_id:
                aligned = _align_table_by_id(order, table_id)
            if source == "DINE_IN" and not aligned and table_number:
                try:
                    tn = int(table_number)
                except Exception:
                    tn = None
                _align_table_by_number(order, tn)

            # Tip
            tip_dec = Decimal("0.00")
            if tip_amount_custom:
                try:
                    tip_dec = Decimal(str(tip_amount_custom))
                except Exception:
                    tip_dec = Decimal("0.00")
            elif tip_percent:
                try:
                    pct = Decimal(str(tip_percent)) / Decimal("100")
                    tip_dec = (order.subtotal * pct).quantize(Decimal("0.01"))
                except Exception:
                    tip_dec = Decimal("0.00")
            order.tip_amount = tip_dec

            # Coupon (compute but do not yet apply; we will pick best-of)
            coupon_discount = Decimal("0.00")
            coupon_code_used = ""
            if coupon_code:
                c = find_active_coupon(coupon_code)
                ok, disc, _reason = compute_discount_for_order(order, c, user)
                if ok:
                    coupon_discount = disc
                    coupon_code_used = c.code

            # Loyalty (TIP-based; FIXED amount) — proxied via loyalty.services
            reward = get_available_reward_for_user(user)
            loyalty_discount = reward.as_discount_amount(order.subtotal) if reward else Decimal("0.00")

            # BEST-OF: choose the greater absolute discount (no stacking; tips excluded from min spend upstream)
            if loyalty_discount >= coupon_discount and loyalty_discount > 0:
                order.discount_amount = loyalty_discount
                order.discount_code = "LOYALTY"
                # keep compatibility no-op
                if reward:
                    reserve_reward_for_order(reward, order)
            elif coupon_discount > 0:
                order.discount_amount = coupon_discount
                order.discount_code = coupon_code_used
            else:
                order.discount_amount = Decimal("0.00")
                order.discount_code = ""

            order.full_clean()
            order.save()

            # Optional invoice placeholder
            try:
                save_invoice_pdf_file(order)
            except Exception:
                pass

            # Stripe Checkout
            session = create_checkout_session(order)
            checkout_url = getattr(session, "url", None) if session else None

            return Response(
                {
                    "id": order.id,
                    "checkout_url": checkout_url,
                    "total": str(order.grand_total()),
                    "currency": _currency(),
                    "source": order.source,
                    "table_number": getattr(order, "table_number", None),
                },
                status=201,
            )


# Simple function-based view for cart to bypass DRF issues
@csrf_exempt
@require_http_methods(["GET"])
def simple_cart_view(request):
    """Simple cart view using session management utility to bypass DRF permission issues"""
    try:
        from .session_utils import get_session_cart_manager
        
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            order = (
                Order.objects.filter(user=user, status="PENDING")
                .prefetch_related("items__menu_item")
                .first()
            )
            items = []
            if order:
                for it in order.items.all():
                    pid = getattr(it, "menu_item_id", None)
                    qty = int(getattr(it, "quantity", 0))
                    name, unit = _fetch_menu_item(pid)
                    items.append({
                        "id": pid,
                        "name": name,
                        "quantity": qty,
                        "unit_price": str(unit),
                        "line_total": str((unit * qty).quantize(Decimal("0.01"))),
                    })
            subtotal = str(sum(Decimal(i["unit_price"]) * i["quantity"] for i in items) if items else Decimal("0.00"))
            return JsonResponse({"items": items, "subtotal": subtotal, "currency": _currency(), "meta": _cart_meta_get(request)})

        # Use session cart manager for guest users
        cart_manager = get_session_cart_manager(request)
        
        # Debug logging
        print(f"DEBUG: Session key: {request.session.session_key}")
        print(f"DEBUG: Cart items from manager: {cart_manager.get_cart_items()}")
        print(f"DEBUG: Raw session data: {dict(request.session)}")
        
        items = _normalize_items(cart_manager.get_cart_items())
        enriched, subtotal = _enrich(items)
        meta = cart_manager.get_cart_meta()
        return JsonResponse({"items": enriched, "subtotal": str(subtotal), "currency": _currency(), "meta": meta})
    except Exception as e:
        return JsonResponse({"error": str(e), "items": [], "subtotal": "0.00", "currency": _currency(), "meta": {}}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def cart_expiration_view(request):
    """Check if cart has expired and return expiration info using session management utility."""
    try:
        from .session_utils import get_session_cart_manager
        
        # Use the new session cart manager
        cart_manager = get_session_cart_manager(request)
        
        # Check if middleware set the expiration flag
        cart_expired = request.session.pop('cart_expired', False)
        
        # Get current cart status
        user = getattr(request, "user", None)
        has_items = False
        
        if user and getattr(user, "is_authenticated", False):
            # For authenticated users, check DB cart
            order = (
                Order.objects.filter(user=user, status="PENDING")
                .first()
            )
            has_items = order and order.items.exists()
        else:
            # For session carts, use session manager
            cart_items = cart_manager.get_cart_items()
            has_items = len(cart_items) > 0
        
        return JsonResponse({
            "expired": cart_expired,
            "has_items": has_items
        })
    except Exception as e:
        return JsonResponse({"error": str(e), "expired": False, "has_items": False}, status=500)


# ----------------------------
# Delivery provider webhooks
# ----------------------------

def _verify_hmac_signature(secret: str, header_signature: str, payload: bytes) -> bool:
    try:
        digest = _hmac.new((secret or "").encode("utf-8"), payload, _hashlib.sha256).hexdigest()
        # header_signature may be raw hex or prefixed; be tolerant
        sig = (header_signature or "").strip()
        if sig.startswith("sha256="):
            sig = sig.split("=", 1)[1]
        return _hmac.compare_digest(digest, sig)
    except Exception:
        return False


@csrf_exempt
@require_http_methods(["POST"])
def ubereats_webhook(request):
    """Webhook endpoint for Uber Eats events.
    Uses optional HMAC verification if UBEREATS_WEBHOOK_SECRET is set.
    """
    raw = request.body or b""
    try:
        event = _json.loads(raw.decode("utf-8"))
    except Exception:
        return HttpResponse("Invalid JSON", status=400)

    secret = getattr(settings, "UBEREATS_WEBHOOK_SECRET", "")
    ok = True
    if secret:
        sig_hdr = request.META.get("HTTP_X_UBER_SIGNATURE", "") or request.META.get("HTTP_X_UBEREATS_SIGNATURE", "")
        ok = _verify_hmac_signature(secret, sig_hdr, raw)
    if not ok:
        return HttpResponse("Invalid signature", status=400)

    try:
        from .services.uber_eats import UberEatsService
        svc = UberEatsService()
        svc.webhook_handler(event)
    except Exception as e:
        _logging.getLogger(__name__).exception("UberEats webhook processing failed: %s", e)
        return HttpResponse("Failed", status=500)
    return HttpResponse("OK", status=200)


@csrf_exempt
@require_http_methods(["POST"])
def doordash_webhook(request):
    """Webhook endpoint for DoorDash Drive events.
    Uses optional HMAC verification if DOORDASH_WEBHOOK_SECRET or DOORDASH_SIGNING_SECRET is set.
    """
    raw = request.body or b""
    try:
        event = _json.loads(raw.decode("utf-8"))
    except Exception:
        return HttpResponse("Invalid JSON", status=400)

    secret = getattr(settings, "DOORDASH_WEBHOOK_SECRET", "") or getattr(settings, "DOORDASH_SIGNING_SECRET", "")
    ok = True
    if secret:
        sig_hdr = request.META.get("HTTP_X_DOORDASH_SIGNATURE", "") or request.META.get("HTTP_X_DD_SIGNATURE", "")
        ok = _verify_hmac_signature(secret, sig_hdr, raw)
    if not ok:
        return HttpResponse("Invalid signature", status=400)

    try:
        from .services.doordash import DoorDashService
        svc = DoorDashService()
        svc.webhook_handler(event)
    except Exception as e:
        _logging.getLogger(__name__).exception("DoorDash webhook processing failed: %s", e)
        return HttpResponse("Failed", status=500)
    return HttpResponse("OK", status=200)
