from django.contrib import admin
from django.apps import apps
from django.contrib.admin.sites import AlreadyRegistered
from .models import UserTipAggregate


# Keep auto-registration for everything else
for m in apps.get_app_config("reports").get_models():
    if m is UserTipAggregate:
        continue
    try:
        admin.site.register(m)
    except AlreadyRegistered:
        pass


@admin.register(UserTipAggregate)
class UserTipAggregateAdmin(admin.ModelAdmin):
    list_display = ("user", "rank", "total_tip", "avg_tip", "max_tip", "last_tip_date")
    list_filter = ("rank",)
    date_hierarchy = "last_tip_date"
    search_fields = ("user__username", "user__email")
    ordering = ("-total_tip",)
    readonly_fields = tuple(list_display)
