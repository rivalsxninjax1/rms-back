from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class LoyaltyRank(models.Model):
    """
    Admin-configurable loyalty ranks with a FIXED TIP in integer cents.

    Examples:
      code = "bronze", name = "Bronze", tip_cents = 0
      code = "silver", name = "Silver", tip_cents = 500    # $5.00 (or 500¢ in your set currency)
      code = "gold",   name = "Gold",   tip_cents = 1000   # $10.00
    """
    code = models.SlugField(max_length=32, unique=True)
    name = models.CharField(max_length=64)
    tip_cents = models.PositiveIntegerField(default=0, help_text="Fixed tip (integer cents) to suggest for this rank.")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.name} ({self.tip_cents}¢)"


class LoyaltyProfile(models.Model):
    """
    Per-user loyalty profile that assigns a rank.
    If a user has a rank with a non-zero tip_cents, that value is treated as the
    DEFAULT suggested tip for checkout — but the CUSTOMER’S chosen tip always wins.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="loyalty_profile")
    rank = models.ForeignKey(
        LoyaltyRank, on_delete=models.SET_NULL, null=True, blank=True, related_name="members"
    )
    notes = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Loyalty Profile"
        verbose_name_plural = "Loyalty Profiles"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.user_id} → {self.rank.name if self.rank else 'No Rank'}"

    @property
    def tip_cents(self) -> int:
        if self.rank and self.rank.is_active:
            return int(self.rank.tip_cents or 0)
        return 0
