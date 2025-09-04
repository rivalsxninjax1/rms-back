from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import Reservation as CoreReservation
from reservations.models import Reservation as ResReservation


STATUS_MAP = {
    # core -> reservations
    "pending": "pending",
    "confirmed": "confirmed",
    "seated": "confirmed",  # reservations app has no 'seated' state
    "completed": "completed",
    "cancelled": "cancelled",
    "no_show": "no_show",
}


class Command(BaseCommand):
    help = "Copy core.Reservation rows into reservations.Reservation (dry-run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Perform writes. Without this, runs as dry-run.")
        parser.add_argument("--limit", type=int, default=0, help="Limit rows for testing")

    def handle(self, *args, **options):
        apply = options["apply"]
        limit = options["limit"]

        qs = CoreReservation.objects.select_related("table", "service_type", "user", "created_by").order_by("pk")
        if limit:
            qs = qs[:limit]

        created = 0
        updated = 0
        skipped = 0

        for core in qs:
            # Build start/end from date+time+duration
            start_dt = timezone.make_aware(
                timezone.datetime.combine(core.reservation_date, core.reservation_time)
            )
            end_dt = start_dt + timezone.timedelta(minutes=core.duration_minutes)

            status = STATUS_MAP.get(core.status, "pending")

            # Try to match by confirmation_number first
            existing = None
            if core.confirmation_number:
                existing = ResReservation.objects.filter(confirmation_number=core.confirmation_number).first()

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
                status=status,
                deposit_amount=getattr(core, "deposit_amount", 0),
                deposit_paid=getattr(core, "deposit_paid", False),
                deposit_applied=False,
                confirmation_number=getattr(core, "confirmation_number", None),
            )

            if existing:
                if apply:
                    for k, v in payload.items():
                        setattr(existing, k, v)
                    existing.save()
                updated += 1
            else:
                if apply:
                    ResReservation.objects.create(**payload)
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Completed. created={created}, updated={updated}, skipped={skipped}"
        ))
