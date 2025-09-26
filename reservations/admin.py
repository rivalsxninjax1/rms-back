from __future__ import annotations

from datetime import timedelta

from django.contrib import admin, messages
from django.utils import timezone
from django.urls import path
from django.template.response import TemplateResponse
from django.db.models import Max

from .models import Reservation
from core.models import Table, Location


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        "id", "reservation_date", "start_time", "party_size",
        "table", "status", "deposit_amount", "deposit_paid", "created_by",
    )
    list_filter = ("status", "reservation_date", "deposit_paid", "table__location", "table__location__organization")
    search_fields = ("=id", "guest_name", "guest_phone", "confirmation_number")
    # Use dynamic readonly fields to avoid referencing non-existent attributes
    def get_readonly_fields(self, request, obj=None):
        candidates = ["confirmed_at", "seated_at", "completed_at", "cancelled_at", "created_at", "updated_at"]
        present = [f for f in candidates if hasattr(Reservation, f) or (obj and hasattr(obj, f))]
        return tuple(present)

    actions = (
        "action_check_in",
        "action_check_out",
        "action_mark_no_show",
        "action_mark_deposit_paid",
        "action_mark_deposit_unpaid",
        "action_create_hold",
    )

    # ----- Admin actions -----
    def _update_selected(self, request, queryset, **updates):
        count = 0
        for r in queryset.select_for_update():
            for k, v in updates.items():
                setattr(r, k, v)
            r.save(update_fields=list(updates.keys()))
            count += 1
        return count

    def action_check_in(self, request, queryset):
        now = timezone.now()
        updated = 0
        for r in queryset.select_for_update():
            if r.status not in [r.STATUS_CANCELLED, r.STATUS_NO_SHOW, r.STATUS_COMPLETED]:
                r.status = r.STATUS_CONFIRMED
                update_fields = ["status"]
                if hasattr(r, "seated_at"):
                    if not getattr(r, "seated_at"):
                        r.seated_at = now  # type: ignore[attr-defined]
                    update_fields.append("seated_at")
                if hasattr(r, "confirmed_at"):
                    if not getattr(r, "confirmed_at"):
                        r.confirmed_at = now  # type: ignore[attr-defined]
                    update_fields.append("confirmed_at")
                if hasattr(r, "updated_at"):
                    update_fields.append("updated_at")
                r.save(update_fields=update_fields)
                updated += 1
        self.message_user(request, f"Checked-in {updated} reservation(s)", level=messages.INFO)
    action_check_in.short_description = "Check-in (confirm + set seated_at)"

    def action_check_out(self, request, queryset):
        now = timezone.now()
        updated = self._update_selected(request, queryset.exclude(status__in=[Reservation.STATUS_CANCELLED, Reservation.STATUS_NO_SHOW]), status=Reservation.STATUS_COMPLETED, completed_at=now)
        self.message_user(request, f"Checked-out {updated} reservation(s)", level=messages.INFO)
    action_check_out.short_description = "Check-out (mark completed)"

    def action_mark_no_show(self, request, queryset):
        now = timezone.now()
        updated = self._update_selected(request, queryset.exclude(status__in=[Reservation.STATUS_CANCELLED, Reservation.STATUS_COMPLETED]), status=Reservation.STATUS_NO_SHOW)
        self.message_user(request, f"Marked {updated} as no-show", level=messages.WARNING)
    action_mark_no_show.short_description = "Mark as No-Show"

    def action_mark_deposit_paid(self, request, queryset):
        updated = self._update_selected(request, queryset.filter(deposit_amount__gt=0), deposit_paid=True)
        self.message_user(request, f"Marked deposit as paid for {updated}", level=messages.INFO)
    action_mark_deposit_paid.short_description = "Mark deposit paid"

    def action_mark_deposit_unpaid(self, request, queryset):
        updated = self._update_selected(request, queryset.filter(deposit_amount__gt=0), deposit_paid=False)
        self.message_user(request, f"Marked deposit as unpaid for {updated}", level=messages.INFO)
    action_mark_deposit_unpaid.short_description = "Mark deposit unpaid"

    def action_create_hold(self, request, queryset):
        try:
            from engagement.models import ReservationHold
        except Exception:
            self.message_user(request, "ReservationHold model not available", level=messages.ERROR)
            return
        created = 0
        for r in queryset:
            if not r.table:
                continue
            try:
                # 20-minute default hold
                expires = timezone.now() + timedelta(minutes=20)
                hold, _ = ReservationHold.objects.get_or_create(
                    table=r.table,
                    status=ReservationHold.STATUS_PENDING,
                    defaults={"expires_at": expires}
                )
                if hold.expires_at < expires:
                    hold.expires_at = expires
                    hold.save(update_fields=["expires_at"])
                created += 1
            except Exception:
                continue
        self.message_user(request, f"Created/extended holds for {created} reservation(s)", level=messages.INFO)
    action_create_hold.short_description = "Create/extend 20m hold for table(s)"

    # ----- Floor map admin view -----
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("floor-map/", self.admin_site.admin_view(self.floor_map_view), name="reservations_floor_map"),
            path("live-dashboard/", self.admin_site.admin_view(self.live_dashboard_view), name="reservations_live_dashboard"),
        ]
        return custom + urls

    def floor_map_view(self, request):
        # Filters
        location_id = request.GET.get("location")
        floor = (request.GET.get("floor") or "").strip() or None

        locations = Location.objects.all().order_by("organization__name", "name")
        tables = Table.objects.filter(is_active=True)
        if location_id:
            tables = tables.filter(location_id=location_id)
        if floor:
            # relies on optional Table.floor_name field (if present)
            if hasattr(Table, "floor_name"):
                tables = tables.filter(floor_name=floor)

        # Status coloring: mark as occupied if overlapping reservation exists now
        now = timezone.now()
        active_res = Reservation.objects.filter(start_time__lt=now + timedelta(minutes=90), end_time__gt=now - timedelta(minutes=90)).exclude(status__in=[Reservation.STATUS_CANCELLED, Reservation.STATUS_COMPLETED, Reservation.STATUS_NO_SHOW])
        active_by_table = {r.table_id: r for r in active_res}

        max_x = tables.aggregate(m=Max(getattr(Table, "map_x").attname if hasattr(Table, "map_x") else "id")).get("m") or 0
        max_y = tables.aggregate(m=Max(getattr(Table, "map_y").attname if hasattr(Table, "map_y") else "id")).get("m") or 0

        data = []
        for t in tables.select_related("location"):
            res = active_by_table.get(t.id)
            data.append(
                {
                    "id": t.id,
                    "number": getattr(t, "table_number", t.id),
                    "x": getattr(t, "map_x", 0) or 0,
                    "y": getattr(t, "map_y", 0) or 0,
                    "floor": getattr(t, "floor_name", ""),
                    "occupied": bool(res),
                    "status": res.status if res else "available",
                }
            )

        ctx = dict(
            self.admin_site.each_context(request),
            title="Floor / Table Map",
            locations=locations,
            current_location_id=int(location_id) if location_id and location_id.isdigit() else None,
            floor=floor or "",
            tables=data,
            max_x=max(1, int(max_x) + 1),
            max_y=max(1, int(max_y) + 1),
        )
        return TemplateResponse(request, "admin/reservations/floor_map.html", ctx)

    def live_dashboard_view(self, request):
        """Minimal admin view that embeds the SPA Live Dashboard under /rms-admin/admin/liveDashboard."""
        ctx = dict(
            self.admin_site.each_context(request),
            title="Live Dashboard",
            spa_url="/rms-admin/admin/liveDashboard",
        )
        return TemplateResponse(request, "admin/reservations/live_dashboard.html", ctx)
