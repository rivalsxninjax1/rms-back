from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import LoyaltyProfile, LoyaltyRank

User = get_user_model()


def _default_rank() -> Optional[LoyaltyRank]:
    """
    Pick a default rank for new users (if one exists).
    Preference order:
      1) code='bronze' (common baseline)
      2) the lowest sort_order active rank
      3) None
    """
    try:
        rank = LoyaltyRank.objects.filter(is_active=True, code__iexact="bronze").first()
        if rank:
            return rank
        return LoyaltyRank.objects.filter(is_active=True).order_by("sort_order", "id").first()
    except Exception:
        return None


@receiver(post_save, sender=User)
def ensure_loyalty_profile(sender, instance: User, created: bool, **kwargs):
    """
    Auto-create a LoyaltyProfile for every new user, assigning a sensible default rank
    if configured by the admin. This supports the fixed-tip-by-rank feature without
    manual steps, and it does NOT force any tip at checkout (client choice wins).
    """
    if not created:
        return
    try:
        profile, made = LoyaltyProfile.objects.get_or_create(user=instance)
        if made and profile.rank is None:
            rank = _default_rank()
            if rank:
                profile.rank = rank
                profile.save(update_fields=["rank"])
    except Exception:
        # Be permissive during initial migrations
        pass
