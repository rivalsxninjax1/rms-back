# FILE: payments/tasks.py
from __future__ import annotations
import logging

from django.apps import apps

logger = logging.getLogger(__name__)

try:
    from celery import shared_task
except Exception:  # Celery not installed; provide a no-op decorator
    def shared_task(*d, **kw):
        def _wrap(fn):
            return fn
        return _wrap

@shared_task
def run_post_payment_hooks_task(order_id: int):
    """
    Celery task wrapper for post-payment hooks.
    This file is safe even if Celery isn't installed (no-op decorator).
    """
    try:
        Order = apps.get_model("orders", "Order")
        order = Order.objects.filter(pk=order_id).first()
        if not order:
            return
        from payments.post_payment import run_post_payment_hooks
        run_post_payment_hooks(order, payment=getattr(order, "payment", None))
    except Exception:
        logger.exception("run_post_payment_hooks_task failed for order %s", order_id)
