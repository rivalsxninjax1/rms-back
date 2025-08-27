from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.contrib import admin
from django.db.models import Sum, Q
from django.urls import path
from django.shortcuts import render

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

# IMPORTANT: LoyaltyTier is now provided by loyality.TipLoyaltySetting.
try:
    from .compat import LoyaltyTier  # aliased to loyality.models.TipLoyaltySetting
except Exception:  # pragma: no cover
    LoyaltyTier = None  # type: ignore


def _register_model_if_needed(model_cls, admin_cls):
    if model_cls is None:
        return
    if model_cls in admin.site._registry:
        return
    admin.site.register(model_cls, admin_cls)


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


# ---- Loyalty config + Top Tippers report ----
if LoyaltyTier is not None:
    class LoyaltyTierAdmin(admin.ModelAdmin):
        list_display = ("active", "threshold_tip_total", "discount_amount", "updated_at")
        list_editable = ("threshold_tip_total", "discount_amount", "active")
        readonly_fields = ("updated_at",)
        fieldsets = (
            ("Status", {"fields": ("active",)}),
            ("Rule", {"fields": ("threshold_tip_total", "discount_amount")}),
            ("Message", {"fields": ("message_template",)}),
            ("Metadata", {"fields": ("updated_at",)}),
        )

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
            from orders.models import Order
            q_paid = Q()
            if hasattr(Order, "status"):
                q_paid |= Q(status="PAID")
            if hasattr(Order, "is_paid"):
                q_paid |= Q(is_paid=True)
            return q_paid

        def top_tippers_view(self, request):
            from orders.models import Order
            q = (request.GET.get("q") or "").strip()
            date_from = (request.GET.get("from") or "").strip()
            date_to = (request.GET.get("to") or "").strip()

            qs = Order.objects.filter(self._paid_orders_q())
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

            agg = qs.values(*values).annotate(total_tip=Sum("tip_amount")).order_by("-total_tip")

            rows = []
            rank = 0
            last_tip = None
            for rec in agg:
                total_tip = (rec.get("total_tip") or Decimal("0.00")).quantize(Decimal("0.01"))
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
