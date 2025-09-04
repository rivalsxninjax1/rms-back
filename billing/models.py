from django.conf import settings
from django.db import models

class Payment(models.Model):
    METHOD_STRIPE = 'stripe'
    METHOD_CASH = 'cash'
    METHOD_POS_CARD = 'pos_card'
    METHOD_CHOICES = [
        (METHOD_STRIPE, 'Stripe'),
        (METHOD_CASH, 'Cash'),
        (METHOD_POS_CARD, 'POS Card'),
    ]

    STATUS_CREATED = 'created'
    STATUS_AUTHORIZED = 'authorized'
    STATUS_CAPTURED = 'captured'
    STATUS_FAILED = 'failed'
    STATUS_REFUNDED = 'refunded'
    STATUS_CHOICES = [
        (STATUS_CREATED, 'Created'),
        (STATUS_AUTHORIZED, 'Authorized'),
        (STATUS_CAPTURED, 'Captured'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_REFUNDED, 'Refunded'),
    ]
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="billing_payments",
        related_query_name="billing_payment",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=8, default="USD")
    method = models.CharField(max_length=16, choices=METHOD_CHOICES, default=METHOD_STRIPE)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_CREATED)
    external_ref = models.CharField(max_length=128, blank=True, null=True)
    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_payments",
    )
    # legacy reference field kept for back-compat with any code reading it
    reference = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        verbose_name = "Billing Payment"
        verbose_name_plural = "Billing Payments"
    def __str__(self):
        return f"BillingPayment {self.pk} for Order {self.order_id} ({self.amount} {self.currency})"

class InvoiceSequence(models.Model):
    prefix = models.CharField(max_length=16, unique=True)
    last_number = models.PositiveIntegerField(default=0)
    class Meta:
        verbose_name = "Invoice Sequence"
        verbose_name_plural = "Invoice Sequences"
    def __str__(self): return f"{self.prefix}-{self.last_number:06d}"
    def next_invoice_no(self) -> str:
        self.last_number += 1
        self.save(update_fields=["last_number"])
        return f"{self.prefix}-{self.last_number:06d}"

class PaymentReceipt(models.Model):
    payment = models.ForeignKey(
        Payment, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="receipts", related_query_name="receipt",
    )
    receipt_no = models.CharField(max_length=32, unique=True, null=True, blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, default="")
    class Meta:
        verbose_name = "Payment Receipt"
        verbose_name_plural = "Payment Receipts"
    def __str__(self):
        return f"Receipt {self.receipt_no or '-'} for BillingPayment {self.payment_id or '-'}"
