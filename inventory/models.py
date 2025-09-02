from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags
import re


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
        indexes = [
            models.Index(fields=['location', 'is_active']),
            models.Index(fields=['condition', 'is_active']),
            models.Index(fields=['last_maintenance']),
            models.Index(fields=['-created_at']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(capacity__gte=1) & models.Q(capacity__lte=50),
                name='valid_inventory_table_capacity'
            ),
            models.CheckConstraint(
                check=models.Q(purchase_cost__isnull=True) | models.Q(purchase_cost__gte=0),
                name='positive_purchase_cost'
            ),
        ]

    def __str__(self) -> str:
        return f"Inventory-{self.location.name}#{self.table_number} ({self.capacity}) - {self.condition}"


class Supplier(models.Model):
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )

    organization = models.ForeignKey(
        "core.Organization", 
        on_delete=models.CASCADE, 
        related_name="suppliers",
        default=1
    )
    name = models.CharField(
        max_length=200,
        help_text="Supplier name (HTML tags will be stripped)"
    )
    contact_person = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Contact person name (HTML tags will be stripped)"
    )
    phone = models.CharField(
        max_length=20, 
        blank=True,
        validators=[phone_regex],
        help_text="Supplier phone number"
    )
    email = models.EmailField(
        blank=True,
        help_text="Supplier email address"
    )
    address = models.TextField(
        blank=True,
        help_text="Supplier address (HTML tags will be stripped)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this supplier is currently active"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        unique_together = [['organization', 'name']]
        indexes = [
            models.Index(fields=['organization', 'is_active']),
            models.Index(fields=['is_active']),
            models.Index(fields=['-created_at']),
        ]

    def clean(self):
        """Validate and sanitize supplier data."""
        super().clean()
        
        # Sanitize text fields
        if self.name:
            self.name = strip_tags(self.name).strip()
            if not self.name:
                raise ValidationError({'name': 'Supplier name cannot be empty after sanitization.'})
            
            # Check for potentially malicious patterns
            if re.search(r'[<>"\'\\/]', self.name):
                raise ValidationError({'name': 'Supplier name contains invalid characters.'})
        
        if self.contact_person:
            self.contact_person = strip_tags(self.contact_person).strip()
            if re.search(r'[<>"\'\\/]', self.contact_person):
                raise ValidationError({'contact_person': 'Contact person name contains invalid characters.'})
        
        if self.address:
            self.address = strip_tags(self.address).strip()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

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
    
    organization = models.ForeignKey(
        "core.Organization", 
        on_delete=models.CASCADE, 
        related_name="inventory_items",
        default=1
    )
    name = models.CharField(
        max_length=200,
        help_text="Item name (HTML tags will be stripped)"
    )
    description = models.TextField(
        blank=True,
        help_text="Item description (HTML tags will be stripped)"
    )
    sku = models.CharField(max_length=100, unique=True)
    unit = models.CharField(
        max_length=10, 
        choices=UNIT_CHOICES, 
        default='PCS',
        help_text="Unit of measurement"
    )
    current_stock = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Current stock quantity"
    )
    minimum_stock = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Minimum stock level for alerts"
    )
    cost_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Cost per unit"
    )
    supplier = models.ForeignKey(
        Supplier, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="items"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this item is currently active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        unique_together = [['organization', 'name'], ['sku']]
        indexes = [
            models.Index(fields=['organization', 'is_active']),
            models.Index(fields=['supplier', 'is_active']),
            models.Index(fields=['sku']),
            models.Index(fields=['unit']),
            models.Index(fields=['-updated_at']),
            # Partial index for low stock items
            models.Index(
                fields=['organization', 'current_stock'],
                condition=models.Q(current_stock__lte=models.F('minimum_stock')),
                name='low_stock_items_idx'
            ),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(current_stock__gte=0),
                name='positive_current_stock'
            ),
            models.CheckConstraint(
                check=models.Q(minimum_stock__gte=0),
                name='positive_minimum_stock'
            ),
            models.CheckConstraint(
                check=models.Q(cost_price__gte=0),
                name='positive_cost_price'
            ),
        ]

    def clean(self):
        """Validate and sanitize inventory item data."""
        super().clean()
        
        # Sanitize text fields
        if self.name:
            self.name = strip_tags(self.name).strip()
            if not self.name:
                raise ValidationError({'name': 'Item name cannot be empty after sanitization.'})
            
            # Check for potentially malicious patterns
            if re.search(r'[<>"\'\\/]', self.name):
                raise ValidationError({'name': 'Item name contains invalid characters.'})
        
        if self.description:
            self.description = strip_tags(self.description).strip()
            
        # Validate stock quantities
        if self.current_stock and self.current_stock < 0:
            raise ValidationError({'current_stock': 'Current stock cannot be negative.'})
            
        if self.minimum_stock and self.minimum_stock < 0:
            raise ValidationError({'minimum_stock': 'Minimum stock cannot be negative.'})
            
        if self.cost_price and self.cost_price < 0:
            raise ValidationError({'cost_price': 'Cost price cannot be negative.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.sku})"