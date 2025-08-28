from __future__ import annotations

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Order(models.Model):
    """
    Lightweight payment/order record that stores *authoritative* amounts in integer cents.
    This model does not interfere with checkout flow if you’re not yet persisting orders,
    but it’s available for webhooks or post-payment bookkeeping.

    Amount conventions (all integer cents in STRIPE_CURRENCY):
      - subtotal_cents: sum of item.unit_amount_cents * qty
      - tip_cents: fixed tip applied (may be rank-based or client-provided, capped >= 0)
      - discount_cents: fixed discount applied (client + threshold ladder; capped >= 0)
      - total_cents: max(0, subtotal_cents + tip_cents - discount_cents)
    """
    STATUS_CHOICES = [
        ("created", "Created"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    # ---- MINIMAL FIX: change related_name to avoid clash with orders.Order.user ----
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_orders",  # was "orders" before; this removes E304/E305 clash
    )
    currency = models.CharField(max_length=10, default="usd")

    subtotal_cents = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    tip_cents = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    discount_cents = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    total_cents = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])

    delivery = models.CharField(
        max_length=20,
        default="DINE_IN",
        help_text='One of: "DINE_IN", "UBER_EATS", "DOORDASH"',
    )

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="created")

    # Stripe references (optional)
    stripe_session_id = models.CharField(max_length=120, blank=True)
    stripe_payment_intent = models.CharField(max_length=120, blank=True)

    # Free-form metadata (JSON string if needed by webhooks)
    meta = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"Order#{self.id or '∅'} {self.status} {self.total_cents}{self.currency}"

    def grand_total(self) -> int:
        return max(0, int(self.subtotal_cents) + int(self.tip_cents) - int(self.discount_cents))


class OrderItem(models.Model):
    """
    Snapshot of a purchased MenuItem at the time of checkout.
    We intentionally duplicate the name and unit_amount_cents for audit accuracy.
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    menu_item_id = models.PositiveIntegerField()  # store original MenuItem PK for reference
    name = models.CharField(max_length=200)
    unit_amount_cents = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    line_total_cents = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])

    class Meta:
        ordering = ["order_id", "id"]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.quantity} × {self.name} ({self.unit_amount_cents}¢)"
