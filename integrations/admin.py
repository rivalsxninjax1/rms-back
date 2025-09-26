from django.contrib import admin
from .models import ExternalOrder, SyncLog


@admin.register(ExternalOrder)
class ExternalOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "provider", "external_id", "order", "status", "updated_at")
    search_fields = ("external_id", "order__id")
    list_filter = ("provider", "status")


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = ("id", "provider", "event", "success", "created_at")
    list_filter = ("provider", "success", "event")
    search_fields = ("message",)

