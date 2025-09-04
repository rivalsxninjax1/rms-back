from __future__ import annotations
from django.contrib import admin
from .models import Coupon
from reports.models import AuditLog


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("code", "percent", "active", "valid_from", "valid_to", "times_used", "max_uses", "created_at")
    list_filter = ("active", "valid_from", "valid_to")
    search_fields = ("code", "phrase")
    readonly_fields = ("times_used", "created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("code", "phrase", "percent", "active")}),
        ("Validity", {"fields": ("valid_from", "valid_to", "max_uses")}),
        ("Usage", {"fields": ("times_used",)}),
        ("Meta", {"fields": ("created_by", "created_at", "updated_at")}),
    )

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        try:
            AuditLog.log_action(request.user, 'UPDATE' if change else 'CREATE', f"Coupon {'updated' if change else 'created'}: {obj.code}", content_object=obj, changes=form.changed_data, request=request, category='coupons')
        except Exception:
            pass

    def delete_model(self, request, obj):
        try:
            AuditLog.log_action(request.user, 'DELETE', f"Coupon deleted: {obj.code}", content_object=obj, request=request, category='coupons')
        except Exception:
            pass
        super().delete_model(request, obj)
