from __future__ import annotations

from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone

# Import the real loyalty config model and expose it as LoyaltyTier for
# legacy code that expects engagement.models.LoyaltyTier.
try:
    from loyality.models import TipLoyaltySetting as LoyaltyTier  # noqa: F401
except Exception:
    # If loyality app is not ready yet, define a tiny placeholder so imports don't crash.
    class LoyaltyTier:  # type: ignore
        pass


class OrderExtras(models.Model):
    """
    Lightweight per-order extras row often used to persist supplemental
    charges/credits (e.g., service fees) as discrete records.
    NOTE: Tips & loyalty discounts are still primarily stored on Order itself,
    but this model exists because some pipelines import it.
    """
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="extras")
    name = models.CharField(max_length=64)  # e.g. "tip", "loyalty_discount"
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    meta = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Order Extra"
        verbose_name_plural = "Order Extras"
        indexes = [
            models.Index(fields=["order", "name"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} {self.amount} for order #{getattr(self.order, 'id', '?')}"


class TipLedger(models.Model):
    """
    Optional ledger to track individual tip events for analytics.
    The primary source of truth for current orders remains Order.tip_amount;
    this ledger is additive and safe to keep empty.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="tip_ledgers")
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Tip Ledger Entry"
        verbose_name_plural = "Tip Ledger"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["order"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"Tip {self.amount} for order #{getattr(self.order, 'id', '?')}"


class ReservationHold(models.Model):
    """
    Optional short-lived hold for dine-in tables to prevent double-booking
    during checkout. Some projects already have a Reservation app; this model
    is safe to coexist and can be unused.
    """
    STATUS_PENDING = "PENDING"
    STATUS_CONFIRMED = "CONFIRMED"
    STATUS_EXPIRED = "EXPIRED"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_EXPIRED, "Expired"),
    )

    table = models.ForeignKey("core.Table", on_delete=models.CASCADE, related_name="holds", help_text="Table being held for reservation")
    order = models.ForeignKey("orders.Order", on_delete=models.SET_NULL, null=True, blank=True, related_name="reservation_holds")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Reservation Hold"
        verbose_name_plural = "Reservation Holds"
        indexes = [
            models.Index(fields=["table", "status"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self) -> str:
        return f"Hold {self.status} on table #{getattr(self.table, 'id', '?')} until {self.expires_at:%Y-%m-%d %H:%M}"


class PendingTip(models.Model):
    """
    Optional storage for a user's *pending* tip amount before payment is completed.
    payments/services.py refers to engagement.services.get_pending_tip_for_user,
    which can read from this table. It is safe to have zero rows.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pending_tips")
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Pending Tip"
        verbose_name_plural = "Pending Tips"
        indexes = [
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Pending tip {self.amount} for {getattr(self.user, 'id', '?')}"
