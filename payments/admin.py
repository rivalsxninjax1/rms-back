from __future__ import annotations

from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("menu_item_id", "name", "unit_amount_cents", "quantity", "line_total_cents")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "status",
        "currency",
        "subtotal_cents",
        "tip_cents",
        "discount_cents",
        "total_cents",
        "delivery",
        "created_at",
    )
    list_filter = ("status", "currency", "delivery", "created_at")
    search_fields = ("id", "user__username", "stripe_session_id", "stripe_payment_intent")
    readonly_fields = ("created_at", "updated_at", "stripe_session_id", "stripe_payment_intent")
    inlines = [OrderItemInline]
