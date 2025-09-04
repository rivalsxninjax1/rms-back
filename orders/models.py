from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, List, Any
import uuid
import json
import hashlib
from datetime import timedelta

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from django.utils.html import strip_tags
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.cache import cache

from menu.models import MenuItem, Modifier

User = get_user_model()


def q2(val: Decimal) -> Decimal:
    """Round decimal to 2 places."""
    return Decimal(val).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class Cart(models.Model):
    """
    Enhanced cart model with comprehensive validation, security, and business logic.
    Supports both authenticated users and guest sessions with seamless merging.
    """
    # Cart identification
    cart_uuid = models.UUIDField(
        default=uuid.uuid4,
        db_index=True,
        help_text="Unique cart identifier for API access"
    )
    
    # Owner information
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="carts",
        null=True,
        blank=True,
        help_text="Cart owner (null for guest carts)"
    )
    
    session_key = models.CharField(
        max_length=40,
        blank=True,
        null=True,
        db_index=True,
        help_text="Session key for anonymous carts"
    )
    
    # Security and validation
    cart_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 hash of cart contents for integrity validation"
    )
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of cart creator for security tracking"
    )
    
    user_agent = models.TextField(
        blank=True,
        help_text="User agent string for fraud detection"
    )
    
    # Cart status
    STATUS_ACTIVE = "active"
    STATUS_ABANDONED = "abandoned"
    STATUS_CONVERTED = "converted"
    STATUS_EXPIRED = "expired"
    
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_ABANDONED, "Abandoned"),
        (STATUS_CONVERTED, "Converted to Order"),
        (STATUS_EXPIRED, "Expired"),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        help_text="Current cart status"
    )
    
    # Service options
    DELIVERY_DINE_IN = "DINE_IN"
    DELIVERY_PICKUP = "PICKUP"
    DELIVERY_DELIVERY = "DELIVERY"
    
    DELIVERY_CHOICES = [
        (DELIVERY_DINE_IN, "Dine-in"),
        (DELIVERY_PICKUP, "Pickup"),
        (DELIVERY_DELIVERY, "Delivery"),
    ]
    
    delivery_option = models.CharField(
        max_length=16,
        choices=DELIVERY_CHOICES,
        default=DELIVERY_PICKUP,
        help_text="Service type for this cart"
    )

    table = models.ForeignKey(
        "core.Table",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="carts",
        help_text="Assigned table for dine-in orders"
    )
    
    # Delivery information
    delivery_address = models.JSONField(
        default=dict,
        blank=True,
        help_text="Delivery address details (street, city, postal_code, etc.)"
    )
    
    delivery_instructions = models.TextField(
        blank=True,
        max_length=500,
        help_text="Special delivery instructions"
    )
    
    estimated_delivery_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Estimated delivery/pickup time"
    )
    
    # Customer information for guest orders
    customer_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Customer name for guest orders"
    )
    
    customer_phone = models.CharField(
        max_length=20,
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^[\+]?[1-9]?[0-9]{7,15}$',
                message="Phone number must be valid format"
            )
        ],
        help_text="Customer phone number"
    )
    
    customer_email = models.EmailField(
        blank=True,
        help_text="Customer email for order updates"
    )
    
    # Financial fields
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Cart subtotal before modifiers and fees"
    )

    modifier_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total modifier adjustments (can be negative)"
    )

    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Applied discount amount"
    )
    
    # Coupon and promotion support
    applied_coupon_code = models.CharField(
        max_length=50,
        blank=True,
        help_text="Applied coupon code"
    )
    
    coupon_discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Discount from applied coupon"
    )
    
    loyalty_discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Loyalty program discount"
    )

    tip_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Tip amount"
    )
    
    tip_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('100.00'))
        ],
        help_text="Tip percentage (0-100%)"
    )

    delivery_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Delivery fee amount"
    )
    
    service_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Service fee amount"
    )

    tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Calculated tax amount"
    )
    
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.0000'),
        validators=[
            MinValueValidator(Decimal('0.0000')),
            MaxValueValidator(Decimal('1.0000'))
        ],
        help_text="Tax rate applied (0.0000-1.0000)"
    )

    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Final cart total"
    )
    
    # Additional information
    notes = models.TextField(
        blank=True,
        max_length=1000,
        help_text="Cart-level notes and special instructions"
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional cart metadata (promo codes, referrals, etc.)"
    )
    
    # Analytics and tracking
    item_count = models.PositiveIntegerField(
        default=0,
        help_text="Cached count of items in cart"
    )
    
    modification_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times cart has been modified"
    )
    
    SOURCE_WEB = 'web'
    SOURCE_MOBILE = 'mobile'
    SOURCE_ADMIN = 'admin'
    SOURCE_WAITER = 'waiter'
    SOURCE_CHOICES = [
        (SOURCE_WEB, 'Web'),
        (SOURCE_MOBILE, 'Mobile'),
        (SOURCE_ADMIN, 'Admin'),
        (SOURCE_WAITER, 'Waiter'),
    ]
    source = models.CharField(
        max_length=50,
        choices=SOURCE_CHOICES,
        default=SOURCE_WEB,
        help_text="Cart creation source (web, mobile, admin, waiter)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Cart expiration time"
    )
    
    converted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When cart was converted to order"
    )
    
    abandoned_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When cart was marked as abandoned"
    )
    
    class Meta:
        verbose_name = "Shopping Cart"
        verbose_name_plural = "Shopping Carts"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user", "status", "-updated_at"]),
            models.Index(fields=["session_key", "status"]),
            models.Index(fields=["cart_uuid"]),
            models.Index(fields=["status", "-last_activity"]),
            models.Index(fields=["table", "status"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["delivery_option", "status"]),
            models.Index(fields=["applied_coupon_code"]),
            models.Index(fields=["ip_address", "-created_at"]),
            models.Index(fields=["source", "-created_at"]),
            models.Index(fields=["-total", "status"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(subtotal__gte=0),
                name="positive_cart_subtotal"
            ),
            models.CheckConstraint(
                check=models.Q(discount_amount__gte=0),
                name="positive_cart_discount"
            ),
            models.CheckConstraint(
                check=models.Q(coupon_discount__gte=0),
                name="positive_cart_coupon_discount"
            ),
            models.CheckConstraint(
                check=models.Q(loyalty_discount__gte=0),
                name="positive_cart_loyalty_discount"
            ),
            models.CheckConstraint(
                check=models.Q(tip_amount__gte=0),
                name="positive_cart_tip"
            ),
            models.CheckConstraint(
                check=models.Q(delivery_fee__gte=0),
                name="positive_cart_delivery_fee"
            ),
            models.CheckConstraint(
                check=models.Q(service_fee__gte=0),
                name="positive_cart_service_fee"
            ),
            models.CheckConstraint(
                check=models.Q(tax_amount__gte=0),
                name="positive_cart_tax_amount"
            ),
            models.CheckConstraint(
                check=models.Q(total__gte=0),
                name="positive_cart_total"
            ),
            models.CheckConstraint(
                check=models.Q(
                    models.Q(delivery_option="DINE_IN", table__isnull=False) |
                    models.Q(delivery_option__in=["PICKUP", "DELIVERY"], table__isnull=True)
                ),
                name="valid_cart_table_delivery_combination"
            ),
            models.CheckConstraint(
                check=models.Q(
                    models.Q(user__isnull=False) |
                    models.Q(session_key__isnull=False)
                ),
                name="cart_must_have_user_or_session"
            ),
            models.CheckConstraint(
                check=models.Q(tax_rate__gte=0) & models.Q(tax_rate__lte=1),
                name="valid_cart_tax_rate"
            ),
        ]
    
    def clean(self):
        """Enhanced validation with comprehensive business rules."""
        super().clean()
        
        # Validate delivery option and table assignment
        if self.delivery_option == self.DELIVERY_DINE_IN and not self.table:
            raise ValidationError("Dine-in orders must have a table assigned.")
        if self.delivery_option != self.DELIVERY_DINE_IN and self.table:
            raise ValidationError("Only dine-in orders can have a table assigned.")
        
        # Validate delivery address for delivery orders
        if self.delivery_option == self.DELIVERY_DELIVERY:
            if not self.delivery_address or not self.delivery_address.get('street'):
                raise ValidationError("Delivery orders must have a valid delivery address.")
        
        # Validate customer information for guest orders
        if not self.user and self.status == self.STATUS_ACTIVE:
            if not self.customer_name and not self.customer_phone:
                raise ValidationError("Guest carts must have customer name or phone number.")
        
        # Validate coupon application
        if self.applied_coupon_code and self.coupon_discount <= 0:
            raise ValidationError("Applied coupon must have a positive discount amount.")
        
        # Clean text fields
        if self.notes:
            self.notes = strip_tags(self.notes).strip()
        if self.delivery_instructions:
            self.delivery_instructions = strip_tags(self.delivery_instructions).strip()
        if self.customer_name:
            self.customer_name = strip_tags(self.customer_name).strip()
        
        # Ensure either user or session_key is set
        if not self.user and not self.session_key:
            raise ValidationError("Cart must have either a user or session_key.")
    
    @transaction.atomic
    def calculate_totals(self, save=True):
        """Comprehensive cart total calculation with all fees and discounts."""
        items = self.items.select_related('menu_item').all()
        
        # Calculate base subtotal and modifier total
        subtotal = Decimal('0.00')
        modifier_total = Decimal('0.00')
        
        for item in items:
            item_subtotal = item.menu_item.price * item.quantity
            subtotal += item_subtotal
            
            # Calculate modifier costs
            for modifier_data in item.selected_modifiers:
                modifier_id = modifier_data.get('modifier_id')
                modifier_qty = modifier_data.get('quantity', 1)
                try:
                    modifier = Modifier.objects.get(id=modifier_id, is_available=True)
                    modifier_total += modifier.price * modifier_qty * item.quantity
                except Modifier.DoesNotExist:
                    continue
        
        self.subtotal = q2(subtotal)
        self.modifier_total = q2(modifier_total)
        
        # Update item count
        self.item_count = sum(item.quantity for item in items)
        
        # Calculate pre-tax total
        pre_tax_total = self.subtotal + self.modifier_total
        
        # Apply discounts in order of precedence
        total_discount = self.discount_amount + self.coupon_discount + self.loyalty_discount
        discounted_total = max(Decimal('0.00'), pre_tax_total - total_discount)
        
        # Calculate tax on discounted amount
        if self.tax_rate > 0:
            self.tax_amount = q2(discounted_total * self.tax_rate)
        else:
            # Fallback tax calculation if rate not set
            tax_rate = self._get_applicable_tax_rate()
            self.tax_rate = tax_rate
            self.tax_amount = q2(discounted_total * tax_rate)
        
        # Add fees
        total_fees = self.delivery_fee + self.service_fee
        
        # Calculate tip (either fixed amount or percentage)
        if self.tip_percentage and not self.tip_amount:
            # Calculate tip as percentage of pre-tax total
            self.tip_amount = q2((discounted_total * self.tip_percentage) / Decimal('100'))
        
        # Calculate final total
        self.total = discounted_total + self.tax_amount + total_fees + self.tip_amount
        
        # Ensure total is not negative
        if self.total < 0:
            self.total = Decimal("0.00")
        
        # Update cart hash for integrity
        self._update_cart_hash()
        
        # Increment modification count
        self.modification_count += 1
        
        if save:
            self.save(update_fields=[
                "subtotal", "modifier_total", "tax_amount", "tax_rate", 
                "total", "tip_amount", "item_count", "cart_hash", 
                "modification_count", "updated_at"
            ])
    
    def is_expired(self):
        """Check if cart has expired."""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    def set_expiration(self, minutes=30):
        """Set cart expiration time."""
        self.expires_at = timezone.now() + timezone.timedelta(minutes=minutes)
    
    def _get_applicable_tax_rate(self):
        """Get applicable tax rate based on delivery option and location.
        Reads DEFAULT_TAX_RATE from settings; defaults to 0 if unset.
        """
        try:
            from django.conf import settings
            raw = getattr(settings, 'DEFAULT_TAX_RATE', 0) or 0
            return Decimal(str(raw)).quantize(Decimal('0.0000'))
        except Exception:
            return Decimal('0.0000')
    
    def _update_cart_hash(self):
        """Update cart hash for integrity validation."""
        # Create hash from cart contents
        hash_data = {
            'items': [{
                'menu_item_id': item.menu_item.id,
                'quantity': item.quantity,
                'modifiers': item.selected_modifiers,
                'notes': item.notes
            } for item in self.items.all()],
            'subtotal': str(self.subtotal),
            'modifier_total': str(self.modifier_total),
            'total': str(self.total)
        }
        
        hash_string = json.dumps(hash_data, sort_keys=True)
        self.cart_hash = hashlib.sha256(hash_string.encode()).hexdigest()
    
    def validate_cart_integrity(self):
        """Validate cart integrity using stored hash."""
        if not self.cart_hash:
            return True  # No hash to validate against
        
        current_hash = self.cart_hash
        self._update_cart_hash()
        return current_hash == self.cart_hash
    
    def apply_coupon(self, coupon_code, discount_amount):
        """Apply a coupon to the cart."""
        self.applied_coupon_code = coupon_code
        self.coupon_discount = q2(discount_amount)
        self.calculate_totals()
    
    def remove_coupon(self):
        """Remove applied coupon from cart."""
        self.applied_coupon_code = ''
        self.coupon_discount = Decimal('0.00')
        self.calculate_totals()
    
    def set_tip(self, amount=None, percentage=None):
        """Set tip amount or percentage."""
        if amount is not None:
            self.tip_amount = q2(amount)
            self.tip_percentage = None
        elif percentage is not None:
            self.tip_percentage = q2(percentage)
            self.tip_amount = Decimal('0.00')  # Will be calculated in calculate_totals
        
        self.calculate_totals()
    
    def mark_abandoned(self):
        """Mark cart as abandoned for analytics."""
        self.status = self.STATUS_ABANDONED
        self.abandoned_at = timezone.now()
        self.save(update_fields=['status', 'abandoned_at', 'updated_at'])
    
    def mark_converted(self):
        """Mark cart as converted to order."""
        self.status = self.STATUS_CONVERTED
        self.converted_at = timezone.now()
        self.save(update_fields=['status', 'converted_at', 'updated_at'])
    
    def get_analytics_data(self):
        """Get cart analytics data."""
        return {
            'cart_uuid': str(self.cart_uuid),
            'source': self.source,
            'item_count': self.item_count,
            'modification_count': self.modification_count,
            'subtotal': float(self.subtotal),
            'total': float(self.total),
            'delivery_option': self.delivery_option,
            'has_coupon': bool(self.applied_coupon_code),
            'coupon_discount': float(self.coupon_discount),
            'tip_amount': float(self.tip_amount),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'time_to_conversion': (
                (self.converted_at - self.created_at).total_seconds() 
                if self.converted_at else None
            ),
            'is_guest': not bool(self.user)
        }
    
    def can_be_modified(self):
        """Check if cart can still be modified."""
        return self.status == self.STATUS_ACTIVE and not self.is_expired()
    
    def get_estimated_total_with_tax(self):
        """Get estimated total including tax for display purposes."""
        if self.total > 0:
            return self.total
        
        # Calculate estimated total without saving
        temp_cart = Cart()
        temp_cart.subtotal = self.subtotal
        temp_cart.modifier_total = self.modifier_total
        temp_cart.discount_amount = self.discount_amount
        temp_cart.coupon_discount = self.coupon_discount
        temp_cart.loyalty_discount = self.loyalty_discount
        temp_cart.delivery_fee = self.delivery_fee
        temp_cart.service_fee = self.service_fee
        temp_cart.tip_amount = self.tip_amount
        temp_cart.tax_rate = self.tax_rate or temp_cart._get_applicable_tax_rate()
        
        temp_cart.calculate_totals(save=False)
        return temp_cart.total
    
    @classmethod
    def cleanup_expired_carts(cls, days_old=7):
        """Clean up old expired carts."""
        cutoff_date = timezone.now() - timedelta(days=days_old)
        expired_carts = cls.objects.filter(
            status__in=[cls.STATUS_EXPIRED, cls.STATUS_ABANDONED],
            updated_at__lt=cutoff_date
        )
        count = expired_carts.count()
        expired_carts.delete()
        return count
    
    def __str__(self):
        owner = self.user.username if self.user else f"Guest ({self.session_key[:8]}...)"
        return f"Cart {self.cart_uuid} - {owner} - ${self.total}"


class CartItem(models.Model):
    """
    Enhanced cart item model for individual menu items in cart with comprehensive validation and features.
    """
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
        db_index=True,
        help_text="Parent cart"
    )
    
    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.CASCADE,
        related_name="cart_items",
        db_index=True,
        help_text="Menu item being ordered"
    )
    
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(999)],
        help_text="Item quantity (1-999)"
    )
    
    # Store price at time of adding to cart
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Unit price at time of adding to cart"
    )
    
    # Store selected modifiers as JSON
    selected_modifiers = models.JSONField(
        default=list,
        blank=True,
        help_text="Selected modifier IDs and details"
    )
    
    # Special instructions for this item
    notes = models.TextField(
        blank=True,
        max_length=500,
        help_text="Special instructions for this item"
    )
    
    # New fields for enhanced functionality
    item_uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        db_index=True,
        help_text="Unique identifier for this cart item"
    )
    
    modifier_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total cost of selected modifiers"
    )
    
    line_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total line cost (unit_price + modifiers) * quantity"
    )
    
    is_gift = models.BooleanField(
        default=False,
        help_text="Mark item as gift"
    )
    
    gift_message = models.CharField(
        max_length=200,
        blank=True,
        help_text="Gift message for this item"
    )
    
    scheduled_for = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Schedule item for specific time"
    )
    
    # Pricing snapshot fields
    original_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Original menu item price at time of adding"
    )
    
    discount_applied = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)],
        help_text="Item-level discount applied"
    )
    
    # Analytics and tracking
    added_via = models.CharField(
        max_length=50,
        default='web',
        choices=[
            ('web', 'Web Interface'),
            ('mobile', 'Mobile App'),
            ('api', 'API'),
            ('pos', 'Point of Sale'),
            ('phone', 'Phone Order')
        ],
        help_text="Source of item addition"
    )
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Cart Item"
        verbose_name_plural = "Cart Items"
        ordering = ["created_at"]
        # Allow same item with different notes or modifiers
        indexes = [
            models.Index(fields=["cart", "menu_item"]),
            models.Index(fields=["menu_item", "created_at"]),
            models.Index(fields=["cart", "created_at"]),
            models.Index(fields=["item_uuid"]),
            models.Index(fields=["cart", "is_gift"]),
            models.Index(fields=["scheduled_for"]),
            models.Index(fields=["added_via", "created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantity__gte=1) & models.Q(quantity__lte=999),
                name="valid_cart_item_quantity"
            ),
            models.CheckConstraint(
                check=models.Q(unit_price__gte=Decimal('0.01')),
                name="positive_cart_item_price"
            ),
            models.CheckConstraint(
                check=models.Q(original_price__gte=Decimal('0.01')),
                name="positive_cart_item_original_price"
            ),
            models.CheckConstraint(
                check=models.Q(discount_applied__gte=0),
                name="positive_cart_item_discount"
            ),
            models.CheckConstraint(
                check=models.Q(modifier_total__gte=0),
                name="positive_cart_item_modifier_total"
            ),
            models.CheckConstraint(
                check=models.Q(line_total__gte=0),
                name="positive_cart_item_line_total"
            ),
        ]
    
    def clean(self):
        super().clean()
        if self.notes:
            self.notes = strip_tags(self.notes).strip()
        
        if self.gift_message:
            self.gift_message = strip_tags(self.gift_message).strip()
        
        # Validate selected modifiers format
        if self.selected_modifiers:
            if not isinstance(self.selected_modifiers, list):
                raise ValidationError({"selected_modifiers": "Must be a list."})
            
            for modifier_data in self.selected_modifiers:
                if not isinstance(modifier_data, dict):
                    raise ValidationError({"selected_modifiers": "Each modifier must be a dictionary."})
                if 'modifier_id' not in modifier_data:
                    raise ValidationError({"selected_modifiers": "Each modifier must have a modifier_id."})
        
        # Validate gift message only if is_gift is True
        if self.is_gift and not self.gift_message:
            raise ValidationError({"gift_message": "Gift message is required for gift items."})
        
        # Validate scheduled time is in the future
        if self.scheduled_for and self.scheduled_for <= timezone.now():
            raise ValidationError({"scheduled_for": "Scheduled time must be in the future."})
    
    def save(self, *args, **kwargs):
        # Set prices from menu item if not provided
        if not self.unit_price:
            self.unit_price = self.menu_item.price
        if not self.original_price:
            self.original_price = self.menu_item.price
        
        # Calculate modifier total and line total
        self.calculate_totals()
        
        self.full_clean()
        super().save(*args, **kwargs)
        
        # Update cart totals after saving
        self.cart.calculate_totals()
        self.cart.save()
    
    def calculate_totals(self):
        """Calculate modifier total and line total for this item."""
        modifier_total = Decimal('0.00')
        
        for modifier_data in self.selected_modifiers:
            modifier_id = modifier_data.get('modifier_id')
            modifier_qty = modifier_data.get('quantity', 1)
            try:
                modifier = Modifier.objects.get(id=modifier_id, is_available=True)
                modifier_total += modifier.price * modifier_qty
            except Modifier.DoesNotExist:
                continue
        
        self.modifier_total = q2(modifier_total)
        
        # Calculate line total: (unit_price - discount + modifiers) * quantity
        item_price = self.unit_price - self.discount_applied
        self.line_total = q2((item_price + self.modifier_total) * self.quantity)
    
    def get_modifier_details(self):
        """Get detailed modifier information with names and prices."""
        modifier_details = []
        
        for modifier_data in self.selected_modifiers:
            modifier_id = modifier_data.get('modifier_id')
            modifier_qty = modifier_data.get('quantity', 1)
            try:
                modifier = Modifier.objects.get(id=modifier_id, is_available=True)
                modifier_details.append({
                    'id': modifier.id,
                    'name': modifier.name,
                    'price': float(modifier.price),
                    'quantity': modifier_qty,
                    'total': float(modifier.price * modifier_qty)
                })
            except Modifier.DoesNotExist:
                continue
        
        return modifier_details
    
    def can_be_modified(self):
        """Check if this item can still be modified."""
        return self.cart.can_be_modified()
    
    def duplicate(self, new_cart=None):
        """Create a duplicate of this cart item."""
        target_cart = new_cart or self.cart
        
        return CartItem.objects.create(
            cart=target_cart,
            menu_item=self.menu_item,
            quantity=self.quantity,
            unit_price=self.unit_price,
            original_price=self.original_price,
            selected_modifiers=self.selected_modifiers.copy(),
            notes=self.notes,
            is_gift=self.is_gift,
            gift_message=self.gift_message,
            scheduled_for=self.scheduled_for,
            discount_applied=self.discount_applied,
            added_via=self.added_via
        )
    
    def apply_discount(self, discount_amount):
        """Apply item-level discount."""
        max_discount = self.unit_price
        self.discount_applied = min(q2(discount_amount), max_discount)
        self.calculate_totals()
        self.save()
    
    def get_analytics_data(self):
        """Get item analytics data."""
        return {
            'item_uuid': str(self.item_uuid),
            'menu_item_id': self.menu_item.id,
            'menu_item_name': self.menu_item.name,
            'quantity': self.quantity,
            'unit_price': float(self.unit_price),
            'original_price': float(self.original_price),
            'modifier_total': float(self.modifier_total),
            'line_total': float(self.line_total),
            'discount_applied': float(self.discount_applied),
            'is_gift': self.is_gift,
            'has_modifiers': len(self.selected_modifiers) > 0,
            'modifier_count': len(self.selected_modifiers),
            'added_via': self.added_via,
            'created_at': self.created_at.isoformat(),
            'is_scheduled': bool(self.scheduled_for)
        }
    
    def delete(self, *args, **kwargs):
        cart = self.cart
        super().delete(*args, **kwargs)
        
        # Update cart totals after deletion
        cart.calculate_totals()
        cart.save()
    
    @property
    def total_price(self):
        """Calculate total price including modifiers (alias for line_total)."""
        return self.line_total
    
    @property
    def effective_unit_price(self):
        """Get unit price after discount."""
        return q2(self.unit_price - self.discount_applied)
    
    @property
    def savings_amount(self):
        """Calculate total savings on this item."""
        original_total = self.original_price * self.quantity
        current_total = self.effective_unit_price * self.quantity
        return q2(original_total - current_total)
    
    @property
    def has_modifiers(self):
        """Check if item has any modifiers."""
        return len(self.selected_modifiers) > 0

    @property
    def extras_total(self):
        """Total extras cost for this line (modifiers per unit × quantity)."""
        try:
            return q2(self.modifier_total * self.quantity)
        except Exception:
            return q2(0)
    
    @property
    def is_scheduled(self):
        """Check if item is scheduled for future."""
        return bool(self.scheduled_for)
    
    def __str__(self):
        gift_indicator = " (Gift)" if self.is_gift else ""
        scheduled_indicator = " (Scheduled)" if self.is_scheduled else ""
        return f"{self.quantity}x {self.menu_item.name}{gift_indicator}{scheduled_indicator} - ${self.line_total}"


# Enhanced Order models for comprehensive order management
class Order(models.Model):
    """
    Enhanced order model with comprehensive tracking, validation, and business logic.
    """
    STATUS_PENDING = "PENDING"
    STATUS_CONFIRMED = "CONFIRMED"
    STATUS_PREPARING = "PREPARING"
    STATUS_READY = "READY"
    STATUS_OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_REFUNDED = "REFUNDED"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending Payment"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_PREPARING, "Preparing"),
        (STATUS_READY, "Ready for Pickup/Delivery"),
        (STATUS_OUT_FOR_DELIVERY, "Out for Delivery"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_REFUNDED, "Refunded"),
    ]

    # Simple workflow aliases for external callers/APIs
    # pending -> in_progress -> served -> completed | cancelled
    VALID_STATUS_TRANSITIONS = {
        'pending': ['in_progress', 'cancelled'],
        'in_progress': ['served', 'cancelled'],
        'served': ['completed', 'cancelled'],
        'completed': [],
        'cancelled': [],
    }

    @staticmethod
    def _simple_to_real(status: str) -> str:
        s = (status or '').strip().lower()
        mapping = {
            'pending': Order.STATUS_PENDING,
            'in_progress': Order.STATUS_PREPARING,
            'served': Order.STATUS_READY,
            'completed': Order.STATUS_COMPLETED,
            'cancelled': Order.STATUS_CANCELLED,
        }
        # If already one of our real enums (case-insensitive), normalize it
        real_values = {v.lower(): v for v in dict(Order.STATUS_CHOICES).keys()}
        if s in real_values:
            return real_values[s]
        return mapping.get(s) or Order.STATUS_PENDING

    @staticmethod
    def _real_to_simple(status: str) -> str:
        s = (status or '').strip().upper()
        mapping = {
            Order.STATUS_PENDING: 'pending',
            Order.STATUS_CONFIRMED: 'in_progress',
            Order.STATUS_PREPARING: 'in_progress',
            Order.STATUS_READY: 'served',
            Order.STATUS_OUT_FOR_DELIVERY: 'in_progress',
            Order.STATUS_COMPLETED: 'completed',
            Order.STATUS_CANCELLED: 'cancelled',
            Order.STATUS_REFUNDED: 'cancelled',  # treat as terminal
        }
        return mapping.get(s, s.lower())

    def transition_to(self, new_status: str, by_user=None):
        """
        Perform a validated status transition and record history + timestamps.
        Accepts either simplified statuses (pending/in_progress/served/...) or
        existing Order.STATUS_* values, case-insensitive.
        """
        from .signals import order_status_changed  # to avoid circulars

        old_real = self.status
        old_simple = self._real_to_simple(old_real)
        new_simple = (new_status or '').strip().lower()
        # Normalize if caller sent an existing enum
        if new_simple in {v.lower() for v in dict(self.STATUS_CHOICES).keys()}:
            new_simple = self._real_to_simple(new_status)

        # Validate transition
        allowed = self.VALID_STATUS_TRANSITIONS.get(old_simple, [])
        if new_simple not in allowed:
            from django.core.exceptions import ValidationError
            raise ValidationError(f"Invalid transition from {old_simple} to {new_simple}")

        # Map to real status and apply
        new_real = self._simple_to_real(new_simple)
        now = timezone.now()

        # Update timestamps based on simplified state
        if new_simple == 'in_progress' and not getattr(self, 'started_preparing_at', None):
            self.started_preparing_at = now
        elif new_simple == 'served' and not getattr(self, 'ready_at', None):
            self.ready_at = now
        elif new_simple == 'completed' and not getattr(self, 'completed_at', None):
            self.completed_at = now
        elif new_simple == 'cancelled' and not getattr(self, 'cancelled_at', None):
            self.cancelled_at = now

        self.status = new_real
        self.save(update_fields=['status', 'started_preparing_at', 'ready_at', 'completed_at', 'cancelled_at', 'updated_at'])

        # Write history
        try:
            OrderStatusHistory.objects.create(
                order=self,
                previous_status=old_real,
                new_status=new_real,
                changed_by=by_user,
            )
        except Exception:
            pass

        # Emit signal
        try:
            order_status_changed.send(sender=Order, order=self, old=old_real, new=new_real, by_user=by_user)
        except Exception:
            pass

    # Core identifiers
    order_uuid = models.UUIDField(
        default=uuid.uuid4,
        db_index=True,
        help_text="Unique order identifier for API access"
    )

    order_number = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        db_index=True,
        help_text="Human-readable order number (auto-generated)"
    )

    # Customer information
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
        db_index=True,
        help_text="Order customer (null for guest orders)"
    )

    # Guest customer details
    customer_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Customer name for guest orders"
    )

    customer_phone = models.CharField(
        max_length=20,
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^[\+]?[1-9]?[0-9]{7,15}$',
                message="Phone number must be valid format"
            )
        ],
        help_text="Customer phone number"
    )

    customer_email = models.EmailField(
        blank=True,
        help_text="Customer email for order updates"
    )

    # Order status and tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
        help_text="Current order status"
    )

    delivery_option = models.CharField(
        max_length=16,
        choices=Cart.DELIVERY_CHOICES,
        default=Cart.DELIVERY_PICKUP,
        db_index=True,
        help_text="Service delivery method"
    )

    table = models.ForeignKey(
        "core.Table",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
        help_text="Assigned table for dine-in orders"
    )

    # Delivery information
    delivery_address = models.JSONField(
        default=dict,
        blank=True,
        help_text="Delivery address details (street, city, zip, etc.)"
    )

    delivery_instructions = models.TextField(
        blank=True,
        max_length=500,
        help_text="Special delivery instructions"
    )

    estimated_delivery_time = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Estimated delivery/pickup time"
    )

    actual_delivery_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Actual delivery/pickup time"
    )
    
    # Financial fields
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Order subtotal before modifiers and fees"
    )

    modifier_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total modifier adjustments (can be negative)"
    )

    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Applied discount amount"
    )

    coupon_discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Discount from applied coupon"
    )

    loyalty_discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Loyalty program discount"
    )

    tip_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Tip amount"
    )

    delivery_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Delivery fee amount"
    )

    service_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Service fee amount"
    )

    tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Calculated tax amount"
    )

    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.0000'),
        validators=[
            MinValueValidator(Decimal('0.0000')),
            MaxValueValidator(Decimal('1.0000'))
        ],
        help_text="Tax rate applied (0.0000-1.0000)"
    )

    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Final order total"
    )

    # Payment information
    payment_method = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('CASH', 'Cash'),
            ('CARD', 'Credit/Debit Card'),
            ('DIGITAL_WALLET', 'Digital Wallet'),
            ('GIFT_CARD', 'Gift Card'),
            ('LOYALTY_POINTS', 'Loyalty Points'),
            ('BANK_TRANSFER', 'Bank Transfer'),
        ],
        help_text="Payment method used"
    )

    payment_status = models.CharField(
        max_length=20,
        default='PENDING',
        choices=[
            ('PENDING', 'Pending'),
            ('PROCESSING', 'Processing'),
            ('COMPLETED', 'Completed'),
            ('FAILED', 'Failed'),
            ('REFUNDED', 'Refunded'),
            ('PARTIALLY_REFUNDED', 'Partially Refunded'),
        ],
        help_text="Payment processing status"
    )

    payment_reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Payment processor reference ID"
    )

    refund_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Total refunded amount"
    )
    
    # Additional information
    notes = models.TextField(
        blank=True,
        max_length=1000,
        help_text="Order-level notes and special instructions"
    )

    applied_coupon_code = models.CharField(
        max_length=50,
        blank=True,
        help_text="Applied coupon code"
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional order metadata"
    )

    # Source tracking
    source_cart = models.ForeignKey(
        Cart,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="converted_orders",
        help_text="Source cart if converted from cart"
    )

    source = models.CharField(
        max_length=50,
        choices=Cart.SOURCE_CHOICES,
        default=Cart.SOURCE_WEB,
        help_text="Order creation source (web, mobile, admin, waiter)"
    )

    # Sales channel for analytics/reporting
    CHANNEL_ONLINE = 'ONLINE'
    CHANNEL_IN_HOUSE = 'IN_HOUSE'
    CHANNEL_CHOICES = [
        (CHANNEL_ONLINE, 'Online'),
        (CHANNEL_IN_HOUSE, 'In-house'),
    ]
    channel = models.CharField(
        max_length=16,
        choices=CHANNEL_CHOICES,
        default=CHANNEL_ONLINE,
        help_text="Sales channel (ONLINE vs IN_HOUSE)"
    )

    # Analytics and tracking
    item_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of items in order"
    )

    preparation_time_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Estimated preparation time in minutes"
    )

    actual_preparation_time = models.DurationField(
        null=True,
        blank=True,
        help_text="Actual time taken to prepare order"
    )

    # Staff assignment
    assigned_to = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_orders",
        help_text="Staff member assigned to handle this order"
    )

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When order was confirmed"
    )
    started_preparing_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When order preparation started"
    )
    ready_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When order was marked ready"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When order was completed"
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When order was cancelled"
    )
    
    class Meta:
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["order_uuid"]),
            models.Index(fields=["order_number"]),
            models.Index(fields=["delivery_option", "status"]),
            models.Index(fields=["table", "status"]),
            models.Index(fields=["payment_status", "-created_at"]),
            models.Index(fields=["assigned_to", "status"]),
            models.Index(fields=["applied_coupon_code"]),
            models.Index(fields=["source", "-created_at"]),
            models.Index(fields=["-total_amount", "status"]),
            models.Index(fields=["estimated_delivery_time"]),
            models.Index(fields=["customer_phone"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(subtotal__gte=0),
                name="positive_order_subtotal"
            ),
            models.CheckConstraint(
                check=models.Q(discount_amount__gte=0),
                name="positive_order_discount"
            ),
            models.CheckConstraint(
                check=models.Q(coupon_discount__gte=0),
                name="positive_order_coupon_discount"
            ),
            models.CheckConstraint(
                check=models.Q(loyalty_discount__gte=0),
                name="positive_order_loyalty_discount"
            ),
            models.CheckConstraint(
                check=models.Q(tip_amount__gte=0),
                name="positive_order_tip"
            ),
            models.CheckConstraint(
                check=models.Q(delivery_fee__gte=0),
                name="positive_order_delivery_fee"
            ),
            models.CheckConstraint(
                check=models.Q(service_fee__gte=0),
                name="positive_order_service_fee"
            ),
            models.CheckConstraint(
                check=models.Q(tax_amount__gte=0),
                name="positive_order_tax_amount"
            ),
            models.CheckConstraint(
                check=models.Q(total_amount__gte=0),
                name="positive_order_total"
            ),
            models.CheckConstraint(
                check=models.Q(refund_amount__gte=0),
                name="positive_order_refund_amount"
            ),
            models.CheckConstraint(
                check=models.Q(refund_amount__lte=models.F('total_amount')),
                name="refund_not_exceeding_total"
            ),
            models.CheckConstraint(
                check=models.Q(
                    models.Q(delivery_option="DINE_IN", table__isnull=False) |
                    models.Q(delivery_option__in=["PICKUP", "DELIVERY"], table__isnull=True)
                ),
                name="valid_order_table_delivery_combination"
            ),
            models.CheckConstraint(
                check=models.Q(tax_rate__gte=0) & models.Q(tax_rate__lte=1),
                name="valid_order_tax_rate"
            ),
        ]
    
    def clean(self):
        """Enhanced validation with comprehensive business rules."""
        super().clean()
        
        # Validate delivery option and table assignment
        if self.delivery_option == Cart.DELIVERY_DINE_IN and not self.table:
            raise ValidationError("Dine-in orders must have a table assigned.")
        if self.delivery_option != Cart.DELIVERY_DINE_IN and self.table:
            raise ValidationError("Only dine-in orders can have a table assigned.")
        
        # Validate delivery address for delivery orders
        if self.delivery_option == Cart.DELIVERY_DELIVERY:
            if not self.delivery_address or not self.delivery_address.get('street'):
                raise ValidationError("Delivery orders must have a valid delivery address.")
        
        # Validate customer information for guest orders
        if not self.user:
            if not self.customer_name and not self.customer_phone:
                raise ValidationError("Guest orders must have customer name or phone number.")
        
        # Validate coupon application
        if self.applied_coupon_code and self.coupon_discount <= 0:
            raise ValidationError("Applied coupon must have a positive discount amount.")
        
        # Clean text fields
        if self.notes:
            self.notes = strip_tags(self.notes).strip()
        if self.delivery_instructions:
            self.delivery_instructions = strip_tags(self.delivery_instructions).strip()
        if self.customer_name:
            self.customer_name = strip_tags(self.customer_name).strip()
    
    def generate_order_number(self):
        """Generate a unique order number."""
        if not self.order_number:
            # Simple format: ORD-YYYYMMDD-XXXX
            date_str = timezone.now().strftime('%Y%m%d')
            last_order = Order.objects.filter(
                order_number__startswith=f'ORD-{date_str}'
            ).order_by('-order_number').first()
            
            if last_order:
                last_num = int(last_order.order_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.order_number = f'ORD-{date_str}-{new_num:04d}'
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            self.generate_order_number()
        
        self.full_clean()
        super().save(*args, **kwargs)
    
    @transaction.atomic
    def calculate_totals(self, save=True):
        """Calculate order totals from items."""
        items = self.items.select_related('menu_item').all()
        
        # Calculate base totals
        subtotal = sum(item.line_total for item in items)
        self.subtotal = q2(subtotal)
        
        # Update item count
        self.item_count = sum(item.quantity for item in items)
        
        # Calculate pre-tax total
        pre_tax_total = self.subtotal + self.modifier_total
        
        # Apply discounts
        total_discount = self.discount_amount + self.coupon_discount + self.loyalty_discount
        discounted_total = max(Decimal('0.00'), pre_tax_total - total_discount)
        
        # Calculate tax
        if self.tax_rate > 0:
            self.tax_amount = q2(discounted_total * self.tax_rate)
        
        # Add fees
        total_fees = self.delivery_fee + self.service_fee
        
        # Calculate final total
        self.total_amount = discounted_total + self.tax_amount + total_fees + self.tip_amount
        
        if save:
            self.save(update_fields=[
                "subtotal", "tax_amount", "total_amount", "item_count", "updated_at"
            ])

    # ---- Convenience helpers for admin/UI compatibility ----
    def items_subtotal(self) -> Decimal:
        """Return subtotal; fallback to computing from items if needed."""
        try:
            sub = Decimal(str(self.subtotal or 0))
            if sub > 0:
                return q2(sub)
        except Exception:
            pass
        # Compute from items if subtotal is zero or missing
        total = Decimal("0.00")
        try:
            for it in self.items.all():
                line = Decimal(str(getattr(it, "line_total", 0) or 0))
                if line <= 0:
                    # fallback: (unit_price * qty) + modifier_total
                    unit = Decimal(str(getattr(it, "unit_price", 0) or 0))
                    qty = int(getattr(it, "quantity", 0) or 0)
                    mods = Decimal(str(getattr(it, "modifier_total", 0) or 0))
                    line = (unit * qty) + mods
                total += line
        except Exception:
            return q2(Decimal("0.00"))
        return q2(total)

    def grand_total(self) -> Decimal:
        """Return final total; compute without saving if not present."""
        try:
            tot = Decimal(str(self.total_amount or 0))
            if tot > 0:
                return q2(tot)
        except Exception:
            pass
        # Compute without persisting
        try:
            self.calculate_totals(save=False)
            return q2(Decimal(str(self.total_amount or 0)))
        except Exception:
            return q2(Decimal("0.00"))
    
    def update_status(self, new_status, user=None, reason="", notes="", request=None):
        """Update order status with timestamp tracking and audit trail."""
        if new_status not in dict(self.STATUS_CHOICES):
            raise ValueError(f"Invalid status: {new_status}")
        
        old_status = self.status
        
        # Skip if status hasn't changed
        if old_status == new_status:
            return
        
        self.status = new_status
        now = timezone.now()
        
        # Update relevant timestamps
        if new_status == self.STATUS_CONFIRMED and not self.confirmed_at:
            self.confirmed_at = now
        elif new_status == self.STATUS_PREPARING and not self.started_preparing_at:
            self.started_preparing_at = now
        elif new_status == self.STATUS_READY and not self.ready_at:
            self.ready_at = now
        elif new_status == self.STATUS_COMPLETED and not self.completed_at:
            self.completed_at = now
        elif new_status == self.STATUS_CANCELLED and not self.cancelled_at:
            self.cancelled_at = now
        
        # Save the order first
        self.save(update_fields=['status', 'confirmed_at', 'started_preparing_at', 
                                'ready_at', 'completed_at', 'cancelled_at', 'updated_at'])
        
        # Create audit trail record
        audit_data = {
            'order': self,
            'previous_status': old_status,
            'new_status': new_status,
            'changed_by': user,
            'change_reason': reason,
            'notes': notes,
        }
        
        # Add request metadata if available
        if request:
            audit_data.update({
                'ip_address': self._get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'metadata': {
                    'request_method': request.method,
                    'request_path': request.path,
                    'session_key': getattr(request.session, 'session_key', None),
                }
            })
        
        # Import here to avoid circular imports
        OrderStatusHistory.objects.create(**audit_data)
    
    def _get_client_ip(self, request):
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def can_be_cancelled(self):
        """Check if order can be cancelled."""
        return self.status in [self.STATUS_PENDING, self.STATUS_CONFIRMED]
    
    def can_be_refunded(self):
        """Check if order can be refunded."""
        return self.payment_status == 'COMPLETED' and self.refund_amount < self.total_amount
    
    def apply_refund(self, amount, reason=""):
        """Apply partial or full refund."""
        if not self.can_be_refunded():
            raise ValidationError("Order cannot be refunded.")
        
        max_refund = self.total_amount - self.refund_amount
        if amount > max_refund:
            raise ValidationError(f"Refund amount cannot exceed {max_refund}")
        
        self.refund_amount += q2(amount)
        
        if self.refund_amount >= self.total_amount:
            self.payment_status = 'REFUNDED'
            self.status = self.STATUS_REFUNDED
        else:
            self.payment_status = 'PARTIALLY_REFUNDED'
        
        self.save(update_fields=['refund_amount', 'payment_status', 'status', 'updated_at'])
    
    def get_preparation_time(self):
        """Get actual preparation time if available."""
        if self.started_preparing_at and self.ready_at:
            return self.ready_at - self.started_preparing_at
        return None
    
    def is_overdue(self):
        """Check if order is overdue based on estimated delivery time."""
        if not self.estimated_delivery_time:
            return False
        return timezone.now() > self.estimated_delivery_time and self.status not in [
            self.STATUS_COMPLETED, self.STATUS_CANCELLED, self.STATUS_REFUNDED
        ]
    
    def get_analytics_data(self):
        """Get order analytics data."""
        return {
            'order_uuid': str(self.order_uuid),
            'order_number': self.order_number,
            'source': self.source,
            'item_count': self.item_count,
            'subtotal': float(self.subtotal),
            'total_amount': float(self.total_amount),
            'delivery_option': self.delivery_option,
            'payment_method': self.payment_method,
            'payment_status': self.payment_status,
            'has_coupon': bool(self.applied_coupon_code),
            'coupon_discount': float(self.coupon_discount),
            'tip_amount': float(self.tip_amount),
            'refund_amount': float(self.refund_amount),
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'preparation_time_seconds': (
                self.get_preparation_time().total_seconds() 
                if self.get_preparation_time() else None
            ),
            'is_guest': not bool(self.user),
            'is_overdue': self.is_overdue()
        }
    
    def get_status_history(self):
        """Get complete status change history for this order."""
        return self.status_history.select_related('changed_by').order_by('-created_at')
    
    def get_latest_status_change(self):
        """Get the most recent status change record."""
        return self.status_history.select_related('changed_by').first()
    
    def get_status_duration(self, status):
        """Get how long the order spent in a specific status."""
        history = list(self.status_history.order_by('created_at'))
        
        start_time = None
        end_time = None
        
        for i, record in enumerate(history):
            if record.new_status == status:
                start_time = record.created_at
            elif record.previous_status == status and start_time:
                end_time = record.created_at
                break
        
        # If status is current and no end time found
        if start_time and not end_time and self.status == status:
            end_time = timezone.now()
        
        if start_time and end_time:
            return end_time - start_time
        
        return None
    
    @classmethod
    def create_from_cart(cls, cart, user=None, notes: str | None = None, delivery_option: str | None = None):
        """Create order from cart with all details. Optionally override user/notes/delivery_option.

        Also sets channel based on delivery option (DINE_IN => IN_HOUSE, else ONLINE),
        ensures initial status is pending, and writes an initial status history entry.
        """
        with transaction.atomic():
            # Compute final delivery option and channel
            deliv = (delivery_option or cart.delivery_option)
            channel = cls.CHANNEL_IN_HOUSE if deliv == Cart.DELIVERY_DINE_IN else cls.CHANNEL_ONLINE

            order = cls.objects.create(
                user=user if user is not None else cart.user,
                customer_name=cart.customer_name,
                customer_phone=cart.customer_phone,
                customer_email=cart.customer_email,
                delivery_option=deliv,
                table=cart.table,
                delivery_address=cart.delivery_address,
                delivery_instructions=cart.delivery_instructions,
                estimated_delivery_time=cart.estimated_delivery_time,
                subtotal=cart.subtotal,
                modifier_total=cart.modifier_total,
                discount_amount=cart.discount_amount,
                coupon_discount=cart.coupon_discount,
                loyalty_discount=cart.loyalty_discount,
                tip_amount=cart.tip_amount,
                delivery_fee=cart.delivery_fee,
                service_fee=cart.service_fee,
                tax_amount=cart.tax_amount,
                tax_rate=cart.tax_rate,
                total_amount=cart.total,
                applied_coupon_code=cart.applied_coupon_code,
                notes=(notes if notes is not None else cart.notes),
                metadata=cart.metadata,
                source_cart=cart,
                source=cart.source,
                item_count=cart.item_count,
                channel=channel,
                status=cls.STATUS_PENDING,
            )

            # Create order items from cart items
            for cart_item in cart.items.all():
                OrderItem.objects.create(
                    order=order,
                    menu_item=cart_item.menu_item,
                    quantity=cart_item.quantity,
                    unit_price=cart_item.unit_price,
                    modifiers=cart_item.get_modifier_details(),
                    notes=cart_item.notes
                )

            # Initial history entry
            try:
                OrderStatusHistory.objects.create(
                    order=order,
                    previous_status=None,
                    new_status=order.status,
                    changed_by=(user if user is not None else cart.user),
                    change_reason="created",
                    notes="Initial status",
                )
            except Exception:
                pass

            # Mark cart as converted
            cart.mark_converted()

            return order
    
    def __str__(self):
        customer = self.user.username if self.user else self.customer_name or f"Guest ({self.customer_phone})"
        return f"Order {self.order_number} - {customer} - ${self.total_amount}"


class OrderItem(models.Model):
    """
    Enhanced order item model for individual menu items in order with comprehensive tracking.
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        db_index=True,
        help_text="Parent order"
    )
    
    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.PROTECT,
        related_name="order_items",
        db_index=True,
        help_text="Menu item being ordered"
    )
    
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(999)],
        help_text="Item quantity (1-999)"
    )
    
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Unit price at time of order creation"
    )
    
    modifiers = models.JSONField(
        default=list,
        blank=True,
        help_text="Selected modifier details with prices"
    )
    
    notes = models.TextField(
        blank=True,
        max_length=500,
        help_text="Special instructions for this item"
    )
    
    # Enhanced fields
    item_uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        db_index=True,
        help_text="Unique identifier for this order item"
    )
    
    modifier_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)],
        help_text="Total cost of selected modifiers"
    )
    
    line_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)],
        help_text="Total line cost (unit_price + modifiers) * quantity"
    )
    
    discount_applied = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)],
        help_text="Item-level discount applied"
    )
    
    is_gift = models.BooleanField(
        default=False,
        help_text="Mark item as gift"
    )
    
    gift_message = models.CharField(
        max_length=200,
        blank=True,
        help_text="Gift message for this item"
    )
    
    # Status tracking
    STATUS_PENDING = "PENDING"
    STATUS_PREPARING = "PREPARING"
    STATUS_READY = "READY"
    STATUS_SERVED = "SERVED"
    STATUS_CANCELLED = "CANCELLED"
    
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PREPARING, "Preparing"),
        (STATUS_READY, "Ready"),
        (STATUS_SERVED, "Served"),
        (STATUS_CANCELLED, "Cancelled"),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        help_text="Item preparation status"
    )
    
    preparation_notes = models.TextField(
        blank=True,
        max_length=300,
        help_text="Kitchen/preparation notes"
    )
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    started_preparing_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When item preparation started"
    )
    ready_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When item was ready"
    )
    served_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When item was served"
    )
    
    class Meta:
        verbose_name = "Order Item"
        verbose_name_plural = "Order Items"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["order", "menu_item"]),
            models.Index(fields=["menu_item", "created_at"]),
            models.Index(fields=["order", "status"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["item_uuid"]),
            models.Index(fields=["is_gift"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantity__gte=1) & models.Q(quantity__lte=999),
                name="valid_order_item_quantity"
            ),
            models.CheckConstraint(
                check=models.Q(unit_price__gte=Decimal('0.01')),
                name="positive_order_item_price"
            ),
            models.CheckConstraint(
                check=models.Q(modifier_total__gte=0),
                name="positive_order_item_modifier_total"
            ),
            models.CheckConstraint(
                check=models.Q(line_total__gte=0),
                name="positive_order_item_line_total"
            ),
            models.CheckConstraint(
                check=models.Q(discount_applied__gte=0),
                name="positive_order_item_discount"
            ),
        ]
    
    def clean(self):
        super().clean()
        if self.notes:
            self.notes = strip_tags(self.notes).strip()
        
        if self.preparation_notes:
            self.preparation_notes = strip_tags(self.preparation_notes).strip()
        
        if self.gift_message:
            self.gift_message = strip_tags(self.gift_message).strip()
        
        # Validate gift message only if is_gift is True
        if self.is_gift and not self.gift_message:
            raise ValidationError({"gift_message": "Gift message is required for gift items."})
    
    def save(self, *args, **kwargs):
        # Calculate totals before saving
        self.calculate_totals()
        
        self.full_clean()
        super().save(*args, **kwargs)
    
    def calculate_totals(self):
        """Calculate modifier total and line total for this item."""
        modifier_total = Decimal('0.00')
        
        for modifier_data in self.modifiers:
            modifier_price = Decimal(str(modifier_data.get('price', '0.00')))
            modifier_qty = modifier_data.get('quantity', 1)
            modifier_total += modifier_price * modifier_qty
        
        self.modifier_total = q2(modifier_total)
        
        # Calculate line total: (unit_price - discount + modifiers) * quantity
        item_price = self.unit_price - self.discount_applied
        self.line_total = q2((item_price + self.modifier_total) * self.quantity)
    
    def update_status(self, new_status, user=None, notes=""):
        """Update item status with timestamp tracking."""
        if new_status not in dict(self.STATUS_CHOICES):
            raise ValueError(f"Invalid status: {new_status}")
        
        old_status = self.status
        
        # Skip if status hasn't changed
        if old_status == new_status:
            return
        
        self.status = new_status
        now = timezone.now()
        
        # Update relevant timestamps
        if new_status == self.STATUS_PREPARING and not self.started_preparing_at:
            self.started_preparing_at = now
        elif new_status == self.STATUS_READY and not self.ready_at:
            self.ready_at = now
        elif new_status == self.STATUS_SERVED and not self.served_at:
            self.served_at = now
        
        self.save(update_fields=['status', 'started_preparing_at', 'ready_at', 'served_at'])
        
        # Create audit trail record for the parent order
        try:
            from django.contrib.contenttypes.models import ContentType
            from reports.models import AuditLog
            
            order_content_type = ContentType.objects.get_for_model(Order)
            AuditLog.objects.create(
                user=user,
                action=f"Item Status Change: {self.menu_item.name}",
                content_type=order_content_type,
                object_id=self.order.id,
                description=f"Item '{self.menu_item.name}' status changed from {old_status} to {new_status}",
                severity='INFO',
                metadata={
                    'item_id': self.id,
                    'item_uuid': str(self.item_uuid),
                    'menu_item_id': self.menu_item.id,
                    'old_status': old_status,
                    'new_status': new_status,
                    'notes': notes,
                }
            )
        except Exception:
            # Silently fail if audit logging fails to not break order processing
            pass
    
    def get_preparation_time(self):
        """Get actual preparation time if available."""
        if self.started_preparing_at and self.ready_at:
            return self.ready_at - self.started_preparing_at
        return None
    
    def apply_discount(self, discount_amount):
        """Apply item-level discount."""
        max_discount = self.unit_price
        self.discount_applied = min(q2(discount_amount), max_discount)
        self.calculate_totals()
        self.save()
    
    def get_analytics_data(self):
        """Get item analytics data."""
        return {
            'item_uuid': str(self.item_uuid),
            'menu_item_id': self.menu_item.id,
            'menu_item_name': self.menu_item.name,
            'quantity': self.quantity,
            'unit_price': float(self.unit_price),
            'modifier_total': float(self.modifier_total),
            'line_total': float(self.line_total),
            'discount_applied': float(self.discount_applied),
            'is_gift': self.is_gift,
            'has_modifiers': len(self.modifiers) > 0,
            'modifier_count': len(self.modifiers),
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'preparation_time_seconds': (
                self.get_preparation_time().total_seconds() 
                if self.get_preparation_time() else None
            )
        }
    
    @property
    def effective_unit_price(self):
        """Get unit price after discount."""
        return q2(self.unit_price - self.discount_applied)
    
    @property
    def has_modifiers(self):
        """Check if item has any modifiers."""
        return len(self.modifiers) > 0
    
    def __str__(self):
        gift_indicator = " (Gift)" if self.is_gift else ""
        return f"{self.quantity}x {self.menu_item.name}{gift_indicator} - ${self.line_total}"


class OrderStatusHistory(models.Model):
    """
    Audit trail model for tracking all order status changes and modifications.
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="status_history",
        db_index=True,
        help_text="Order being tracked"
    )
    
    previous_status = models.CharField(
        max_length=20,
        choices=Order.STATUS_CHOICES,
        null=True,
        blank=True,
        help_text="Previous order status"
    )
    
    new_status = models.CharField(
        max_length=20,
        choices=Order.STATUS_CHOICES,
        help_text="New order status"
    )
    
    changed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="order_status_changes",
        help_text="User who made the status change"
    )
    
    change_reason = models.TextField(
        blank=True,
        max_length=500,
        help_text="Reason for status change"
    )
    
    notes = models.TextField(
        blank=True,
        max_length=1000,
        help_text="Additional notes about the status change"
    )
    
    # System information
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the user making the change"
    )
    
    user_agent = models.TextField(
        blank=True,
        help_text="User agent string for audit purposes"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata about the status change"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When the status change occurred"
    )
    
    class Meta:
        verbose_name = "Order Status History"
        verbose_name_plural = "Order Status Histories"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["order", "-created_at"]),
            models.Index(fields=["new_status", "-created_at"]),
            models.Index(fields=["changed_by", "-created_at"]),
            models.Index(fields=["previous_status", "new_status"]),
        ]
    
    def __str__(self):
        change_desc = f"{self.previous_status or 'None'} → {self.new_status}"
        user_desc = f" by {self.changed_by.username}" if self.changed_by else " (System)"
        return f"Order #{self.order.order_number or self.order.id}: {change_desc}{user_desc}"
