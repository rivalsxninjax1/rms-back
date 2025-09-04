from __future__ import annotations

from channels.generic.websocket import AsyncJsonWebsocketConsumer


class OrdersConsumer(AsyncJsonWebsocketConsumer):
    """
    Lightweight public feed for order update events. No PII is broadcast.
    Frontend should re-fetch details via REST on notifications.
    """

    GROUP = "orders_console"

    async def connect(self):
        await self.channel_layer.group_add(self.GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP, self.channel_name)

    async def order_event(self, event):
        # event = {"type": "order_event", "data": {...}}
        await self.send_json(event.get("data", {}))

