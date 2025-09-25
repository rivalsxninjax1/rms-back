from django.contrib import admin
from django.apps import apps
from django.contrib.admin.sites import AlreadyRegistered
from .models import Organization, Location, Table
try:
    # Legacy model that has been superseded by reservations.Reservation
    from .models import Reservation as CoreReservation  # type: ignore
except Exception:
    CoreReservation = None
try:
    # Core AuditLog is deprecated in favor of reports.AuditLog — hide in Admin
    from .models import AuditLog as CoreAuditLog  # type: ignore
except Exception:
    CoreAuditLog = None


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ('table_number', 'location', 'capacity', 'table_type', 'is_active', 'created_at')
    list_filter = ('location', 'table_type', 'is_active', 'created_at')
    search_fields = ('table_number', 'location__name')
    list_editable = ('is_active',)
    ordering = ('location', 'table_number')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('location', 'table_number', 'capacity')
        }),
        ('Table Details', {
            'fields': ('table_type', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# Register other models automatically
for m in apps.get_app_config("core").get_models():
    # Skip legacy core.Reservation and deprecated core.AuditLog in Admin
    if m in [Organization, Location, Table] or (CoreReservation and m is CoreReservation) or (CoreAuditLog and m is CoreAuditLog):
        continue
    try:
        admin.site.register(m)
    except AlreadyRegistered:
        pass
