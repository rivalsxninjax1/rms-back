from __future__ import annotations
from decimal import Decimal

from django.contrib import admin
from django.db.models import Sum, Q
from django.urls import path
from django.shortcuts import render

from .models import TipLoyaltySetting
from orders.models import Order


@admin.register(TipLoyaltySetting)
class TipLoyaltySettingAdmin(admin.ModelAdmin):
    """
    Admin to configure tip-based loyalty:
      - threshold_tip_total
      - discount_amount (fixed money off)
      - active toggle
      - message_template

    Also exposes a custom report URL under this model's section:
      /admin/loyality/tiployaltysetting/top-tippers/
    """

    # To avoid admin.E124, the first column in list_display must not be editable.
    # We use "id" as the link column and only edit the other fields inline.
    list_display = (
        "id",  # link column (non-editable)
        "active",
        "threshold_tip_total",
        "discount_amount",
        "updated_at",
    )
    list_display_links = ("id",)
    list_editable = (
        "active",
        "threshold_tip_total",
        "discount_amount",
    )
    readonly_fields = ("updated_at",)
    fieldsets = (
        ("Status", {"fields": ("active",)}),
        ("Rule", {"fields": ("threshold_tip_total", "discount_amount")}),
        ("Message", {"fields": ("message_template",)}),
        ("Metadata", {"fields": ("updated_at",)}),
    )

    # ----- Custom report: Top Tippers (rank users by total TIP paid) -----
    def get_urls(self):
        urls = super().get_urls()
        extra = [
            path(
                "top-tippers/",
                self.admin_site.admin_view(self.top_tippers_view),
                name="loyality_top_tippers",
            ),
        ]
        return extra + urls

    def _paid_orders_q_for_user_model(self):
        """
        Build a Q object that marks 'paid'. We OR together status=PAID and is_paid=True
        because different deployments may rely on either/both fields.
        """
        q_paid = Q()
        if hasattr(Order, "status"):
            q_paid |= Q(status="PAID")
        if hasattr(Order, "is_paid"):
            q_paid |= Q(is_paid=True)
        return q_paid

    def top_tippers_view(self, request):
        """
        Renders a simple table of users ranked by total TIP paid (descending).
        Filters:
          - q : substring on username/email
          - from : YYYY-MM-DD (paid_at/date lower bound)
          - to   : YYYY-MM-DD (paid_at/date upper bound)
        """
        q = (request.GET.get("q") or "").strip()
        date_from = (request.GET.get("from") or "").strip()
        date_to = (request.GET.get("to") or "").strip()

        qs = Order.objects.all()

        # Only PAID orders
        qs = qs.filter(self._paid_orders_q_for_user_model())

        # Join user fields if present
        select_related_fields = []
        if hasattr(Order, "user"):
            select_related_fields.append("user")
        if hasattr(Order, "created_by"):
            select_related_fields.append("created_by")
        if select_related_fields:
            qs = qs.select_related(*select_related_fields)

        # Text filter
        if q:
            qq = Q()
            if hasattr(Order, "user"):
                qq |= Q(user__username__icontains=q) | Q(user__email__icontains=q)
            if hasattr(Order, "created_by"):
                qq |= Q(created_by__username__icontains=q) | Q(created_by__email__icontains=q)
            qs = qs.filter(qq)

        # Date range filter (paid_at preferred, else created_at)
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

        # Aggregate by user identity (user or created_by) and sum tips
        values = []
        if hasattr(Order, "user"):
            values += ["user_id", "user__username", "user__email"]
        if hasattr(Order, "created_by"):
            values += ["created_by_id", "created_by__username", "created_by__email"]

        agg = (
            qs.values(*values)
            .annotate(total_tip=Sum("tip_amount"))
            .order_by("-total_tip")
        )

        # Build rows with a unified 'display user'
        rows = []
        rank = 0
        last_tip = None
        for rec in agg:
            total_tip = (rec.get("total_tip") or Decimal("0.00")).quantize(Decimal("0.01"))
            # Choose best available identity
            display = None
            if rec.get("user__username"):
                display = rec["user__username"]
            elif rec.get("created_by__username"):
                display = rec["created_by__username"]
            elif rec.get("user__email"):
                display = rec["user__email"]
            elif rec.get("created_by__email"):
                display = rec["created_by__email"]
            else:
                # Fallback to ids
                if rec.get("user_id"):
                    display = f"User #{rec['user_id']}"
                elif rec.get("created_by_id"):
                    display = f"User #{rec['created_by_id']}"
                else:
                    display = "(unknown user)"

            if last_tip != total_tip:
                rank += 1
                last_tip = total_tip

            rows.append({
                "rank": rank,
                "user_display": display,
                "total_tip": total_tip,
            })

        # Current config for context
        cfg = TipLoyaltySetting.get_solo()
        ctx = {
            "title": "Top Tippers (by total tip paid)",
            "rows": rows,
            "q": q,
            "date_from": date_from,
            "date_to": date_to,
            "threshold": cfg.threshold_tip_total,
            "discount": cfg.discount_amount,
            "active": cfg.active,
            "opts": self.model._meta,  # for admin breadcrumbs
        }
        # Template: loyality/templates/admin/loyality/top_tippers.html
        return render(request, "admin/loyality/top_tippers.html", ctx)
