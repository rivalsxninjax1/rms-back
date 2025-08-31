from django.contrib import admin
from django.apps import apps
from django.contrib.admin.sites import AlreadyRegistered
from .models import Organization, Location, Table


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
    if m not in [Organization, Location, Table]:  # Skip already registered models
        try: admin.site.register(m)
        except AlreadyRegistered: pass
