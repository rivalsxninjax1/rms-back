from django.contrib import admin
from django.apps import apps
from django.contrib.admin.sites import AlreadyRegistered
from .models import Reservation
# Note: Table model is now managed in core.admin


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
    if m not in [Reservation]:  # Skip already registered models
        try: admin.site.register(m)
        except AlreadyRegistered: pass
