from __future__ import annotations

from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

User = get_user_model()


class Table(models.Model):
    """
    Physical dining table at a specific Location.
    NOTE: This matches the original ZIP schema (Location + table_number uniqueness).
    """
    location = models.ForeignKey(
        "core.Location",
        on_delete=models.CASCADE,
        related_name="tables",
    )
    table_number = models.CharField(max_length=50)
    capacity = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["location", "table_number"]
        ordering = ["location_id", "table_number"]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.location_id}#{self.table_number} ({self.capacity})"


class Reservation(models.Model):
    """
    Reservation for a specific Table and time window.
    - Prevents double-booking via atomic overlap check in save().
    - Keeps a 'reservation_date' (date-only) to support original filterset usage.
    """
    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_CANCELLED = "cancelled"
    STATUS_NO_SHOW = "no_show"
    STATUS_COMPLETED = "completed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_NO_SHOW, "No Show"),
        (STATUS_COMPLETED, "Completed"),
    ]

    location = models.ForeignKey(
        "core.Location",
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    table = models.ForeignKey(
        Table,
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations",
    )

    # Guest-facing fields (optional if user not provided)
    guest_name = models.CharField(max_length=120, blank=True)
    guest_phone = models.CharField(max_length=40, blank=True)
    party_size = models.PositiveIntegerField(default=2)

    # Window
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    # For filter convenience (kept because original code filtered on this)
    reservation_date = models.DateField(editable=False)

    note = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_time", "-id"]
        indexes = [
            models.Index(fields=["location", "table", "start_time"]),
            models.Index(fields=["location", "start_time", "end_time"]),
            models.Index(fields=["reservation_date"]),
        ]

    # ---------------- Validation & overlap prevention ----------------

    def clean(self):
        if self.end_time <= self.start_time:
            raise ValidationError({"end_time": "End time must be after start time."})
        if self.party_size < 1:
            raise ValidationError({"party_size": "Party size must be at least 1."})
        if self.table_id and self.party_size and self.table and self.party_size > self.table.capacity:
            raise ValidationError({"party_size": f"Exceeds table capacity ({self.table.capacity})."})

        # Minimum lead time: 15 minutes; Maximum lead days: 60 (sane defaults since the ZIP had no explicit rule model)
        now = timezone.now()
        min_start = now + timedelta(minutes=15)
        max_start = now + timedelta(days=60)
        if self.start_time < min_start:
            raise ValidationError({"start_time": "Start must be at least 15 minutes from now."})
        if self.start_time > max_start:
            raise ValidationError({"start_time": "Start cannot be more than 60 days in advance."})

    def _overlaps_qs(self) -> models.QuerySet:
        """
        Overlaps on same table in active statuses:
            existing.start < self.end AND existing.end > self.start
        """
        active = [self.STATUS_PENDING, self.STATUS_CONFIRMED]
        return (
            Reservation.objects.select_for_update()
            .filter(
                location=self.location,
                table=self.table,
                status__in=active,
                start_time__lt=self.end_time,
                end_time__gt=self.start_time,
            )
            .exclude(pk=self.pk)
        )

    @transaction.atomic
    def save(self, *args, **kwargs):
        # Keep reservation_date synced with start_time's date
        if self.start_time and timezone.is_aware(self.start_time):
            self.reservation_date = timezone.localtime(self.start_time).date()
        elif self.start_time:
            self.reservation_date = self.start_time.date()

        self.full_clean()

        if self._overlaps_qs().exists():
            raise ValidationError("This table is already booked in the selected time range.")

        super().save(*args, **kwargs)
