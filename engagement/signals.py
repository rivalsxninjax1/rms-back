from __future__ import annotations
import logging
from decimal import Decimal
from django.dispatch import receiver
from django.db import transaction
from django.utils import timezone

from payments.post_payment import order_paid
from engagement.models import OrderExtras, TipLedger, PendingTip, ReservationHold
from engagement.services import clear_pending_tip

logger = logging.getLogger(__name__)

@receiver(order_paid)
def on_order_paid(sender, order=None, payment=None, request=None, **kwargs):
    """
    Finalization path after Stripe confirms payment:
    - Persist tip to TipLedger
    - Clear pending tip
    - Confirm any ReservationHold for this user/table
    """
    if not order or not getattr(order, "id", None):
        return

    try:
        with transaction.atomic():
            ox, _ = OrderExtras.objects.select_for_update().get_or_create(
                order=order, defaults={"user": order.user}
            )
            tip = Decimal(ox.tip_amount or 0)

            # Record tip ledger (idempotent: one per order)
            if tip > 0 and not hasattr(order, "tip_ledger"):
                TipLedger.objects.create(user=order.user, order=order, amount=tip)

            # Clear pending tip artifacts
            clear_pending_tip(order.user)

            # Auto-confirm pending hold if present
            try:
                hold = (ReservationHold.objects
                        .select_for_update()
                        .filter(user=order.user, status=ReservationHold.STATUS_PENDING)
                        .order_by("-created_at")
                        .first())
                if hold and not hold.is_expired():
                    hold.status = ReservationHold.STATUS_CONFIRMED
                    hold.order = order
                    hold.save(update_fields=["status", "order"])
            except Exception:
                logger.exception("Failed to promote ReservationHold to CONFIRMED for order %s", order.id)
    except Exception:
        logger.exception("Error in post-payment finalization for order %s", order.id)
