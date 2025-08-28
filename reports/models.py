from __future__ import annotations

from django.db import models


class DailySales(models.Model):
    """
    Minimal Daily Sales aggregate so `reports.views` can import and the
    admin/API can read something stable. Amounts are stored in integer cents.
    """
    date = models.DateField(unique=True)
    total_orders = models.PositiveIntegerField(default=0)

    subtotal_cents = models.PositiveIntegerField(default=0)
    tip_cents = models.PositiveIntegerField(default=0)
    discount_cents = models.PositiveIntegerField(default=0)
    total_cents = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self) -> str:  # pragma: no cover
        return f"DailySales {self.date} (orders={self.total_orders})"


class ShiftReport(models.Model):
    """
    Minimal shift report record (non-blocking). Keeps the interface that other
    parts of the code expect: a per-shift roll-up with integer-cents totals.
    """
    SHIFT_CHOICES = [
        ("morning", "Morning"),
        ("afternoon", "Afternoon"),
        ("evening", "Evening"),
        ("night", "Night"),
    ]

    date = models.DateField()
    shift = models.CharField(max_length=16, choices=SHIFT_CHOICES, default="evening")
    staff = models.CharField(max_length=120, blank=True, help_text="Shift lead or cashier")

    orders_count = models.PositiveIntegerField(default=0)
    total_cents = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("date", "shift")]
        ordering = ["-date", "shift", "-id"]

    def __str__(self) -> str:  # pragma: no cover
        return f"ShiftReport {self.date} {self.shift} (orders={self.orders_count})"
