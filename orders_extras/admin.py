from __future__ import annotations

from django.contrib import admin

from .models import OrderExtra


@admin.register(OrderExtra)
class OrderExtraAdmin(admin.ModelAdmin):
    """
    Safe, minimal admin to avoid system check errors coming from fields that
    don't exist in the original broken admin (created_at, updated_at, etc.).
    """
    list_display = ("id",)
    readonly_fields: tuple = ()
    list_filter: tuple = ()
    search_fields: tuple = ()
