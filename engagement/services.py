from __future__ import annotations

from decimal import Decimal
from typing import Optional, Tuple

from django.db import transaction

from .models import PendingTip
from loyalty.services import eligible_discount_for_user


def _q2(x) -> Decimal:
    try:
        return Decimal(str(x or 0)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def get_pending_tip_for_user(user) -> Decimal:
    """
    Returns the most recent *pending* tip amount for this user, or 0.00.
    This satisfies `from engagement.services import get_pending_tip_for_user`
    used in payments/services.py.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return Decimal("0.00")
    row = PendingTip.objects.filter(user=user).order_by("-created_at").first()
    return _q2(row.amount if row else Decimal("0.00"))


def set_pending_tip_for_user(user, amount: Decimal) -> None:
    """
    Optional helper: persist/update a user's pending tip (idempotent enough).
    Not strictly required by payments/services.py, but useful if you call it.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return
    with transaction.atomic():
        PendingTip.objects.create(user=user, amount=_q2(amount))


def clear_pending_tips_for_user(user) -> None:
    """
    Optional helper to clean pending tip rows after payment success.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return
    PendingTip.objects.filter(user=user).delete()


def best_loyalty_discount_for_user(user, subtotal: Decimal) -> Tuple[Decimal, Optional[str]]:
    """
    Computes the tip-based loyalty discount (fixed currency) and a friendly message
    using loyality.services.eligible_discount_for_user. Returns (amount, message).
    """
    subtotal = _q2(subtotal)
    try:
        discount, message = eligible_discount_for_user(user, subtotal=subtotal)
        return _q2(discount), (message or None)
    except Exception:
        return Decimal("0.00"), None


def choose_better_discount(coupon_discount: Decimal, loyalty_discount: Decimal) -> Tuple[Decimal, str]:
    """
    Given two fixed-amount discounts, return the larger one and a label:
      - ("coupon") or ("loyalty") or ("none")
    This mirrors your earlier rule: pick the *greater absolute* discount, no stacking.
    """
    c = _q2(coupon_discount)
    l = _q2(loyalty_discount)
    if l > c and l > 0:
        return l, "loyalty"
    if c > 0:
        return c, "coupon"
    return Decimal("0.00"), "none"
