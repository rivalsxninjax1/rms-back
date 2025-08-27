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
# Keep the original import path ("loyalty.services") which is proxied to the new tip-based
# logic implemented in the `loyality` app. If the proxy isn’t present, the safe stubs apply.
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
    mi = MenuItem.objects.get(pk=mi_id)
    price = Decimal(str(getattr(mi, "price", 0)))
    return (mi.name, price)

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
        try:
            pid = int(pid); qty = int(qty)
        except Exception:
            continue
        if pid > 0 and qty > 0:
            out.append({"id": pid, "quantity": qty})
    return out

def _cart_get(request) -> List[Dict[str, Any]]:
    return list(request.session.get("cart", []))

def _cart_set(request, items: List[Dict[str, Any]]):
    request.session["cart"] = items
    request.session.modified = True

def _cart_meta_get(request) -> Dict[str, Any]:
    return dict(request.session.get("cart_meta", {}))

def _cart_meta_set(request, meta: Dict[str, Any]):
    request.session["cart_meta"] = meta
    request.session.modified = True

def _enrich(items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Decimal]:
    enriched: List[Dict[str, Any]] = []
    subtotal = Decimal("0")
    for it in items:
        pid = int(it["id"])
        qty = int(it.get("quantity", 1))
        name, unit = _fetch_menu_item(pid)
        line = unit * qty
        subtotal += line
        enriched.append({
            "id": pid,
            "name": name,
            "quantity": qty,
            "unit_price": str(unit),
            "line_total": str(line),
        })
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
class SessionCartViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def list(self, request):
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            order = (
                Order.objects.filter(created_by=user, status="PENDING", is_paid=False)
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
            return Response({"items": items, "subtotal": subtotal, "currency": _currency(), "meta": _cart_meta_get(request)})

        items = _normalize_items(_cart_get(request))
        enriched, subtotal = _enrich(items)
        meta = _cart_meta_get(request)
        return Response({"items": enriched, "subtotal": str(subtotal), "currency": _currency(), "meta": meta})

    def create(self, request):
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            with transaction.atomic():
                order = (
                    Order.objects.select_for_update()
                    .filter(created_by=user, status="PENDING", is_paid=False)
                    .prefetch_related("items__menu_item")
                    .first()
                )
                if not order:
                    order = Order.objects.create(created_by=user, status="PENDING", currency=_currency())
                items = _normalize_items(request.data.get("items", []))
                order.items.all().delete()
                for it in items:
                    pid = int(it["id"]); qty = int(it["quantity"])
                    _, unit = _fetch_menu_item(pid)
                    OrderItem.objects.create(order=order, menu_item_id=pid, quantity=qty, unit_price=unit)
                resp_items = []
                for it in order.items.all():
                    pid = it.menu_item_id; qty = int(it.quantity); name, unit = _fetch_menu_item(pid)
                    resp_items.append({
                        "id": pid, "name": name, "quantity": qty,
                        "unit_price": str(unit), "line_total": str((unit*qty).quantize(Decimal("0.01")))
                    })
                subtotal = str(sum(Decimal(i["unit_price"]) * i["quantity"] for i in resp_items) if resp_items else Decimal("0.00"))
                return Response({"status": "ok", "items": resp_items, "subtotal": subtotal, "currency": _currency()})

        items = _normalize_items(request.data.get("items", []))
        _cart_set(request, items)
        enriched, subtotal = _enrich(items)
        return Response({"status": "ok", "items": enriched, "subtotal": str(subtotal), "currency": _currency()})

    @action(methods=["post"], detail=False, url_path="items", permission_classes=[AllowAny])
    def add_item(self, request):
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            # ---- AUTH: support +/- deltas (including negative)
            pid = request.data.get("menu_item_id") or request.data.get("id")
            qty = request.data.get("quantity") or 1
            try:
                pid = int(pid); qty = int(qty)
            except Exception:
                return Response({"detail": "Invalid id/quantity."}, status=400)
            with transaction.atomic():
                order = (
                    Order.objects.select_for_update()
                    .filter(created_by=user, status="PENDING", is_paid=False)
                    .prefetch_related("items__menu_item")
                    .first()
                )
                if not order:
                    order = Order.objects.create(created_by=user, status="PENDING", currency=_currency())
                existing = {oi.menu_item_id: oi for oi in order.items.all()}
                _, unit = _fetch_menu_item(pid)
                if pid in existing:
                    oi = existing[pid]
                    oi.quantity = max(0, int(oi.quantity) + qty)
                    if oi.quantity == 0:
                        oi.delete()
                    else:
                        oi.unit_price = unit
                        oi.save(update_fields=["quantity", "unit_price"])
                else:
                    if qty > 0:
                        OrderItem.objects.create(order=order, menu_item_id=pid, quantity=qty, unit_price=unit)
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
            qty = int(request.data.get("quantity") or 1)
        except Exception:
            return Response({"detail": "Invalid id/quantity."}, status=400)
        if pid <= 0:
            return Response({"detail": "Invalid id."}, status=400)

        items = list(_cart_get(request))  # raw session items: [{"id":..,"quantity":..}, ...]
        # Coerce types and ensure structure
        norm_items: List[Dict[str, int]] = []
        for it in items:
            try:
                norm_items.append({"id": int(it.get("id")), "quantity": int(it.get("quantity", 0))})
            except Exception:
                continue

        found = False
        for it in norm_items:
            if it["id"] == pid:
                it["quantity"] = max(0, it["quantity"] + qty)
                found = True
                break

        if not found and qty > 0:
            norm_items.append({"id": pid, "quantity": qty})

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
                    .filter(created_by=user, status="PENDING", is_paid=False)
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
        for k in ("cart", "cart_meta", "applied_coupon"):
            request.session.pop(k, None)
        request.session.modified = True
        return Response({"status": "ok"})

    @action(methods=["post"], detail=False, url_path="merge", permission_classes=[IsAuthenticated])
    def merge(self, request):
        session_items = _normalize_items(_cart_get(request))
        if not session_items:
            return Response({"status": "noop", "detail": "empty session cart"})

        with transaction.atomic():
            order = (
                Order.objects.select_for_update()
                .filter(created_by=request.user, status="PENDING", is_paid=False)
                .order_by("-id").first()
            )
            if not order:
                order = Order.objects.create(created_by=request.user, status="PENDING", currency=_currency())

            existing = {oi.menu_item_id: oi for oi in order.items.select_related("menu_item")}
            for it in session_items:
                pid, qty = int(it["id"]), int(it["quantity"])
                _, unit = _fetch_menu_item(pid)
                if pid in existing:
                    oi = existing[pid]
                    oi.quantity = int(oi.quantity) + qty
                    oi.unit_price = unit
                    oi.save(update_fields=["quantity", "unit_price"])
                else:
                    OrderItem.objects.create(order=order, menu_item_id=pid, quantity=qty, unit_price=unit)

            _cart_set(request, [])

        return Response({"status": "ok", "order_id": order.id})


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
            if hasattr(Order, "created_by"):
                return qs.filter(created_by=user)
            if hasattr(Order, "user"):
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
                Order.objects.filter(created_by=user, status="PENDING", is_paid=False)
                .prefetch_related("items__menu_item").first()
            )
            if not order:
                order = Order(created_by=user, status="PENDING", currency=_currency())
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
