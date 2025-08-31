from django.conf import settings
from django.db import models


class Table(models.Model):
    """
    Core Table model for centralized table management.
    This serves as the master table registry for the RMS system.
    """
    location = models.ForeignKey(
        "Location",
        on_delete=models.CASCADE,
        related_name="core_tables",
    )
    table_number = models.CharField(max_length=50)
    capacity = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    table_type = models.CharField(
        max_length=20,
        choices=[
            ('dining', 'Dining Table'),
            ('bar', 'Bar Table'),
            ('outdoor', 'Outdoor Table'),
            ('private', 'Private Dining'),
        ],
        default='dining'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["location", "table_number"]
        ordering = ["location_id", "table_number"]

    def __str__(self) -> str:
        return f"Core-{self.location.name}#{self.table_number} ({self.capacity})"


class Organization(models.Model):
    name = models.CharField(max_length=200)
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Location(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='locations')
    name = models.CharField(max_length=200)
    address = models.TextField(blank=True)
    timezone = models.CharField(max_length=50, default='UTC')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.organization.name} - {self.name}"
