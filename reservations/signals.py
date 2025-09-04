from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Reservation


@receiver(post_save, sender=Reservation)
def reservation_broadcast(sender, instance: Reservation, created: bool, **kwargs):
    try:
        layer = get_channel_layer()
        if not layer:
            return
        event = "reservation_created" if created else "reservation_updated"
        data = {
            "event": event,
            "reservation_id": getattr(instance, 'id', None),
            "table_id": getattr(instance, 'table_id', None),
            "status": getattr(instance, 'status', None),
            "start_time": getattr(instance, 'start_time', None).isoformat() if getattr(instance, 'start_time', None) else None,
            "end_time": getattr(instance, 'end_time', None).isoformat() if getattr(instance, 'end_time', None) else None,
        }
        async_to_sync(layer.group_send)("reservations", {"type": "broadcast", "data": data})
    except Exception:
        # Keep signals robust
        pass

