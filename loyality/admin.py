from __future__ import annotations

from django.contrib import admin

from .models import LoyaltyRank, LoyaltyProfile


@admin.register(LoyaltyRank)
class LoyaltyRankAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "tip_cents", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    ordering = ("sort_order", "name")
    list_editable = ("tip_cents", "is_active", "sort_order")


@admin.register(LoyaltyProfile)
class LoyaltyProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "rank", "rank_tip_cents")
    list_filter = ("rank__name",)
    search_fields = ("user__username", "user__email", "rank__name")
    autocomplete_fields = ("user", "rank")

    @admin.display(description="Tip (¢)")
    def rank_tip_cents(self, obj: LoyaltyProfile) -> int:
        return obj.tip_cents
