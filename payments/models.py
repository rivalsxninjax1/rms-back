# payments/models.py
from django.db import models
from django.conf import settings


class Payment(models.Model):
    """One payment record per Order (Stripe-based)."""
    PROVIDER_STRIPE = "stripe"
    PROVIDERS = [
        (PROVIDER_STRIPE, "Stripe"),
    ]

    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="payment",
        db_index=True,
    )
    provider = models.CharField(
        max_length=20,
        choices=PROVIDERS,
        default=PROVIDER_STRIPE,
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(
        max_length=10,
        default=getattr(settings, "STRIPE_CURRENCY", "usd"),
    )
    is_paid = models.BooleanField(default=False)

    # Stripe IDs
    stripe_session_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    stripe_payment_intent = models.CharField(max_length=255, blank=True, default="", db_index=True)

    # Auditing
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment(order={self.order_id}, provider={self.provider}, paid={self.is_paid})"


class StripeEvent(models.Model):
    """
    Stores Stripe webhook events for idempotency/audit.
    Guarantees we only process each event.id once.
    """
    event_id = models.CharField(max_length=255, unique=True, db_index=True)
    event_type = models.CharField(max_length=255)
    payload = models.TextField(blank=True)  # stringified JSON
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.event_type}:{self.event_id}"
