from django.contrib import admin
from django.apps import apps
from django.contrib.admin.sites import AlreadyRegistered
from .models import Table, Reservation


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ('table_number', 'location', 'capacity', 'is_active', 'created_at')
    list_filter = ('location', 'is_active', 'created_at')
    search_fields = ('table_number', 'location__name')
    list_editable = ('is_active',)
    ordering = ('location', 'table_number')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('location', 'table_number', 'capacity')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'table', 'guest_name', 'guest_phone', 'party_size', 'start_time', 'status')
    list_filter = ('status', 'start_time', 'table__location')
    search_fields = ('guest_name', 'guest_phone', 'table__table_number')
    list_editable = ('status',)
    ordering = ('-start_time',)
    readonly_fields = ('created_at', 'reservation_date')
    
    fieldsets = (
        ('Reservation Details', {
            'fields': ('location', 'table', 'guest_name', 'guest_phone', 'party_size')
        }),
        ('Timing', {
            'fields': ('start_time', 'end_time')
        }),
        ('Status & Notes', {
            'fields': ('status', 'note')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'reservation_date'),
            'classes': ('collapse',)
        }),
    )


# Register other models automatically
for m in apps.get_app_config("reservations").get_models():
    if m not in [Table, Reservation]:  # Skip already registered models
        try: admin.site.register(m)
        except AlreadyRegistered: pass
