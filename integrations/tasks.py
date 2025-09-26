from __future__ import annotations

from celery import shared_task
from django.utils import timezone
from .providers.ubereats import UberEatsClient
from .providers.doordash import DoorDashClient
from .services import _log


@shared_task(bind=True, max_retries=5, default_retry_delay=30)
def sync_recent_orders_task(self):
    ue = UberEatsClient(); dd = DoorDashClient()
    for prov, client in (('UBEREATS', ue), ('DOORDASH', dd)):
        try:
            res = client.list_orders()
            if res.ok:
                _log(prov, 'list_orders', True, payload={'count': len(res.data) if isinstance(res.data, list) else 0})
            else:
                _log(prov, 'list_orders', False, res.error or '', {})
        except Exception as e:
            _log(prov, 'list_orders', False, f'Exception: {e}', {})

