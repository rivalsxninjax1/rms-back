from __future__ import annotations

from django.db import migrations
from django.utils import timezone


def forward_copy_core_to_reservations(apps, schema_editor):
    CoreReservation = apps.get_model("core", "Reservation")
    ResReservation = apps.get_model("reservations", "Reservation")

    status_map = {
        "pending": "pending",
        "confirmed": "confirmed",
        "cancelled": "cancelled",
        "no_show": "no_show",
        "completed": "completed",
        # core-only statuses mapped to nearest equivalents
        "seated": "confirmed",
    }

    for core in CoreReservation.objects.all().iterator():
        # Build start/end from date+time+duration
        start_dt = timezone.make_aware(
            timezone.datetime.combine(core.reservation_date, core.reservation_time)
        )
        end_dt = start_dt + timezone.timedelta(minutes=getattr(core, "duration_minutes", 120) or 120)

        payload = dict(
            location=core.table.location,
            table=core.table,
            created_by=core.created_by,
            guest_name=core.guest_name,
            guest_phone=core.guest_phone,
            guest_email=getattr(core, "guest_email", ""),
            party_size=core.party_size,
            start_time=start_dt,
            end_time=end_dt,
            reservation_date=core.reservation_date,
            note=getattr(core, "special_requests", ""),
            status=status_map.get(core.status, "pending"),
            deposit_amount=getattr(core, "deposit_amount", 0),
            deposit_paid=getattr(core, "deposit_paid", False),
            # deposit_applied doesn't exist in core; default False
            deposit_applied=False,
            confirmation_number=getattr(core, "confirmation_number", None),
            special_requests=getattr(core, "special_requests", ""),
            internal_notes=getattr(core, "internal_notes", ""),
        )

        # Upsert by confirmation number when present; else create new row
        cn = payload.get("confirmation_number")
        if cn:
            obj, _ = ResReservation.objects.update_or_create(
                confirmation_number=cn,
                defaults=payload,
            )
        else:
            ResReservation.objects.create(**payload)


def reverse_copy_reservations_to_core(apps, schema_editor):
    CoreReservation = apps.get_model("core", "Reservation")
    ResReservation = apps.get_model("reservations", "Reservation")

    status_map = {
        "pending": "pending",
        "confirmed": "confirmed",
        "cancelled": "cancelled",
        "no_show": "no_show",
        "completed": "completed",
    }

    for r in ResReservation.objects.all().iterator():
        # Derive date/time/duration from start/end
        start_dt = r.start_time
        end_dt = r.end_time or (r.start_time + timezone.timedelta(minutes=120))
        # Normalize to aware datetimes for consistency
        if timezone.is_naive(start_dt):
            start_dt = timezone.make_aware(start_dt)
        if timezone.is_naive(end_dt):
            end_dt = timezone.make_aware(end_dt)
        duration = int((end_dt - start_dt).total_seconds() // 60)

        payload = dict(
            user=r.created_by,  # core model uses 'user' optional; best-effort mapping
            guest_name=r.guest_name,
            guest_phone=r.guest_phone,
            guest_email=getattr(r, "guest_email", ""),
            table=r.table,
            service_type=None,
            party_size=r.party_size,
            reservation_date=r.reservation_date,
            reservation_time=start_dt.timetz() if hasattr(start_dt, "timetz") else start_dt.time(),
            duration_minutes=duration,
            status=status_map.get(r.status, "pending"),
            special_requests=getattr(r, "special_requests", r.note or ""),
            internal_notes=getattr(r, "internal_notes", ""),
            deposit_amount=getattr(r, "deposit_amount", 0),
            deposit_paid=getattr(r, "deposit_paid", False),
            confirmation_number=getattr(r, "confirmation_number", None),
            created_by=r.created_by,
        )
        cn = payload.get("confirmation_number")
        if cn:
            CoreReservation.objects.update_or_create(
                confirmation_number=cn,
                defaults=payload,
            )
        else:
            CoreReservation.objects.create(**payload)


class Migration(migrations.Migration):

    dependencies = [
        ("reservations", "0004_extend_reservation_fields"),
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            forward_copy_core_to_reservations,
            reverse_copy_reservations_to_core,
        )
    ]

