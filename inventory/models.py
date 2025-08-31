from django.conf import settings
from django.db import models


class Table(models.Model):
    """
    Inventory Table model for tracking table-related inventory and equipment.
    This tracks tables from an inventory/asset management perspective.
    """
    location = models.ForeignKey(
        "core.Location",
        on_delete=models.CASCADE,
        related_name="inventory_tables",
    )
    table_number = models.CharField(max_length=50)
    capacity = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    condition = models.CharField(
        max_length=20,
        choices=[
            ('excellent', 'Excellent'),
            ('good', 'Good'),
            ('fair', 'Fair'),
            ('needs_repair', 'Needs Repair'),
            ('out_of_service', 'Out of Service'),
        ],
        default='good'
    )
    last_maintenance = models.DateField(null=True, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    purchase_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["location", "table_number"]
        ordering = ["location_id", "table_number"]

    def __str__(self) -> str:
        return f"Inventory-{self.location.name}#{self.table_number} ({self.capacity}) - {self.condition}"


class Supplier(models.Model):
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class InventoryItem(models.Model):
    UNIT_CHOICES = [
        ('KG', 'Kilogram'),
        ('G', 'Gram'),
        ('L', 'Liter'),
        ('ML', 'Milliliter'),
        ('PCS', 'Pieces'),
        ('PACK', 'Pack'),
    ]
    
    location = models.ForeignKey('core.Location', on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=100, unique=True)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='PCS')
    current_stock = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    minimum_stock = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.sku})"