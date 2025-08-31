from django.contrib import admin
from django.apps import apps
from django.contrib.admin.sites import AlreadyRegistered
from .models import Supplier, InventoryItem, Table


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ('table_number', 'location', 'capacity', 'condition', 'is_active', 'last_maintenance', 'purchase_date')
    list_filter = ('location', 'condition', 'is_active', 'purchase_date', 'last_maintenance')
    search_fields = ('table_number', 'location__name')
    list_editable = ('is_active', 'condition')
    ordering = ('location', 'table_number')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('location', 'table_number', 'capacity')
        }),
        ('Asset Details', {
            'fields': ('condition', 'is_active')
        }),
        ('Maintenance & Purchase', {
            'fields': ('last_maintenance', 'purchase_date', 'purchase_cost')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# Register other models automatically
for m in apps.get_app_config("inventory").get_models():
    if m not in [Supplier, InventoryItem, Table]:  # Skip already registered models
        try: admin.site.register(m)
        except AlreadyRegistered: pass
