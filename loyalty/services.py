from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Tuple

from django.db.models import Sum, Q

from .models import LoyaltyRank, LoyaltyProfile
from orders.models import Order


def _q2(d: Decimal) -> Decimal:
    """Quantize to 2dp safely."""
    return Decimal(str(d or 0)).quantize(Decimal("0.01"))


def _paid_orders_q_for_user(user) -> Q:
    """
    Build a Q() that matches PAID orders for the given user, supporting projects
    that use either 'user' or 'created_by' and either a 'status' flag or 'is_paid' boolean.
    """
    q_user = Q()
    if hasattr(Order, "user"):
        q_user |= Q(user=user)
    if hasattr(Order, "created_by"):
        q_user |= Q(created_by=user)

    q_paid = Q()
    if hasattr(Order, "status"):
        q_paid |= Q(status="PAID")
    if hasattr(Order, "is_paid"):
        q_paid |= Q(is_paid=True)

    return q_user & q_paid


def tip_sum_for_user(user) -> Decimal:
    """
    Sum of PAID tips for this user across orders (tips only; NOT bill totals).
    """
    if not user or not getattr(user, "is_authenticated", False):
        return Decimal("0.00")
    total = (
        Order.objects.filter(_paid_orders_q_for_user(user))
        .aggregate(s=Sum("tip_amount"))
        .get("s") or Decimal("0.00")
    )
    return _q2(total)


@dataclass
class _RewardCandidate:
    """
    Lightweight object representing a reward with .as_discount_amount(subtotal),
    so existing callsites can compute a fixed currency discount safely.
    """
    reward_amount: Decimal  # fixed currency amount only

    def as_discount_amount(self, subtotal: Decimal) -> Decimal:
        subtotal = _q2(subtotal)
        amt = _q2(self.reward_amount)
        if amt > subtotal:
            amt = subtotal
        return amt


def eligible_discount_for_user(user, subtotal: Decimal) -> Tuple[Decimal, Optional[str]]:
    """
    Returns (discount_amount, message or None) using TipLoyaltySetting
    and the user's tip history. Discount is fixed currency, capped to subtotal.
    """
    cfg = TipLoyaltySetting.get_solo()
    if not cfg.active:
        return Decimal("0.00"), None

    sum_tips = tip_sum_for_user(user)
    if sum_tips < _q2(cfg.threshold_tip_total):
        return Decimal("0.00"), None

    discount = _q2(cfg.discount_amount)
    if discount <= 0:
        return Decimal("0.00"), None

    # Cap to subtotal to avoid negative totals
    discount = min(discount, _q2(subtotal))
    msg = cfg.message_template.format(amount=str(discount))
    return discount, msg


# -------- Compatibility shims for existing import sites --------
# Some parts of your code import from "loyalty.services". We provide equivalent
# APIs here and re-export them via a tiny proxy module (loyalty/services.py).

def get_available_reward_for_user(user):
    """
    Compatibility: returns a _RewardCandidate or None if not eligible.
    NOTE: At this stage, we don't have the current subtotal; we return the
    configured fixed discount amount. The caller should cap it against subtotal.
    """
    cfg = TipLoyaltySetting.get_solo()
    if not cfg.active:
        return None
    # Check using a very large subtotal; later the caller caps to actual subtotal.
    discount, _ = eligible_discount_for_user(user, subtotal=Decimal("999999.00"))
    if discount > 0:
        return _RewardCandidate(reward_amount=discount)
    return None


def reserve_reward_for_order(reward: _RewardCandidate, order):
    """
    Compatibility no-op: we don't track reservations for rewards in this tip-based design.
    """
    return None


def redeem_reserved_reward_if_any(order):
    """
    Compatibility no-op: since we don't reserve, there's nothing to redeem.
    """
    return None
