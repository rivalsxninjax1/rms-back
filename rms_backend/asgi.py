import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rms_backend.settings')

from core.routing import websocket_urlpatterns as core_ws
try:
    from reports.routing import websocket_urlpatterns as reports_ws
except Exception:
    reports_ws = []

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(
        URLRouter(list(core_ws) + list(reports_ws))
    ),
})
