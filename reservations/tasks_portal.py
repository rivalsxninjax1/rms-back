from __future__ import annotations
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from celery import shared_task
from .models import Reservation

@shared_task
def auto_cancel_no_show_reservations():
    """
    Mark PENDING/CONFIRMED reservations as NO_SHOW if now >= start_time + RESERVATION_AUTO_CANCEL_MINUTES.
    """
    now = timezone.now()
    minutes = int(getattr(settings, 'RESERVATION_AUTO_CANCEL_MINUTES', 20) or 20)
    cutoff = now - timedelta(minutes=minutes)
    qs = Reservation.objects.filter(
        status__in=["pending", "confirmed"],
        start_time__lte=cutoff,
    )
    updated = qs.update(status="no_show")
    return updated
