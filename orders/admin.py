from __future__ import annotations

import csv
import re
from typing import Dict, Optional

from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html
from django.urls import reverse

from .models import Order, OrderItem

# Optional Payment inline
try:
    from payments.models import Payment  # type: ignore
except Exception:
    Payment = None

# Optional Reservations.Table for linking dine-in table
try:
    from reservations.models import Table as RMSTable  # type: ignore
except Exception:
    RMSTable = None


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    raw_id_fields = ("menu_item",)


if Payment:
    class PaymentInline(admin.StackedInline):
        model = Payment
        extra = 0
        can_delete = False
        fk_name = "order"
        fields = (
            "provider",
            "amount",
            "currency",
            "is_paid",
            "stripe_session_id",
            "stripe_payment_intent",
            "created_at",
            "updated_at",
        )
        readonly_fields = fields
else:
    PaymentInline = None


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "created_by",
        "source",
        "table_number",
        "table_ref",        # NEW: link to RMS Table if available (TBL:<id>)
        "status",
        "is_paid",
        "subtotal",
        "tip_amount",
        "discount_amount",
        "discount_code",
        "created_at",
        "invoice_link",
    )
    list_filter = ("status", "source", "is_paid", "created_at")
    date_hierarchy = "created_at"
    inlines = [x for x in (OrderItemInline, PaymentInline) if x]
    search_fields = ("=id", "created_by__username", "discount_code", "external_order_id")
    raw_id_fields = ("created_by",)
    ordering = ("-created_at",)
    readonly_fields = ("invoice_pdf",)

    # ---- Performance: avoid N+1 (payment + items -> menu_item)
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        try:
            qs = qs.select_related("payment", "created_by")
            qs = qs.prefetch_related("items__menu_item")
        except Exception:
            pass
        return qs

    # ---- Clickable invoice link (unchanged)
    def invoice_link(self, obj: Order) -> str:
        invoice = getattr(obj, "invoice_pdf", None)
        if invoice:
            try:
                return format_html('<a href="{}" target="_blank" rel="noopener">PDF</a>', invoice.url)
            except Exception:
                return "-"
        return "-"
    invoice_link.short_description = "Invoice"

    # ---- NEW: RMS Table link/label if external_order_id == "TBL:<id>"
    def table_ref(self, obj: Order) -> str:
        """
        If the order was aligned to an RMS Table, we store external_order_id="TBL:<id>".
        This renders a link to that Table's admin change page, with a human-friendly label:
        "<Location Name> — Table <number>" when available; else "Table <number>".
        """
        ext = (getattr(obj, "external_order_id", "") or "").strip()
        m = re.match(r"^TBL:(\d+)$", ext or "")
        if not m:
            return "-"
        if RMSTable is None:
            return f"TBL:{m.group(1)}"
        try:
            table_id = int(m.group(1))
        except Exception:
            return f"TBL:{ext}"
        try:
            tbl = RMSTable.objects.select_related("location").filter(id=table_id).first()
            if not tbl:
                return f"TBL:{table_id}"
            loc_name = getattr(tbl.location, "name", getattr(tbl.location, "title", "")) if getattr(tbl, "location", None) else ""
            label = f"{loc_name} — Table {getattr(tbl, 'table_number', '')}".strip(" —")
            try:
                url = reverse("admin:reservations_table_change", args=[tbl.id])
                return format_html('<a href="{}">{}</a>', url, label or f"TBL:{table_id}")
            except Exception:
                return label or f"TBL:{table_id}"
        except Exception:
            return f"TBL:{table_id}"
    table_ref.short_description = "RMS Table"

    # ---- CSV Export (kept; now also resolves RMS Table label when possible)
    actions = ["export_sales_csv"]

    def _build_table_labels(self, table_ids) -> Dict[int, str]:
        """
        Batch-fetch labels for table ids -> "Location — Table X"
        Only used inside export to avoid N+1 queries.
        """
        if not RMSTable or not table_ids:
            return {}
        labels: Dict[int, str] = {}
        try:
            for tbl in RMSTable.objects.select_related("location").filter(id__in=table_ids):
                loc = getattr(tbl.location, "name", getattr(tbl.location, "title", "")) if getattr(tbl, "location", None) else ""
                lbl = f"{loc} — Table {getattr(tbl, 'table_number', '')}".strip(" —")
                labels[tbl.id] = lbl or f"Table {getattr(tbl, 'table_number', '')}"
        except Exception:
            # Best-effort; return what we have
            pass
        return labels

    def export_sales_csv(self, request, queryset):
        # Pre-resolve any external_order_id "TBL:<id>" -> admin label
        table_ids = []
        id_map: Dict[int, int] = {}  # order_id -> table_id
        for o in queryset:
            try:
                ext = (getattr(o, "external_order_id", "") or "").strip()
                m = re.match(r"^TBL:(\d+)$", ext)
                if m:
                    tid = int(m.group(1))
                    id_map[o.id] = tid
                    table_ids.append(tid)
            except Exception:
                continue
        labels = self._build_table_labels(table_ids)

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="sales.csv"'
        writer = csv.writer(response)
        writer.writerow([
            "Order ID", "Created At", "User", "Source",
            "Table", "RMS Table",        # <-- added RMS Table label
            "Status", "Paid", "Subtotal", "Tip", "Discount",
            "Final Total", "Currency"
        ])
        for o in queryset:
            rms_label: Optional[str] = None
            tid = id_map.get(o.id)
            if tid:
                rms_label = labels.get(tid) or f"TBL:{tid}"

            writer.writerow([
                o.id,
                o.created_at,
                getattr(o.created_by, "username", "") if getattr(o, "created_by_id", None) else "",
                getattr(o, "source", ""),
                getattr(o, "table_number", "") or "",
                rms_label or "",  # NEW column
                getattr(o, "status", ""),
                "YES" if getattr(o, "is_paid", False) else "NO",
                str(getattr(o, "subtotal", "")),
                str(getattr(o, "tip_amount", "")),
                str(getattr(o, "discount_amount", "")),
                str(o.grand_total()),
                (getattr(o, "currency", "USD") or "USD").upper(),
            ])
        return response
    export_sales_csv.short_description = "Export Sales (CSV)"
