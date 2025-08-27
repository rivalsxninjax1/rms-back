from django.core.management.base import BaseCommand
from django.utils import timezone
from reservations.models import ReservationHold


class Command(BaseCommand):
    help = "Expire pending ReservationHold rows whose expires_at is in the past (idempotent)."

    def handle(self, *args, **options):
        now = timezone.now()
        qs = ReservationHold.objects.filter(status="PENDING", expires_at__lte=now)
        count = qs.update(status="EXPIRED")
        self.stdout.write(self.style.SUCCESS(f"Expired {count} holds"))
