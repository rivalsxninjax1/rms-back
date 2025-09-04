from django.urls import path

from .consumers import OrdersEventsConsumer, ReservationsEventsConsumer

websocket_urlpatterns = [
    path("ws/orders/", OrdersEventsConsumer.as_asgi()),
    path("ws/reservations/", ReservationsEventsConsumer.as_asgi()),
]

