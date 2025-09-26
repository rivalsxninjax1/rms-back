from __future__ import annotations

from django.db import models
from django.utils import timezone


class ExternalOrder(models.Model):
    """Mapping between an external platform order and our internal Order.

    provider: 'UBEREATS' | 'DOORDASH'
    external_id: platform order id
    """
    PROVIDER_CHOICES = (
        ("UBEREATS", "Uber Eats"),
        ("DOORDASH", "DoorDash"),
    )

    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, db_index=True)
    external_id = models.CharField(max_length=64, db_index=True)
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="external_refs")
    status = models.CharField(max_length=32, default="pending", db_index=True)
    last_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("provider", "external_id")
        indexes = [
            models.Index(fields=["provider", "status"]),
        ]


class SyncLog(models.Model):
    """Store integration sync events for audit/monitoring."""

    provider = models.CharField(max_length=20, blank=True, default="")
    event = models.CharField(max_length=64, blank=True, default="")
    success = models.BooleanField(default=True)
    message = models.TextField(blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class IntegrationToken(models.Model):
    """Stores OAuth tokens per platform and restaurant/location.

    For production, store tokens encrypted (e.g., using django-fernet-fields or
    a KMS-backed solution). This model is intentionally minimal here with
    placeholders to integrate encryption later.
    """

    PLATFORM_CHOICES = (
        ("UBEREATS", "Uber Eats"),
        ("DOORDASH", "DoorDash"),
        ("GRUBHUB", "Grubhub"),
    )

    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, db_index=True)
    restaurant_id = models.CharField(max_length=64, db_index=True)
    access_token = models.TextField(blank=True, default="")
    refresh_token = models.TextField(blank=True, default="")
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("platform", "restaurant_id")
        indexes = [
            models.Index(fields=["platform", "revoked"]),
            models.Index(fields=["platform", "expires_at"]),
        ]

    def is_expired(self) -> bool:
        return bool(self.expires_at and timezone.now() >= self.expires_at)
