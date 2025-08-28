# orders/models.py
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from menu.models import MenuItem


def q2(val: Decimal) -> Decimal:
    return Decimal(val).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class Order(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_PAID = "PAID"
    STATUS_FAILED = "FAILED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PAID, "Paid"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders"
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING)
    notes = models.TextField(blank=True, default="")

    # Monetary parts
    tip_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=8, default="NPR")

    # Delivery / dine-in choice
    DELIVERY_DINE_IN = "DINE_IN"
    DELIVERY_UBER_EATS = "UBER_EATS"
    DELIVERY_DOORDASH = "DOORDASH"
    DELIVERY_CHOICES = [
        (DELIVERY_DINE_IN, "Dine-in"),
        (DELIVERY_UBER_EATS, "Uber Eats"),
        (DELIVERY_DOORDASH, "DoorDash"),
    ]
    delivery_option = models.CharField(max_length=16, choices=DELIVERY_CHOICES, default=DELIVERY_DINE_IN)

    # Dine-in table (optional)
    dine_in_table = models.ForeignKey(
        "reservations.Table", null=True, blank=True, on_delete=models.SET_NULL, related_name="orders"
    )

    # Artifacts
    invoice_pdf = models.FileField(upload_to="invoices/", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    # ---- Computation helpers -------------------------------------------------
    def items_subtotal(self) -> Decimal:
        total = Decimal("0.00")
        for it in self.items.all():
            total += it.line_total()
        return q2(total)

    def grand_total(self) -> Decimal:
        subtotal = self.items_subtotal()
        total = subtotal + q2(self.tip_amount) - q2(self.discount_amount)
        if total < 0:
            total = Decimal("0.00")
        return q2(total)

    def is_payable(self) -> bool:
        return self.status == self.STATUS_PENDING and self.items.exists()

    def __str__(self) -> str:  # pragma: no cover
        return f"Order #{self.pk or '-'} ({self.get_status_display()})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    menu_item = models.ForeignKey(MenuItem, related_name="order_items", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    # optional snapshots / notes
    modifiers = models.JSONField(default=list, blank=True)
    notes = models.CharField(max_length=255, blank=True, default="")

    def line_total(self) -> Decimal:
        return q2(Decimal(self.unit_price) * Decimal(int(self.quantity)))

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.menu_item} x {self.quantity}"


# --- Tip Tier & Threshold Discount (Admin-managed) ---------------------------

class TipTier(models.Model):
    """Fixed default tip amount per user rank (e.g., Bronze/Silver/Gold)."""
    RANK_CHOICES = [
        ("BRONZE", "Bronze"),
        ("SILVER", "Silver"),
        ("GOLD", "Gold"),
        ("PLATINUM", "Platinum"),
    ]
    rank = models.CharField(max_length=16, choices=RANK_CHOICES, unique=True)
    default_tip_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        verbose_name = "Tip Tier"
        verbose_name_plural = "Tip Tiers"
        ordering = ["rank"]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.rank} → {self.default_tip_amount}"


class DiscountRule(models.Model):
    """
    Fixed discount thresholds managed by admins.
    """
    threshold_cents = models.PositiveIntegerField(help_text="Minimum spend (in integer cents) to qualify.")
    discount_cents = models.PositiveIntegerField(help_text="Fixed discount (in integer cents) to apply.")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "-threshold_cents", "id"]

    # Expose a default list_display the admin can pick up if desired
    __admin_list_display__ = ("id", "threshold_cents", "discount_cents", "is_active", "sort_order", "created_at")

    def __str__(self) -> str:  # pragma: no cover - trivial
        state = "" if self.is_active else " (inactive)"
        return f"Spend ≥ {self.threshold_cents}¢ → {self.discount_cents}¢ off{state}"
