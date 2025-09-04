from __future__ import annotations

from django.contrib import admin

from .models import LoyaltyRank, LoyaltyProfile, LoyaltyPointsLedger
from django.http import HttpResponse
import csv
from reports.models import AuditLog


@admin.register(LoyaltyRank)
class LoyaltyRankAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "tip_cents", "earn_points_per_currency", "burn_cents_per_point", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    ordering = ("sort_order", "name")
    list_editable = ("tip_cents", "is_active", "sort_order")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        try:
            AuditLog.log_action(request.user, 'UPDATE' if change else 'CREATE', f"Loyalty rank {'updated' if change else 'created'}: {obj.code}", content_object=obj, changes=form.changed_data, request=request, category='loyalty')
        except Exception:
            pass

    def delete_model(self, request, obj):
        try:
            AuditLog.log_action(request.user, 'DELETE', f"Loyalty rank deleted: {obj.code}", content_object=obj, request=request, category='loyalty')
        except Exception:
            pass
        super().delete_model(request, obj)


@admin.register(LoyaltyProfile)
class LoyaltyProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "rank", "points", "rank_tip_cents")
    list_filter = ("rank__name",)
    search_fields = ("user__username", "user__email", "rank__name")
    autocomplete_fields = ("user", "rank")
    actions = ("export_profiles_csv",)

    @admin.display(description="Tip (¢)")
    def rank_tip_cents(self, obj: LoyaltyProfile) -> int:
        return obj.tip_cents

    def export_profiles_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="loyalty_profiles.csv"'
        writer = csv.writer(response)
        writer.writerow(['user_id', 'user', 'rank', 'points'])
        for p in queryset.select_related('user','rank'):
            writer.writerow([p.user_id, getattr(p.user,'username',''), getattr(p.rank,'name',''), p.points])
        try:
            AuditLog.log_action(request.user, 'EXPORT', f'Exported {queryset.count()} loyalty profiles', request=request, category='loyalty')
        except Exception:
            pass
        return response
    export_profiles_csv.short_description = "Export selected profiles to CSV"


@admin.register(LoyaltyPointsLedger)
class LoyaltyPointsLedgerAdmin(admin.ModelAdmin):
    list_display = ("profile", "delta", "type", "reason", "reference", "created_by", "created_at")
    list_filter = ("type", "created_at")
    search_fields = ("profile__user__username", "reason", "reference")
    autocomplete_fields = ("profile", "created_by")
    actions = ("export_ledger_csv",)

    def export_ledger_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="loyalty_ledger.csv"'
        writer = csv.writer(response)
        writer.writerow(['profile_id', 'user', 'delta', 'type', 'reason', 'reference', 'created_by', 'created_at'])
        for e in queryset.select_related('profile__user','created_by'):
            writer.writerow([e.profile_id, getattr(e.profile.user,'username',''), e.delta, e.type, e.reason, e.reference, getattr(e.created_by,'username',''), e.created_at.isoformat()])
        return response
    export_ledger_csv.short_description = "Export selected entries to CSV"
