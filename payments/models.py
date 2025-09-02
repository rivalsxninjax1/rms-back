from __future__ import annotations

import uuid
from decimal import Decimal

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


class StripePaymentIntent(models.Model):
    """
    Tracks Stripe Payment Intents with comprehensive webhook handling and idempotency.
    Ensures atomic payment processing and prevents duplicate charges.
    """
    
    STATUS_CHOICES = [
        ('requires_payment_method', 'Requires Payment Method'),
        ('requires_confirmation', 'Requires Confirmation'),
        ('requires_action', 'Requires Action'),
        ('processing', 'Processing'),
        ('requires_capture', 'Requires Capture'),
        ('canceled', 'Canceled'),
        ('succeeded', 'Succeeded'),
    ]
    
    # Unique identifier for idempotency
    idempotency_key = models.UUIDField(
        unique=True,
        help_text="Unique key to prevent duplicate payment processing"
    )
    
    # Stripe identifiers
    stripe_payment_intent_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="Stripe Payment Intent ID"
    )
    
    stripe_client_secret = models.CharField(
        max_length=255,
        blank=True,
        help_text="Client secret for frontend confirmation"
    )
    
    # Payment details
    amount_cents = models.PositiveIntegerField(
        validators=[MinValueValidator(50)],  # Stripe minimum is $0.50
        help_text="Payment amount in cents"
    )
    
    currency = models.CharField(
        max_length=3,
        default='usd',
        help_text="ISO currency code"
    )
    
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='requires_payment_method',
        help_text="Current Stripe payment intent status"
    )
    
    # Associated order (can be null for standalone payments)
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stripe_payment_intents',
        help_text="Associated order if applicable"
    )
    
    # User tracking
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stripe_payment_intents',
        help_text="User who initiated the payment"
    )
    
    # Payment method details
    payment_method_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Stripe Payment Method ID"
    )
    
    payment_method_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Payment method type (card, bank_transfer, etc.)"
    )

    # Stripe customer information
    stripe_customer_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Stripe Customer ID for saved payment methods"
    )

    # Additional metadata and tracking
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional payment metadata"
    )
    
    # Webhook processing tracking
    last_webhook_event_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Last processed webhook event ID"
    )
    
    webhook_processing_attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of webhook processing attempts"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When payment was confirmed"
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['stripe_payment_intent_id']),
            models.Index(fields=['idempotency_key']),
            models.Index(fields=['status']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.idempotency_key:
            self.idempotency_key = uuid.uuid4()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"PaymentIntent {self.stripe_payment_intent_id} - {self.status} - ${self.amount_cents/100:.2f}"
    
    @property
    def amount_dollars(self):
        """Convert cents to dollars for display."""
        return Decimal(self.amount_cents) / 100
    
    def is_successful(self):
        """Check if payment was successful."""
        return self.status == 'succeeded'
    
    def is_pending(self):
        """Check if payment is still pending."""
        return self.status in ['requires_payment_method', 'requires_confirmation', 'requires_action', 'processing']
    
    def can_be_canceled(self):
        """Check if payment can be canceled."""
        return self.status in ['requires_payment_method', 'requires_confirmation', 'requires_action']


class StripeWebhookEvent(models.Model):
    """
    Tracks Stripe webhook events for idempotency and audit trail.
    Prevents duplicate processing of webhook events.
    """
    
    # Stripe event details
    stripe_event_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="Stripe event ID"
    )
    
    event_type = models.CharField(
        max_length=100,
        help_text="Stripe event type (e.g., payment_intent.succeeded)"
    )
    
    # Processing status
    processed = models.BooleanField(
        default=False,
        help_text="Whether this event has been successfully processed"
    )
    
    processing_attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of processing attempts"
    )
    
    # Event data
    event_data = models.JSONField(
        help_text="Full Stripe event data"
    )
    
    # Error tracking
    last_error = models.TextField(
        blank=True,
        help_text="Last processing error if any"
    )
    
    # Associated payment intent
    payment_intent = models.ForeignKey(
        StripePaymentIntent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='webhook_events',
        help_text="Associated payment intent if applicable"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When event was successfully processed"
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['stripe_event_id']),
            models.Index(fields=['event_type']),
            models.Index(fields=['processed']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        status = "✓" if self.processed else "⏳"
        return f"{status} {self.event_type} - {self.stripe_event_id}"
    
    def mark_processed(self):
        """Mark event as successfully processed."""
        self.processed = True
        self.processed_at = timezone.now()
        self.save(update_fields=['processed', 'processed_at'])
    
    def increment_attempts(self, error_message=None):
        """Increment processing attempts and optionally log error."""
        self.processing_attempts += 1
        if error_message:
            self.last_error = error_message
        self.save(update_fields=['processing_attempts', 'last_error'])


class PaymentRefund(models.Model):
    """
    Tracks payment refunds with Stripe integration.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
        ('canceled', 'Canceled'),
    ]
    
    # Associated payment intent
    payment_intent = models.ForeignKey(
        StripePaymentIntent,
        on_delete=models.CASCADE,
        related_name='refunds',
        help_text="Original payment intent"
    )
    
    # Stripe refund details
    stripe_refund_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="Stripe refund ID"
    )
    
    amount_cents = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Refund amount in cents"
    )
    
    currency = models.CharField(
        max_length=3,
        help_text="ISO currency code"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Refund status"
    )
    
    reason = models.CharField(
        max_length=100,
        blank=True,
        help_text="Reason for refund"
    )
    
    # Admin details
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='initiated_refunds',
        help_text="Admin user who initiated the refund"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Internal notes about the refund"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When refund was processed by Stripe"
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['stripe_refund_id']),
            models.Index(fields=['status']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"Refund {self.stripe_refund_id} - ${self.amount_cents/100:.2f} - {self.status}"
    
    @property
    def amount_dollars(self):
        """Convert cents to dollars for display."""
        return Decimal(self.amount_cents) / 100


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
