from __future__ import annotations

from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError


class Coupon(models.Model):
    """Enhanced coupon model with flexible discount rules and validation."""
    
    DISCOUNT_TYPE_CHOICES = [
        ('PERCENTAGE', 'Percentage'),
        ('FIXED_AMOUNT', 'Fixed Amount'),
        ('FREE_SHIPPING', 'Free Shipping'),
        ('BUY_X_GET_Y', 'Buy X Get Y Free'),
    ]
    
    CUSTOMER_TYPE_CHOICES = [
        ('ALL', 'All Customers'),
        ('NEW_ONLY', 'New Customers Only'),
        ('EXISTING_ONLY', 'Existing Customers Only'),
        ('VIP_ONLY', 'VIP Customers Only'),
    ]
    
    # Basic coupon information
    code = models.CharField(
        max_length=64, 
        unique=True,
        help_text="Unique coupon code (case-insensitive)"
    )
    
    name = models.CharField(
        max_length=128,
        default="Coupon",
        help_text="Internal name for the coupon"
    )
    
    description = models.TextField(
        blank=True,
        max_length=500,
        help_text="Public description shown to customers"
    )
    
    phrase = models.CharField(
        max_length=128, 
        blank=True,
        help_text="Alternative phrase that can be used instead of code"
    )
    
    # Discount configuration
    discount_type = models.CharField(
        max_length=20,
        choices=DISCOUNT_TYPE_CHOICES,
        default='PERCENTAGE',
        help_text="Type of discount to apply"
    )
    
    percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text="Percentage discount (0-100%)"
    )
    
    fixed_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Fixed discount amount"
    )
    
    # Threshold and limits
    minimum_order_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Minimum order amount required to use this coupon"
    )
    
    maximum_discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Maximum discount amount (for percentage discounts)"
    )
    
    # Usage restrictions
    active = models.BooleanField(
        default=True,
        help_text="Whether this coupon is currently active"
    )
    
    valid_from = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When this coupon becomes valid"
    )
    
    valid_to = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When this coupon expires"
    )
    
    max_uses = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Maximum number of times this coupon can be used (total)"
    )
    
    max_uses_per_customer = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of times each customer can use this coupon"
    )
    
    times_used = models.PositiveIntegerField(
        default=0,
        help_text="Number of times this coupon has been used"
    )
    
    # Customer restrictions
    customer_type = models.CharField(
        max_length=20,
        choices=CUSTOMER_TYPE_CHOICES,
        default='ALL',
        help_text="Which type of customers can use this coupon"
    )
    
    first_order_only = models.BooleanField(
        default=False,
        help_text="Whether this coupon can only be used on first orders"
    )
    
    # Stackability
    stackable_with_other_coupons = models.BooleanField(
        default=False,
        help_text="Whether this coupon can be combined with other coupons"
    )
    
    stackable_with_loyalty = models.BooleanField(
        default=True,
        help_text="Whether this coupon can be combined with loyalty discounts"
    )
    
    # Buy X Get Y configuration (for BUY_X_GET_Y type)
    buy_quantity = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of items to buy (for Buy X Get Y offers)"
    )
    
    get_quantity = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of items to get free (for Buy X Get Y offers)"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        null=True, 
        blank=True,
        on_delete=models.SET_NULL, 
        related_name="created_coupons"
    )
    
    created_at = models.DateTimeField(
        default=timezone.now, 
        editable=False
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    
    # Analytics
    total_discount_given = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total discount amount given through this coupon"
    )
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['active', 'valid_from', 'valid_to']),
            models.Index(fields=['discount_type']),
            models.Index(fields=['customer_type']),
        ]
    
    def clean(self):
        """Validate coupon configuration."""
        super().clean()
        
        # Validate discount configuration
        if self.discount_type == 'PERCENTAGE':
            if self.percent <= 0:
                raise ValidationError({'percent': 'Percentage must be greater than 0 for percentage discounts.'})
        elif self.discount_type == 'FIXED_AMOUNT':
            if self.fixed_amount <= 0:
                raise ValidationError({'fixed_amount': 'Fixed amount must be greater than 0 for fixed amount discounts.'})
        elif self.discount_type == 'BUY_X_GET_Y':
            if not self.buy_quantity or not self.get_quantity:
                raise ValidationError('Buy quantity and get quantity are required for Buy X Get Y offers.')
            if self.buy_quantity <= 0 or self.get_quantity <= 0:
                raise ValidationError('Buy quantity and get quantity must be greater than 0.')
        
        # Validate date range
        if self.valid_from and self.valid_to and self.valid_from >= self.valid_to:
            raise ValidationError({'valid_to': 'Valid to date must be after valid from date.'})
        
        # Validate usage limits
        if self.max_uses is not None and self.max_uses <= 0:
            raise ValidationError({'max_uses': 'Maximum uses must be greater than 0.'})
        
        if self.max_uses_per_customer is not None and self.max_uses_per_customer <= 0:
            raise ValidationError({'max_uses_per_customer': 'Maximum uses per customer must be greater than 0.'})
    
    def __str__(self) -> str:
        if self.discount_type == 'PERCENTAGE':
            return f"{self.code} (-{self.percent}%)"
        elif self.discount_type == 'FIXED_AMOUNT':
            return f"{self.code} (-${self.fixed_amount})"
        elif self.discount_type == 'FREE_SHIPPING':
            return f"{self.code} (Free Shipping)"
        elif self.discount_type == 'BUY_X_GET_Y':
            return f"{self.code} (Buy {self.buy_quantity} Get {self.get_quantity})"
        return self.code
    
    def is_valid_now(self) -> bool:
        """Check if coupon is currently valid (basic validation)."""
        if not self.active:
            return False
        
        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False
        
        if self.valid_to and now > self.valid_to:
            return False
        
        if self.max_uses is not None and self.times_used >= self.max_uses:
            return False
        
        # Check if discount configuration is valid
        if self.discount_type == 'PERCENTAGE' and self.percent <= 0:
            return False
        elif self.discount_type == 'FIXED_AMOUNT' and self.fixed_amount <= 0:
            return False
        elif self.discount_type == 'BUY_X_GET_Y' and (not self.buy_quantity or not self.get_quantity):
            return False
        
        return True
    
    def can_be_used_by_customer(self, user, is_first_order=False, previous_usage_count=0):
        """Check if this coupon can be used by a specific customer."""
        if not self.is_valid_now():
            return False, "Coupon is not valid"
        
        # Check customer type restrictions
        if self.customer_type == 'NEW_ONLY' and user and user.is_authenticated:
            # For new customers only, check if user has previous orders
            from orders.models import Order
            if Order.objects.filter(user=user, status__in=['COMPLETED', 'DELIVERED']).exists():
                return False, "This coupon is only valid for new customers"
        
        elif self.customer_type == 'EXISTING_ONLY' and user and user.is_authenticated:
            # For existing customers only, check if user has previous orders
            from orders.models import Order
            if not Order.objects.filter(user=user, status__in=['COMPLETED', 'DELIVERED']).exists():
                return False, "This coupon is only valid for existing customers"
        
        # Check first order restriction
        if self.first_order_only and not is_first_order:
            return False, "This coupon can only be used on your first order"
        
        # Check per-customer usage limit
        if self.max_uses_per_customer is not None and previous_usage_count >= self.max_uses_per_customer:
            return False, f"You have already used this coupon {self.max_uses_per_customer} times"
        
        return True, "Valid"
    
    def calculate_discount(self, order_total, item_count=1):
        """Calculate the discount amount for a given order total."""
        if not self.is_valid_now():
            return Decimal('0.00')
        
        # Check minimum order amount
        if self.minimum_order_amount and order_total < self.minimum_order_amount:
            return Decimal('0.00')
        
        discount = Decimal('0.00')
        
        if self.discount_type == 'PERCENTAGE':
            discount = (order_total * self.percent / Decimal('100')).quantize(Decimal('0.01'))
            # Apply maximum discount limit if set
            if self.maximum_discount_amount and discount > self.maximum_discount_amount:
                discount = self.maximum_discount_amount
        
        elif self.discount_type == 'FIXED_AMOUNT':
            discount = min(self.fixed_amount, order_total)  # Don't exceed order total
        
        elif self.discount_type == 'FREE_SHIPPING':
            # This would need to be handled in the order calculation logic
            # For now, return 0 as shipping is handled separately
            discount = Decimal('0.00')
        
        elif self.discount_type == 'BUY_X_GET_Y':
            # Calculate how many free items customer gets
            if self.buy_quantity and item_count >= self.buy_quantity:
                free_items = (item_count // self.buy_quantity) * self.get_quantity
                # This would need item-specific logic to calculate actual discount
                # For now, return a placeholder
                discount = Decimal('0.00')
        
        return discount.quantize(Decimal('0.01'))
    
    def increment_usage(self, discount_amount=None):
        """Increment usage count and track total discount given."""
        self.times_used += 1
        if discount_amount:
            self.total_discount_given += discount_amount
        self.save(update_fields=['times_used', 'total_discount_given', 'updated_at'])
