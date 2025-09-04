from __future__ import annotations

import csv
from typing import Dict, Optional, Type

from django.contrib import admin
from django.db import models
from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import format_html

from .models import Order, OrderItem
from .models import Cart
from reports.models import AuditLog

# Optional Billing Payment inline (manual/cash payments)
try:
    from billing.models import Payment as BillingPayment  # type: ignore
except Exception:
    BillingPayment = None

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
if BillingPayment and any(getattr(f, "attname", "") == "order_id" for f in BillingPayment._meta.get_fields()):  # type: ignore[attr-defined]
    class PaymentInline(admin.StackedInline):
        model = BillingPayment
        extra = 0
        can_delete = False
        fk_name = "order"
        readonly_fields = tuple(
            f for f in (
                "amount", "currency", "status", "reference", "created_at", "updated_at"
            ) if hasattr(BillingPayment, f)
        )
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
        "coupon_discount",
        "applied_coupon_code",
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
    # Only include fields that actually exist on orders.Order
    _ro = []
    if hasattr(Order, "invoice_pdf"):
        _ro.append("invoice_pdf")
    if hasattr(Order, "applied_coupon_code"):
        _ro.append("applied_coupon_code")
    # Harden: make money/tax/discount fields read-only in admin UI
    _money_ro = [
        'subtotal', 'modifier_total', 'discount_amount', 'coupon_discount',
        'loyalty_discount', 'tip_amount', 'delivery_fee', 'service_fee',
        'tax_amount', 'tax_rate', 'total_amount', 'refund_amount', 'item_count'
    ]
    readonly_fields = tuple([f for f in _ro if hasattr(Order, f)]) + tuple(
        [f for f in _money_ro if hasattr(Order, f)]
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        try:
            AuditLog.log_action(request.user, 'UPDATE' if change else 'CREATE', f"Order {'updated' if change else 'created'}: #{obj.id}", content_object=obj, changes=form.changed_data, request=request, category='orders')
        except Exception:
            pass

    def delete_model(self, request, obj):
        try:
            AuditLog.log_action(request.user, 'DELETE', f"Order deleted: #{obj.id}", content_object=obj, request=request, category='orders')
        except Exception:
            pass
        super().delete_model(request, obj)

    # Avoid N+1 (items + menu_item + user + table)
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        try:
            qs = qs.select_related("user", "table")
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
        tbl = getattr(obj, "table", None)
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

    # ---- CSV Export and Cash Payment ----
    actions = ["export_sales_csv", "record_cash_payment"]

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
                (f"Table {getattr(o.table, 'table_number', '')}" if getattr(o, "table_id", None) else ""),
                getattr(o, "status", ""),
                str(o.items_subtotal()),
                str(o.tip_amount),
                str(o.discount_amount),
                str(o.grand_total()),
                (getattr(o, "currency", "USD") or "USD").upper(),
            ])
        try:
            AuditLog.log_action(request.user, 'EXPORT', f'Exported sales CSV ({queryset.count()} orders)', request=request, category='orders')
        except Exception:
            pass
        return response
    export_sales_csv.short_description = "Export Sales (CSV)"

    def record_cash_payment(self, request, queryset):
        """
        Create a manual cash BillingPayment for selected orders for the full order total,
        and mark payment_status as COMPLETED if the model has that field.
        """
        if not BillingPayment:
            self.message_user(request, "Billing.Payment model not available", level=admin.messages.ERROR)
            return
        created = 0
        for o in queryset:
            try:
                amt = getattr(o, "total_amount", None) or getattr(o, "total", None)
                if amt is None:
                    continue
                BillingPayment.objects.create(order=o, amount=amt, currency=getattr(o, "currency", "USD"), status="completed", reference="cash")
                if hasattr(o, "payment_status"):
                    setattr(o, "payment_status", "COMPLETED")
                    o.save(update_fields=["payment_status", "updated_at"]) if hasattr(o, "updated_at") else o.save()
                created += 1
            except Exception:
                continue
        self.message_user(request, f"Recorded cash payments for {created} order(s)", level=admin.messages.INFO)
        try:
            AuditLog.log_action(request.user, 'UPDATE', f'Recorded cash payments for {created} orders', request=request, category='orders')
        except Exception:
            pass
    record_cash_payment.short_description = "Record Cash Payment (full)"


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


# ---------------------------------------------------------------------------
# Cart admin (read-only money fields)
# ---------------------------------------------------------------------------

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'cart_uuid', 'user', 'status', 'delivery_option', 'item_count', 'total', 'updated_at'
    )
    search_fields = ('=id', '=cart_uuid', 'user__username', 'user__email')
    list_filter = ('status', 'delivery_option', 'updated_at')
    readonly_fields = tuple(
        f for f in (
            'cart_uuid', 'user', 'subtotal', 'modifier_total', 'discount_amount',
            'coupon_discount', 'loyalty_discount', 'tip_amount', 'tip_percentage',
            'delivery_fee', 'service_fee', 'tax_amount', 'tax_rate', 'total',
            'item_count', 'modification_count', 'created_at', 'updated_at'
        ) if hasattr(Cart, f)
    )
