from __future__ import annotations

from channels.generic.websocket import AsyncJsonWebsocketConsumer


class ReportsEventsConsumer(AsyncJsonWebsocketConsumer):
    """
    Read-only stream of reporting events (daily sales, audit logs, shift reports).
    Clients receive JSON messages broadcast to group "reports" with a payload:
      { "topic": "daily_sales"|"audit_log"|"shift_report", "data": {...} }
    """

    GROUP = "reports"

    async def connect(self):
        await self.channel_layer.group_add(self.GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, code):  # pragma: no cover - trivial
        await self.channel_layer.group_discard(self.GROUP, self.channel_name)

    async def broadcast(self, event: dict):
        # event: {"type": "broadcast", "data": {...}}
        await self.send_json(event.get("data", {}))

