from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from django.conf import settings

from .models import MenuItem


def _mw_enabled() -> bool:
    try:
        return bool(int(getattr(settings, "MIDDLEWARE_ENABLED", 0) or 0))
    except Exception:
        return False


@receiver(post_save, sender=MenuItem)
def on_menu_item_saved(sender, instance: MenuItem, **kwargs):
    if not _mw_enabled():
        return
    try:
        from integrations.middleware import get_middleware_client
        client = get_middleware_client()
        if client.is_configured():
            client.update_item_availability(instance.id, bool(instance.is_available))
    except Exception:
        pass

