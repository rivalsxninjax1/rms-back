from __future__ import annotations

from django.contrib import admin

from .models import DailySales, ShiftReport, AuditLog
from django.http import HttpResponse
import csv


@admin.register(DailySales)
class DailySalesAdmin(admin.ModelAdmin):
    list_display = ("date", "total_orders", "subtotal_cents", "tip_cents", "discount_cents", "total_cents", "created_at")
    date_hierarchy = "date"
    ordering = ("-date", "-id")
    readonly_fields = ("created_at",)


@admin.register(ShiftReport)
class ShiftReportAdmin(admin.ModelAdmin):
    list_display = ("date", "shift", "staff", "orders_count", "total_cents", "cash_open_cents", "cash_close_cents", "over_short_cents", "created_at")
    list_filter = ("shift", "opened_at", "closed_at")
    date_hierarchy = "date"
    ordering = ("-date", "shift", "-id")
    readonly_fields = ("created_at",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "severity", "category", "model_name", "object_repr")
    list_filter = ("action", "severity", "category", "created_at")
    search_fields = ("description", "object_repr", "user__username", "model_name")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    readonly_fields = ("user", "action", "description", "content_type", "object_id", "object_repr", "model_name", "changes", "ip_address", "user_agent", "request_path", "request_method", "severity", "category", "metadata", "created_at")
    actions = ("export_audit_csv",)

    def export_audit_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="audit_logs.csv"'
        w = csv.writer(response)
        w.writerow(["created_at","user","action","severity","category","model","object_id","object_repr","description","ip","method","path"]) 
        for row in queryset.select_related('user','content_type'):
            w.writerow([
                row.created_at,
                getattr(row.user, 'username', ''),
                row.action,
                row.severity,
                row.category,
                row.model_name,
                row.object_id,
                row.object_repr,
                row.description,
                row.ip_address,
                row.request_method,
                row.request_path,
            ])
        return response
    export_audit_csv.short_description = "Export selected audit logs to CSV"
