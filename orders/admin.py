from __future__ import annotations

import csv
from typing import Dict, Optional, Type

from django.contrib import admin
from django.db import models
from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import format_html

from .models import Order, OrderItem

# Optional Payment inline (only if a payments.Payment model exists and FK->orders.Order)
try:
    from payments.models import Payment  # type: ignore
except Exception:
    Payment = None

# Optional Reservations.Table for linking dine-in table
try:
    from reservations.models import Table as RMSTable  # type: ignore
except Exception:
    RMSTable = None


# ---------------------------------------------------------------------------
# Safe registration helper (for optional models)
# ---------------------------------------------------------------------------

def _is_model(klass: object) -> bool:
    try:
        return isinstance(klass, type) and issubclass(klass, models.Model)
    except Exception:
        return False


def _safe_register(model_cls: Optional[Type[models.Model]], admin_cls: Optional[Type[admin.ModelAdmin]] = None) -> None:
    if not _is_model(model_cls):
        return
    try:
        if hasattr(admin.site, "is_registered") and admin.site.is_registered(model_cls):  # type: ignore[attr-defined]
            return
    except Exception:
        pass
    try:
        if admin_cls is None:
            class _AutoAdmin(admin.ModelAdmin):
                list_display = ("id",)
            admin.site.register(model_cls, _AutoAdmin)
        else:
            admin.site.register(model_cls, admin_cls)
    except admin.sites.AlreadyRegistered:
        return


# ---------------------------------------------------------------------------
# Order inlines and admin
# ---------------------------------------------------------------------------

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    raw_id_fields = ("menu_item",)


# Register Payment inline only if it truly has FK to orders.Order named "order"
if Payment and any(getattr(f, "attname", "") == "order_id" for f in Payment._meta.get_fields()):  # type: ignore[attr-defined]
    class PaymentInline(admin.StackedInline):
        model = Payment
        extra = 0
        can_delete = False
        fk_name = "order"
        fields = tuple(
            f for f in (
                "provider",
                "amount",
                "currency",
                "is_paid",
                "stripe_session_id",
                "stripe_payment_intent",
                "created_at",
                "updated_at",
            ) if hasattr(Payment, f)
        )
        readonly_fields = fields
else:
    PaymentInline = None


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """
    Admin aligned to the actual fields present in orders.models.Order
    (per your ZIP): user, status, notes, tip_amount, discount_amount,
    currency, delivery_option, dine_in_table, invoice_pdf, created_at, updated_at.
    """
    list_display = (
        "id",
        "user",
        "delivery_option",
        "status",
        "items_subtotal_admin",
        "tip_amount",
        "discount_amount",
        "grand_total_admin",
        "created_at",
        "invoice_link",
    )
    list_filter = ("status", "delivery_option", "created_at")
    date_hierarchy = "created_at"
    inlines = [x for x in (OrderItemInline, PaymentInline) if x]
    search_fields = ("=id", "user__username")
    raw_id_fields = ("user",)
    ordering = ("-created_at",)
    readonly_fields = tuple(f for f in ("invoice_pdf",) if hasattr(Order, "invoice_pdf"))

    # Avoid N+1 (items + menu_item + user + dine_in_table)
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        try:
            qs = qs.select_related("user", "dine_in_table")
            qs = qs.prefetch_related("items__menu_item")
        except Exception:
            pass
        return qs

    # Friendly invoice link if file present
    def invoice_link(self, obj: Order) -> str:
        invoice = getattr(obj, "invoice_pdf", None)
        if invoice:
            try:
                return format_html('<a href="{}" target="_blank" rel="noopener">PDF</a>', invoice.url)
            except Exception:
                return "-"
        return "-"
    invoice_link.short_description = "Invoice"

    # Table link to reservations.Table admin if FK exists
    def table_ref(self, obj: Order) -> str:
        """
        Render a friendly link to the dine-in table admin page if set.
        """
        tbl = getattr(obj, "dine_in_table", None)
        if not tbl:
            return "-"
        label = f"Table {getattr(tbl, 'table_number', '')}".strip() or f"Table #{getattr(tbl, 'id', '')}"
        if RMSTable:
            try:
                url = reverse("admin:reservations_table_change", args=[tbl.id])
                return format_html('<a href="{}">{}</a>', url, label)
            except Exception:
                return label
        return label
    table_ref.short_description = "RMS Table"

    # Admin-friendly numeric columns
    def items_subtotal_admin(self, obj: Order):
        return obj.items_subtotal()
    items_subtotal_admin.short_description = "Subtotal"

    def grand_total_admin(self, obj: Order):
        return obj.grand_total()
    grand_total_admin.short_description = "Grand Total"

    # ---- CSV Export (aligned to your model)
    actions = ["export_sales_csv"]

    def export_sales_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="sales.csv"'
        writer = csv.writer(response)
        writer.writerow([
            "Order ID", "Created At", "User",
            "Delivery", "Table",
            "Status",
            "Subtotal", "Tip", "Discount",
            "Final Total", "Currency"
        ])
        for o in queryset:
            writer.writerow([
                o.id,
                o.created_at,
                getattr(o.user, "username", "") if getattr(o, "user_id", None) else "",
                getattr(o, "delivery_option", ""),
                (f"Table {getattr(o.dine_in_table, 'table_number', '')}" if getattr(o, "dine_in_table_id", None) else ""),
                getattr(o, "status", ""),
                str(o.items_subtotal()),
                str(o.tip_amount),
                str(o.discount_amount),
                str(o.grand_total()),
                (getattr(o, "currency", "USD") or "USD").upper(),
            ])
        return response
    export_sales_csv.short_description = "Export Sales (CSV)"


# ---------------------------------------------------------------------------
# Optional: TipTier/DiscountRule admin (robust imports; no crashes if missing)
# ---------------------------------------------------------------------------

TipTier = None
try:
    from .models import TipTier as _TipTier  # defined in this app
    TipTier = _TipTier
except Exception:
    TipTier = None

class TipTierAdmin(admin.ModelAdmin):
    # Reflect the actual fields of your TipTier in orders.models:
    # rank, default_tip_amount
    list_display = tuple(
        col for col in ("id", "rank", "default_tip_amount")
        if hasattr(TipTier, col)  # type: ignore
    ) or ("id",)
    search_fields = tuple(col for col in ("rank",) if hasattr(TipTier, col))  # type: ignore
    ordering = tuple(col for col in ("rank", "id") if hasattr(TipTier, col))  # type: ignore

_safe_register(TipTier, TipTierAdmin)

DiscountRule = None
try:
    from .models import DiscountRule as _DiscountRule
    DiscountRule = _DiscountRule
except Exception:
    DiscountRule = None

class DiscountRuleAdmin(admin.ModelAdmin):
    list_display = tuple(
        col for col in ("id", "threshold_cents", "discount_cents", "is_active", "sort_order", "created_at")
        if hasattr(DiscountRule, col)  # type: ignore
    ) or ("id",)
    list_filter = tuple(col for col in ("is_active",) if hasattr(DiscountRule, col))  # type: ignore
    ordering = tuple(col for col in ("sort_order", "-threshold_cents", "id") if hasattr(DiscountRule, col))  # type: ignore

_safe_register(DiscountRule, DiscountRuleAdmin)
