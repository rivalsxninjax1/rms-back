from django.urls import path

from .consumers import ReportsEventsConsumer

websocket_urlpatterns = [
    path("ws/reports/", ReportsEventsConsumer.as_asgi()),
]

