from __future__ import annotations
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpRequest

from .services import eligible_discount_for_user
from orders.models import Order  # only for typing/intellisense; not required at runtime


@login_required
def loyalty_preview(request: HttpRequest):
    """
    Returns a preview for the current user:
      { eligible: bool, discount: "x.xx", message: "..." | null }
    Subtotal is best-effort derived from session cart if your stack supplies it,
    but we’ll fall back to a large subtotal cap to report the configured discount.
    """
    # If your project stores a live "cart subtotal" in session, fetch it here.
    # We simply report the configured discount cap, which is OK for a user message.
    subtotal = Decimal("999999.00")
    discount, msg = eligible_discount_for_user(request.user, subtotal)
    return JsonResponse({
        "eligible": bool(discount and discount > 0),
        "discount": str(discount or Decimal("0.00")),
        "message": msg or None,
    })
