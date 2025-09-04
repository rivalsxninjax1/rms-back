from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Order, OrderItem


def _send(event: dict) -> None:
    try:
        layer = get_channel_layer()
        async_to_sync(layer.group_send)(
            "orders_console",
            {"type": "order_event", "data": event},
        )
    except Exception:
        # Swallow errors so signals don't break saves
        pass


@receiver(post_save, sender=Order)
def orders_broadcast(sender, instance: Order, created: bool, **kwargs):
    evt = {
        "event": "order_created" if created else "order_updated",
        "id": instance.id,
        "status": getattr(instance, "status", None),
        "total_amount": str(getattr(instance, "total_amount", "")),
        "created_at": getattr(instance, "created_at", None).isoformat() if getattr(instance, "created_at", None) else None,
    }
    _send(evt)


@receiver(post_save, sender=OrderItem)
def order_item_broadcast(sender, instance: OrderItem, created: bool, **kwargs):
    try:
        order_id = instance.order_id
    except Exception:
        order_id = None
    evt = {
        "event": "order_item_created" if created else "order_item_updated",
        "order_id": order_id,
        "item_id": instance.id,
    }
    _send(evt)

