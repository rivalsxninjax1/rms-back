from __future__ import annotations

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional


class MenuItemModifierGroup(models.Model):
    """
    Enhanced many-to-many relationship between menu items and modifier groups.
    Provides advanced configuration for modifier group behavior per menu item.
    """
    # Core relationships
    menu_item = models.ForeignKey(
        'menu.MenuItem',
        on_delete=models.CASCADE,
        related_name="modifier_groups",
        help_text="Menu item this modifier group applies to"
    )
    modifier_group = models.ForeignKey(
        'menu.ModifierGroup',
        on_delete=models.CASCADE,
        related_name="menu_items",
        help_text="Modifier group that applies to the menu item"
    )
    
    # Configuration
    is_required = models.BooleanField(
        default=False,
        help_text="Whether this modifier group is required for the menu item"
    )
    is_visible = models.BooleanField(
        default=True,
        help_text="Whether this modifier group is visible for the menu item"
    )
    
    # Override group settings for this specific item
    override_min_selections = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Override minimum selections for this item (null = use group default)"
    )
    override_max_selections = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Override maximum selections for this item (null = use group default)"
    )
    override_selection_type = models.CharField(
        max_length=20,
        choices=[
            ('single', 'Single Selection'),
            ('multiple', 'Multiple Selection'),
            ('exact', 'Exact Count'),
            ('range', 'Range Selection'),
        ],
        blank=True,
        help_text="Override selection type for this item (blank = use group default)"
    )
    
    # Display customization
    custom_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Custom name for this modifier group on this item (blank = use group name)"
    )
    custom_description = models.TextField(
        blank=True,
        max_length=200,
        help_text="Custom description for this modifier group on this item"
    )
    
    # Pricing overrides
    price_multiplier = models.DecimalField(
        max_digits=5,
        decimal_places=3,
        default=Decimal('1.000'),
        validators=[
            MinValueValidator(Decimal('0.000')),
            MaxValueValidator(Decimal('10.000'))
        ],
        help_text="Price multiplier for all modifiers in this group (1.000 = no change)"
    )
    
    # Availability overrides
    available_from = models.TimeField(
        null=True,
        blank=True,
        help_text="Override availability start time for this group on this item"
    )
    available_until = models.TimeField(
        null=True,
        blank=True,
        help_text="Override availability end time for this group on this item"
    )
    available_days = models.JSONField(
        default=list,
        blank=True,
        help_text="Override available days for this group on this item"
    )
    
    # Display and ordering
    sort_order = models.PositiveIntegerField(
        default=0,
        validators=[MaxValueValidator(9999)],
        help_text="Display order for this modifier group on the item (0-9999)"
    )
    
    # Conditional display
    show_when_item_size = models.CharField(
        max_length=50,
        blank=True,
        help_text="Only show this group when item has specific size modifier"
    )
    hide_when_item_size = models.CharField(
        max_length=50,
        blank=True,
        help_text="Hide this group when item has specific size modifier"
    )
    
    # Analytics and metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    usage_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times modifiers from this group were selected"
    )
    last_used = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time a modifier from this group was selected"
    )

    class Meta:
        verbose_name = "Menu Item Modifier Group"
        verbose_name_plural = "Menu Item Modifier Groups"
        ordering = ['menu_item', 'sort_order', 'modifier_group__name']
        indexes = [
            models.Index(fields=['menu_item', 'sort_order']),
            models.Index(fields=['modifier_group', 'is_required']),
            models.Index(fields=['is_visible', 'is_required']),
            models.Index(fields=['-usage_count']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['menu_item', 'modifier_group'],
                name='unique_menu_item_modifier_group'
            ),
            models.CheckConstraint(
                check=models.Q(price_multiplier__gte=Decimal('0.000')) & 
                      models.Q(price_multiplier__lte=Decimal('10.000')),
                name='valid_price_multiplier_range'
            ),
            models.CheckConstraint(
                check=models.Q(available_from__isnull=True) | 
                      models.Q(available_until__isnull=True) |
                      models.Q(available_from__lt=models.F('available_until')),
                name='valid_override_availability_times'
            ),
        ]

    def clean(self):
        """Enhanced validation with business rules."""
        super().clean()
        
        # Ensure both menu item and modifier group are active
        if self.menu_item and not self.menu_item.is_available:
            raise ValidationError({
                'menu_item': 'Cannot assign modifier groups to unavailable menu items.'
            })
        
        if self.modifier_group and not self.modifier_group.is_active:
            raise ValidationError({
                'modifier_group': 'Cannot assign inactive modifier groups to menu items.'
            })
        
        # Validate override selections
        if (self.override_min_selections is not None and 
            self.override_max_selections is not None and
            self.override_min_selections > self.override_max_selections):
            raise ValidationError({
                'override_max_selections': 'Maximum selections must be greater than or equal to minimum selections.'
            })
        
        # Validate availability times
        if self.available_from and self.available_until:
            if self.available_from >= self.available_until:
                raise ValidationError({
                    'available_until': 'End time must be after start time.'
                })
        
        # Validate available days
        if self.available_days:
            for day in self.available_days:
                if not isinstance(day, int) or day < 0 or day > 6:
                    raise ValidationError({
                        'available_days': 'Days must be integers between 0 (Monday) and 6 (Sunday).'
                    })
        
        # Clean text fields
        if self.custom_name:
            self.custom_name = strip_tags(self.custom_name).strip()
        if self.custom_description:
            self.custom_description = strip_tags(self.custom_description).strip()

    def save(self, *args, **kwargs):
        """Save with validation."""
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        required_str = " (Required)" if self.is_required else ""
        custom_str = f" [{self.custom_name}]" if self.custom_name else ""
        return f"{self.menu_item.name} - {self.modifier_group.name}{custom_str}{required_str}"

    def get_effective_name(self) -> str:
        """Get the effective name to display (custom or group name)."""
        return self.custom_name or self.modifier_group.name

    def get_effective_description(self) -> str:
        """Get the effective description to display."""
        return self.custom_description or self.modifier_group.description

    def get_effective_min_selections(self) -> int:
        """Get the effective minimum selections (override or group default)."""
        if self.override_min_selections is not None:
            return self.override_min_selections
        return self.modifier_group.min_selections

    def get_effective_max_selections(self) -> Optional[int]:
        """Get the effective maximum selections (override or group default)."""
        if self.override_max_selections is not None:
            return self.override_max_selections
        return self.modifier_group.max_selections

    def get_effective_selection_type(self) -> str:
        """Get the effective selection type (override or group default)."""
        return self.override_selection_type or self.modifier_group.selection_type

    def get_modifier_count(self) -> int:
        """Get count of available modifiers in this group."""
        return self.modifier_group.modifiers.filter(is_available=True).count()

    def get_required_selections(self) -> int:
        """Get the required number of selections for this group."""
        if not self.is_required:
            return 0
        return self.get_effective_min_selections() or 1

    def is_available_now(self) -> bool:
        """Check if this modifier group is currently available for the item."""
        if not self.is_visible:
            return False
        
        # Check base modifier group availability
        if not self.modifier_group.is_active:
            return False
        
        # Check override availability times
        if self.available_from and self.available_until:
            now = timezone.now().time()
            if not (self.available_from <= now <= self.available_until):
                return False
        
        # Check override available days
        if self.available_days:
            current_day = timezone.now().weekday()
            if current_day not in self.available_days:
                return False
        
        # If no overrides, check group availability
        if not (self.available_from or self.available_until or self.available_days):
            return self.modifier_group.is_available_now()
        
        return True

    def get_available_modifiers(self):
        """Get available modifiers with price adjustments applied."""
        modifiers = self.modifier_group.modifiers.filter(is_available=True)
        
        # Apply price multiplier if not 1.000
        if self.price_multiplier != Decimal('1.000'):
            for modifier in modifiers:
                modifier.adjusted_price = (modifier.price * self.price_multiplier).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )
        
        return modifiers

    def validate_selections(self, selected_modifiers: List[int]) -> bool:
        """Validate that the selected modifiers meet the group requirements."""
        if not isinstance(selected_modifiers, (list, tuple)):
            selected_modifiers = [selected_modifiers] if selected_modifiers else []
        
        selection_count = len(selected_modifiers)
        
        # Check minimum selections
        min_required = self.get_required_selections()
        if selection_count < min_required:
            raise ValidationError(
                f"At least {min_required} selection(s) required for {self.get_effective_name()}"
            )
        
        # Check maximum selections
        max_allowed = self.get_effective_max_selections()
        if max_allowed and selection_count > max_allowed:
            raise ValidationError(
                f"Maximum {max_allowed} selection(s) allowed for {self.get_effective_name()}"
            )
        
        # Validate that all selected modifiers belong to this group and are available
        valid_modifier_ids = set(
            self.modifier_group.modifiers.filter(is_available=True).values_list('id', flat=True)
        )
        
        for modifier_id in selected_modifiers:
            if modifier_id not in valid_modifier_ids:
                raise ValidationError(
                    f"Invalid modifier selection for {self.get_effective_name()}"
                )
        
        return True

    def calculate_total_price_adjustment(self, selected_modifier_ids: List[int]) -> Decimal:
        """Calculate total price adjustment for selected modifiers."""
        if not selected_modifier_ids:
            return Decimal('0.00')
        
        modifiers = self.modifier_group.modifiers.filter(
            id__in=selected_modifier_ids,
            is_available=True
        )
        
        total = sum(modifier.price for modifier in modifiers)
        
        # Apply price multiplier
        if self.price_multiplier != Decimal('1.000'):
            total *= self.price_multiplier
        
        return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def increment_usage_count(self):
        """Increment usage count and update last used time."""
        MenuItemModifierGroup.objects.filter(pk=self.pk).update(
            usage_count=models.F('usage_count') + 1,
            last_used=timezone.now()
        )

    def get_display_config(self) -> dict:
        """Get comprehensive display configuration for frontend."""
        return {
            'id': self.id,
            'name': self.get_effective_name(),
            'description': self.get_effective_description(),
            'is_required': self.is_required,
            'is_visible': self.is_visible,
            'selection_type': self.get_effective_selection_type(),
            'min_selections': self.get_effective_min_selections(),
            'max_selections': self.get_effective_max_selections(),
            'price_multiplier': float(self.price_multiplier),
            'is_available': self.is_available_now(),
            'modifier_count': self.get_modifier_count(),
            'sort_order': self.sort_order,
        }

    @classmethod
    def get_for_menu_item(cls, menu_item_id: int):
        """Get all modifier groups for a specific menu item."""
        return cls.objects.filter(
            menu_item_id=menu_item_id,
            is_visible=True
        ).select_related('modifier_group').prefetch_related(
            'modifier_group__modifiers'
        ).order_by('sort_order')