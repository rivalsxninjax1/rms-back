from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse

from .models import LoyaltyProfile, LoyaltyRank

# Optional DB-managed discount rules (best-match if present)
try:
    from orders.models import DiscountRule  # type: ignore
except Exception:  # pragma: no cover
    DiscountRule = None  # type: ignore


def _threshold_discount_cents(subtotal_cents: int) -> int:
    """
    Returns the best fixed discount (in cents) for a given subtotal.
    Prefers DB rules if present; otherwise falls back to built-in ladder.
    """
    # Prefer DB DiscountRule if available
    if DiscountRule:
        try:
            rule = (
                DiscountRule.objects.filter(is_active=True, threshold_cents__lte=subtotal_cents)
                .order_by("-discount_cents")
                .first()
            )
            if rule:
                return int(getattr(rule, "discount_cents", 0) or 0)
        except Exception:
            pass

    # Built-in fallback thresholds (edit as needed)
    if subtotal_cents >= 300000:
        return 20000
    if subtotal_cents >= 200000:
        return 10000
    return 0


@login_required
def loyalty_preview(request: HttpRequest) -> JsonResponse:
    """
    Lightweight JSON endpoint used by the cart/checkout UI to preview:
      - the user's loyalty rank + default tip (fixed cents)
      - the applicable fixed discount for a given subtotal (if provided)

    GET params:
      - subtotal_cents (optional int)

    Response:
    {
      "rank": {"code": "gold", "name": "Gold", "tip_cents": 1000} | null,
      "suggested_tip_cents": 1000,
      "discount_cents": 0
    }
    """
    user = request.user
    subtotal_cents_raw = request.GET.get("subtotal_cents")
    try:
        subtotal_cents = int(subtotal_cents_raw) if subtotal_cents_raw is not None else 0
        if subtotal_cents < 0:
            subtotal_cents = 0
    except Exception:
        subtotal_cents = 0

    profile: Optional[LoyaltyProfile] = None
    try:
        profile = LoyaltyProfile.objects.select_related("rank").filter(user=user).first()
    except Exception:
        profile = None

    rank_payload: Optional[Dict[str, Any]] = None
    suggested_tip_cents = 0
    if profile and profile.rank and profile.rank.is_active:
        r: LoyaltyRank = profile.rank
        suggested_tip_cents = int(r.tip_cents or 0)
        rank_payload = {
            "code": r.code,
            "name": r.name,
            "tip_cents": suggested_tip_cents,
        }

    discount_cents = _threshold_discount_cents(subtotal_cents)

    return JsonResponse(
        {
            "rank": rank_payload,
            "suggested_tip_cents": suggested_tip_cents,
            "discount_cents": discount_cents,
        }
    )


@login_required
def ranks_list(request: HttpRequest) -> JsonResponse:
    """
    Return all active loyalty ranks for admin/config UIs.
    Response:
      {"ranks": [{"id":..., "code":"...", "name":"...", "tip_cents":..., "sort_order":...}, ...]}
    """
    ranks: List[LoyaltyRank] = list(LoyaltyRank.objects.filter(is_active=True).order_by("sort_order", "name"))
    data = [
        {
            "id": r.id,
            "code": r.code,
            "name": r.name,
            "tip_cents": int(r.tip_cents or 0),
            "sort_order": int(r.sort_order or 0),
        }
        for r in ranks
    ]
    return JsonResponse({"ranks": data})

