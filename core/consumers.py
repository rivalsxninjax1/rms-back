from __future__ import annotations

from channels.generic.websocket import AsyncJsonWebsocketConsumer


class OrdersEventsConsumer(AsyncJsonWebsocketConsumer):
    """
    Public, read-only stream of order events.
    Clients receive JSON messages broadcast to group "orders".
    """

    GROUP = "orders"

    async def connect(self):
        await self.channel_layer.group_add(self.GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, code):  # pragma: no cover - trivial
        await self.channel_layer.group_discard(self.GROUP, self.channel_name)

    async def broadcast(self, event: dict):
        # event: {"type": "broadcast", "data": {...}}
        await self.send_json(event.get("data", {}))


class ReservationsEventsConsumer(AsyncJsonWebsocketConsumer):
    """
    Public, read-only stream of reservation events.
    Clients receive JSON messages broadcast to group "reservations".
    """

    GROUP = "reservations"

    async def connect(self):
        await self.channel_layer.group_add(self.GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, code):  # pragma: no cover - trivial
        await self.channel_layer.group_discard(self.GROUP, self.channel_name)

    async def broadcast(self, event: dict):
        await self.send_json(event.get("data", {}))

