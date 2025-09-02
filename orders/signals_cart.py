# orders/signals_cart.py
from __future__ import annotations
import logging
from typing import Any

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.db import transaction

from orders.models import Cart
from orders.utils.cart import get_or_create_cart, merge_carts

logger = logging.getLogger(__name__)


@receiver(user_logged_in)
@transaction.atomic
def merge_session_cart_on_login(sender, request, user, **kwargs: Any) -> None:
    try:
        if not request.session.session_key:
            return
        source = (
            Cart.objects.select_for_update()
            .filter(session_key=request.session.session_key, status=Cart.STATUS_ACTIVE)
            .first()
        )
        if not source:
            return

        destination = get_or_create_cart(request).cart
        if source.pk == destination.pk:
            return

        summary = merge_carts(source, destination, strategy="increment")
        logger.info(
            "Merged session cart into user cart",
            extra={"user_id": user.id, "session": request.session.session_key, **summary},
        )
        request.session.modified = True
    except Exception as e:  # pragma: no cover
        logger.exception("Cart merge on login failed: %s", e)


@receiver(user_logged_out)
def clear_cart_on_logout(sender, request, user, **kwargs: Any) -> None:
    try:
        if getattr(request, "session", None):
            request.session.modified = True
    except Exception:
        pass
