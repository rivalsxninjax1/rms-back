from __future__ import annotations

from decimal import Decimal
from django.db import models
from django.utils import timezone


class TipLoyaltySetting(models.Model):
    """
    Single-row configuration for tip-based loyalty.

    Fields:
        active: toggle ON/OFF the loyalty discount logic
        threshold_tip_total: when a user's cumulative *tip* reaches this amount,
                             they qualify for the discount (fixed amount)
        discount_amount: fixed currency amount to deduct (not a percent)
        message_template: message shown to the user when discount applies
        updated_at: auto timestamp of last modification

    We expose a convenience classmethod get_solo() to read or create the single row.
    """

    active = models.BooleanField(default=True)
    threshold_tip_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    message_template = models.TextField(
        blank=True,
        default="You are our loyal customer and you get a discount!",
        help_text="Template shown when the loyalty discount applies.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "loyality"
        verbose_name = "Tip Loyalty Setting"
        verbose_name_plural = "Tip Loyalty Settings"

    def __str__(self) -> str:  # pragma: no cover
        return f"LoyaltySettings(active={self.active}, threshold={self.threshold_tip_total}, discount={self.discount_amount})"

    # ---- Singleton helper -------------------------------------------------
    @classmethod
    def get_solo(cls) -> "TipLoyaltySetting":
        """
        Ensure we always have a single row. Returns that row.
        """
        obj, _ = cls.objects.get_or_create(pk=1, defaults={
            "active": True,
            "threshold_tip_total": Decimal("0.00"),
            "discount_amount": Decimal("0.00"),
        })
        return obj

    # ---- Safe accessors ---------------------------------------------------
    @property
    def is_active(self) -> bool:
        return bool(self.active)

    def qualifies(self, total_tip_for_user: Decimal) -> bool:
        """
        Returns True if the user's accumulated TIP total meets the threshold.
        """
        try:
            total_tip_for_user = Decimal(total_tip_for_user or 0)
        except Exception:
            total_tip_for_user = Decimal("0.00")
        return self.active and total_tip_for_user >= (self.threshold_tip_total or Decimal("0.00"))

    def discount_value(self) -> Decimal:
        """
        Fixed currency amount (>= 0).
        """
        try:
            amt = Decimal(self.discount_amount or 0)
        except Exception:
            amt = Decimal("0.00")
        return max(Decimal("0.00"), amt)

    def updated(self):
        self.updated_at = timezone.now()
        self.save(update_fields=["updated_at"])
