from __future__ import annotations

from django.contrib import admin

from .models import DailySales, ShiftReport


@admin.register(DailySales)
class DailySalesAdmin(admin.ModelAdmin):
    list_display = ("date", "total_orders", "subtotal_cents", "tip_cents", "discount_cents", "total_cents", "created_at")
    date_hierarchy = "date"
    ordering = ("-date", "-id")
    readonly_fields = ("created_at",)


@admin.register(ShiftReport)
class ShiftReportAdmin(admin.ModelAdmin):
    list_display = ("date", "shift", "staff", "orders_count", "total_cents", "created_at")
    list_filter = ("shift",)
    date_hierarchy = "date"
    ordering = ("-date", "shift", "-id")
    readonly_fields = ("created_at",)
