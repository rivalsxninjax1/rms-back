from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional, Type

from django.contrib import admin
from django.db import models
from django.db.models import Q, Sum
from django.shortcuts import render
from django.urls import path

# ---- Imports of your existing engagement models (kept intact if present) ----
try:
    from .models import OrderExtras  # type: ignore
except Exception:  # pragma: no cover
    OrderExtras = None  # type: ignore

try:
    from .models import TipLedger  # type: ignore
except Exception:  # pragma: no cover
    TipLedger = None  # type: ignore

try:
    from .models import ReservationHold  # type: ignore
except Exception:  # pragma: no cover
    ReservationHold = None  # type: ignore

try:
    from .models import PendingTip  # type: ignore
except Exception:  # pragma: no cover
    PendingTip = None  # type: ignore

# IMPORTANT: LoyaltyTier may be provided by a compat alias that points to the
# loyalty app (we keep your original import and add a safe fallback).
try:
    from .compat import LoyaltyTier  # aliased to a loyalty model when present
except Exception:  # pragma: no cover
    LoyaltyTier = None  # type: ignore
    try:
        from loyality.models import LoyaltyRank as _LoyaltyTier  # type: ignore
        LoyaltyTier = _LoyaltyTier
    except Exception:
        LoyaltyTier = None  # type: ignore


# ---------------------------------------------------------------------------
# Safe registration helpers (prevents TypeError: 'type' object is not iterable)
# ---------------------------------------------------------------------------

def _is_model(klass: object) -> bool:
    try:
        return isinstance(klass, type) and issubclass(klass, models.Model)
    except Exception:
        return False


def _register_model_if_needed(model_cls: Optional[Type[models.Model]], admin_cls: Optional[Type[admin.ModelAdmin]]):
    """
    Register only if model_cls is a Django model and not already registered.
    This guards against passing incompatible objects to admin.site.register.
    """
    if not _is_model(model_cls):
        return
    try:
        # Django >= 4.2
        if hasattr(admin.site, "is_registered") and admin.site.is_registered(model_cls):  # type: ignore[attr-defined]
            return
    except Exception:
        # For older versions, fall through and rely on AlreadyRegistered
        pass
    try:
        if admin_cls is None:
            class _Stub(admin.ModelAdmin):
                list_display = ("id",)
            admin.site.register(model_cls, _Stub)
        else:
            admin.site.register(model_cls, admin_cls)
    except admin.sites.AlreadyRegistered:
        return


# ---- Admins (guarded) ----

if OrderExtras is not None:
    class OrderExtrasAdmin(admin.ModelAdmin):
        list_display = ("id", "order", "name", "amount", "created_at")
        search_fields = ("order__id", "name")
        list_filter = ("name", "created_at")
        readonly_fields = ()
    _register_model_if_needed(OrderExtras, OrderExtrasAdmin)

if TipLedger is not None:
    class TipLedgerAdmin(admin.ModelAdmin):
        list_display = ("id", "user", "order", "amount", "created_at")
        search_fields = ("user__username", "user__email", "order__id")
        list_filter = ("created_at",)
        readonly_fields = ()
    _register_model_if_needed(TipLedger, TipLedgerAdmin)

if ReservationHold is not None:
    class ReservationHoldAdmin(admin.ModelAdmin):
        list_display = ("id", "table", "status", "expires_at", "created_at")
        search_fields = ("table__table_number", "table__id")
        list_filter = ("status", "expires_at")
        readonly_fields = ()
    _register_model_if_needed(ReservationHold, ReservationHoldAdmin)

if PendingTip is not None:
    class PendingTipAdmin(admin.ModelAdmin):
        list_display = ("id", "user", "amount", "created_at")
        search_fields = ("user__username", "user__email")
        list_filter = ("created_at",)
        readonly_fields = ()
    _register_model_if_needed(PendingTip, PendingTipAdmin)


# ---- Loyalty config + Top Tippers report (guarded for both model shapes) ----
if LoyaltyTier is not None:
    class LoyaltyTierAdmin(admin.ModelAdmin):
        """
        Works with either:
          - engagement.compat.LoyaltyTier (your project-specific fields), or
          - loyality.LoyaltyRank (fallback; fields code/name/tip_cents/is_active/sort_order)
        We only reference fields if they exist on the model to avoid runtime errors.
        """
        # Keep your original display when fields exist; otherwise fall back to id-only.
        list_display = tuple(
            col for col in ("active", "threshold_tip_total", "discount_amount", "updated_at")
            if hasattr(LoyaltyTier, col)  # type: ignore
        ) or tuple(
            col for col in ("id", "code", "name", "tip_cents", "is_active", "sort_order")
            if hasattr(LoyaltyTier, col)  # type: ignore
        ) or ("id",)

        # Allow inline editing if the fields exist
        list_editable = tuple(
            col for col in ("threshold_tip_total", "discount_amount", "active")
            if hasattr(LoyaltyTier, col)  # type: ignore
        )

        readonly_fields = tuple(col for col in ("updated_at",) if hasattr(LoyaltyTier, col))  # type: ignore

        # Fieldsets only when those fields exist
        fieldsets = (
            ("Status", {"fields": tuple(col for col in ("active",) if hasattr(LoyaltyTier, col))}),
            ("Rule", {"fields": tuple(col for col in ("threshold_tip_total", "discount_amount") if hasattr(LoyaltyTier, col))}),
            ("Message", {"fields": tuple(col for col in ("message_template",) if hasattr(LoyaltyTier, col))}),
            ("Metadata", {"fields": tuple(col for col in ("updated_at",) if hasattr(LoyaltyTier, col))}),
        )

        # --- Report URL wiring (kept from your code) ---
        def get_urls(self):
            urls = super().get_urls()
            extra = [
                path(
                    "top-tippers/",
                    self.admin_site.admin_view(self.top_tippers_view),
                    name="engagement_top_tippers",
                ),
            ]
            return extra + urls

        def _paid_orders_q(self):
            # Support different order schemas; prefer standardized payments.Order if present
            try:
                from orders.models import Order  # local import to avoid early import errors
            except Exception:
                return Q()

            q_paid = Q()
            if hasattr(Order, "status"):
                # normalize to lower-case "paid" if your statuses are strings
                q_paid |= Q(status__iexact="paid")
                q_paid |= Q(status__iexact="PAID")
            if hasattr(Order, "is_paid"):
                q_paid |= Q(is_paid=True)
            return q_paid

        def top_tippers_view(self, request):
            try:
                from orders.models import Order
            except Exception:
                # Render empty safely if orders app is not ready
                ctx = {"title": "Top Tippers (by total tips paid)", "rows": [], "q": "", "date_from": "", "date_to": ""}
                return render(request, "admin/loyality/top_tippers.html", ctx)

            q = (request.GET.get("q") or "").strip()
            date_from = (request.GET.get("from") or "").strip()
            date_to = (request.GET.get("to") or "").strip()

            qs = Order.objects.all()
            paid_filter = self._paid_orders_q()
            if paid_filter:
                qs = qs.filter(paid_filter)

            select_related_fields = []
            if hasattr(Order, "user"):
                select_related_fields.append("user")
            if hasattr(Order, "created_by"):
                select_related_fields.append("created_by")
            if select_related_fields:
                qs = qs.select_related(*select_related_fields)

            if q:
                qq = Q()
                if hasattr(Order, "user"):
                    qq |= Q(user__username__icontains=q) | Q(user__email__icontains=q)
                if hasattr(Order, "created_by"):
                    qq |= Q(created_by__username__icontains=q) | Q(created_by__email__icontains=q)
                qs = qs.filter(qq)

            if date_from:
                if hasattr(Order, "paid_at"):
                    qs = qs.filter(paid_at__date__gte=date_from)
                elif hasattr(Order, "created_at"):
                    qs = qs.filter(created_at__date__gte=date_from)
            if date_to:
                if hasattr(Order, "paid_at"):
                    qs = qs.filter(paid_at__date__lte=date_to)
                elif hasattr(Order, "created_at"):
                    qs = qs.filter(created_at__date__lte=date_to)

            values = []
            if hasattr(Order, "user"):
                values += ["user_id", "user__username", "user__email"]
            if hasattr(Order, "created_by"):
                values += ["created_by_id", "created_by__username", "created_by__email"]

            tip_field = "tip_cents" if hasattr(Order, "tip_cents") else "tip_amount"
            agg = qs.values(*values).annotate(total_tip=Sum(tip_field)).order_by("-total_tip")

            rows = []
            rank = 0
            last_tip = None
            for rec in agg:
                # rec['total_tip'] might be int (cents) or Decimal — normalize for display
                raw_tip = rec.get("total_tip") or 0
                if isinstance(raw_tip, int):
                    total_tip = Decimal(raw_tip) / Decimal("100")
                else:
                    total_tip = Decimal(raw_tip).quantize(Decimal("0.01"))

                if rec.get("user__username"):
                    display = rec["user__username"]
                elif rec.get("created_by__username"):
                    display = rec["created_by__username"]
                elif rec.get("user__email"):
                    display = rec["user__email"]
                elif rec.get("created_by__email"):
                    display = rec["created_by__email"]
                elif rec.get("user_id"):
                    display = f"User #{rec['user_id']}"
                elif rec.get("created_by_id"):
                    display = f"User #{rec['created_by_id']}"
                else:
                    display = "(unknown user)"

                if last_tip != total_tip:
                    rank += 1
                    last_tip = total_tip

                rows.append({"rank": rank, "user_display": display, "total_tip": total_tip})

            cfg = LoyaltyTier.objects.first() if hasattr(LoyaltyTier, "objects") else None
            threshold = getattr(cfg, "threshold_tip_total", None)
            discount = getattr(cfg, "discount_amount", None)
            active = getattr(cfg, "active", None)

            ctx = {
                "title": "Top Tippers (by total tips paid)",
                "rows": rows,
                "q": q,
                "date_from": date_from,
                "date_to": date_to,
                "threshold": threshold,
                "discount": discount,
                "active": active,
                "opts": LoyaltyTier._meta if hasattr(LoyaltyTier, "_meta") else None,
            }
            return render(request, "admin/loyality/top_tippers.html", ctx)

    _register_model_if_needed(LoyaltyTier, LoyaltyTierAdmin)


# ---------------------------------------------------------------------------
# Optional DiscountRule admin wiring
# ---------------------------------------------------------------------------

DiscountRule = None
try:
    from orders.models import DiscountRule as _DiscountRule  # type: ignore
    DiscountRule = _DiscountRule
except Exception:
    DiscountRule = None


class DiscountRuleAdmin(admin.ModelAdmin):
    list_display = tuple(
        col
        for col in ("id", "threshold_cents", "discount_cents", "is_active", "sort_order", "created_at")
        if hasattr(DiscountRule, col)  # type: ignore
    ) or ("id",)
    list_filter = tuple(col for col in ("is_active",) if hasattr(DiscountRule, col))  # type: ignore
    ordering = tuple(col for col in ("sort_order", "-threshold_cents") if hasattr(DiscountRule, col))  # type: ignore


_register_model_if_needed(DiscountRule, DiscountRuleAdmin)
