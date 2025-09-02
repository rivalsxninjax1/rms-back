from __future__ import annotations

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags
from django.utils import timezone
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from decimal import Decimal, ROUND_HALF_UP
import re
import uuid
from typing import Dict, List, Optional, Any

# Import the MenuItemModifierGroup model
from .menu_item_modifier_group import MenuItemModifierGroup


class MenuCategory(models.Model):
    """
    Enhanced Menu categories with improved validation, caching, and business logic.
    Supports hierarchical organization with comprehensive validation.
    """
    # Core fields
    organization = models.ForeignKey(
        "core.Organization",
        on_delete=models.CASCADE,
        related_name="menu_categories",
    )
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for external API references"
    )
    name = models.CharField(
        max_length=100,
        help_text="Category name (HTML tags will be stripped)",
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z0-9\s\-&\'".,!()]+$',
                message="Category name contains invalid characters"
            )
        ]
    )
    slug = models.SlugField(
        max_length=120,
        blank=True,
        help_text="URL-friendly version of the name"
    )
    description = models.TextField(
        blank=True,
        max_length=500,
        help_text="Category description (HTML tags will be stripped)"
    )
    
    # Hierarchy
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategories',
        help_text="Parent category for nested categories"
    )
    level = models.PositiveSmallIntegerField(
        default=0,
        validators=[MaxValueValidator(5)],
        help_text="Hierarchy level (0-5, calculated automatically)"
    )
    
    # Media and presentation
    image = models.ImageField(
        upload_to='categories/%Y/%m/',
        null=True,
        blank=True,
        help_text="Category image (optimized automatically)"
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Icon class name for UI display"
    )
    color_theme = models.CharField(
        max_length=7,
        blank=True,
        validators=[RegexValidator(r'^#[0-9A-Fa-f]{6}$', 'Enter a valid hex color')],
        help_text="Theme color for category display"
    )
    
    # Business logic
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this category is currently active"
    )
    is_featured = models.BooleanField(
        default=False,
        help_text="Featured categories appear prominently"
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        validators=[MaxValueValidator(9999)],
        help_text="Display order (0-9999)"
    )
    
    # Availability scheduling
    available_from = models.TimeField(
        null=True,
        blank=True,
        help_text="Daily availability start time"
    )
    available_until = models.TimeField(
        null=True,
        blank=True,
        help_text="Daily availability end time"
    )
    
    # Metadata
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Cached fields for performance
    item_count = models.PositiveIntegerField(
        default=0,
        help_text="Cached count of active items (updated via signals)"
    )
    min_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Minimum item price in category (cached)"
    )
    max_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum item price in category (cached)"
    )

    class Meta:
        verbose_name = "Menu Category"
        verbose_name_plural = "Menu Categories"
        ordering = ['level', 'sort_order', 'name']
        unique_together = [["organization", "name"]]
        indexes = [
            models.Index(fields=["organization", "is_active", "sort_order"]),
            models.Index(fields=['is_active', 'is_featured', 'sort_order']),
            models.Index(fields=['parent', 'sort_order']),
            models.Index(fields=['level', 'sort_order']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['uuid']),
            models.Index(fields=['slug']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(level__gte=0) & models.Q(level__lte=5),
                name='menu_category_valid_level'
            ),
            models.CheckConstraint(
                check=models.Q(available_from__isnull=True) | 
                      models.Q(available_until__isnull=True) |
                      models.Q(available_from__lt=models.F('available_until')),
                name='menu_category_valid_availability_times'
            ),
        ]

    def clean(self):
        """Enhanced validation with business rules."""
        super().clean()
        
        # Strip HTML tags and validate text fields
        if self.name:
            self.name = strip_tags(self.name).strip()
            if not self.name:
                raise ValidationError({'name': 'Category name cannot be empty after removing HTML tags.'})
            if len(self.name) < 2:
                raise ValidationError({'name': 'Category name must be at least 2 characters long.'})
        
        if self.description:
            self.description = strip_tags(self.description).strip()
        
        # Validate hierarchy
        if self.parent:
            if self.parent == self:
                raise ValidationError({'parent': 'A category cannot be its own parent.'})
            
            # Check for circular reference and calculate level
            current = self.parent
            level = 1
            while current:
                if current == self:
                    raise ValidationError({'parent': 'Circular reference detected in category hierarchy.'})
                current = current.parent
                level += 1
                if level > 5:
                    raise ValidationError({'parent': 'Category hierarchy cannot exceed 5 levels.'})
            
            self.level = level
        else:
            self.level = 0
        
        # Validate availability times
        if self.available_from and self.available_until:
            if self.available_from >= self.available_until:
                raise ValidationError({
                    'available_until': 'End time must be after start time.'
                })

    def save(self, *args, **kwargs):
        """Enhanced save with slug generation and validation."""
        # Generate slug if not provided
        if not self.slug and self.name:
            from django.utils.text import slugify
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while MenuCategory.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        
        self.full_clean()
        super().save(*args, **kwargs)
        
        # Update cached fields for parent categories
        self._update_parent_cache()

    def _update_parent_cache(self):
        """Update cached fields for parent categories."""
        if self.parent:
            self.parent.refresh_cached_fields()

    def refresh_cached_fields(self):
        """Refresh cached fields like item_count and price range."""
        active_items = self.get_active_items()
        self.item_count = active_items.count()
        
        if self.item_count > 0:
            prices = active_items.values_list('price', flat=True)
            self.min_price = min(prices)
            self.max_price = max(prices)
        else:
            self.min_price = None
            self.max_price = None
        
        # Save without triggering signals to avoid recursion
        MenuCategory.objects.filter(pk=self.pk).update(
            item_count=self.item_count,
            min_price=self.min_price,
            max_price=self.max_price
        )

    def __str__(self) -> str:
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name

    def get_absolute_url(self):
        """Get the URL for this category."""
        from django.urls import reverse
        return reverse('storefront:category_detail', kwargs={'slug': self.slug})

    def get_full_path(self) -> str:
        """Get the full category path."""
        path = [self.name]
        current = self.parent
        while current:
            path.insert(0, current.name)
            current = current.parent
        return " > ".join(path)

    def get_active_items(self):
        """Get all active menu items in this category."""
        return self.menu_items.filter(is_available=True)

    def get_featured_items(self, limit: int = 6):
        """Get featured items from this category."""
        return self.get_active_items().filter(is_featured=True)[:limit]

    def is_available_now(self) -> bool:
        """Check if category is available at current time."""
        if not self.is_active:
            return False
        
        if not (self.available_from and self.available_until):
            return True
        
        now = timezone.now().time()
        return self.available_from <= now <= self.available_until

    def get_subcategories(self, active_only: bool = True):
        """Get subcategories, optionally filtered by active status."""
        qs = self.subcategories.all()
        if active_only:
            qs = qs.filter(is_active=True)
        return qs.order_by('sort_order', 'name')

    def get_all_descendants(self):
        """Get all descendant categories recursively."""
        descendants = []
        for child in self.subcategories.all():
            descendants.append(child)
            descendants.extend(child.get_all_descendants())
        return descendants

    @classmethod
    def get_root_categories(cls, active_only: bool = True):
        """Get all root-level categories."""
        qs = cls.objects.filter(parent=None)
        if active_only:
            qs = qs.filter(is_active=True)
        return qs.order_by('sort_order', 'name')

    @classmethod
    def get_featured_categories(cls, limit: int = 8):
        """Get featured categories for homepage display."""
        return cls.objects.filter(
            is_active=True,
            is_featured=True
        ).order_by('sort_order', 'name')[:limit]


class MenuItem(models.Model):
    """
    Enhanced menu items with comprehensive validation, nutritional info, and business logic.
    Supports complex pricing, availability scheduling, and dietary restrictions.
    """
    # Core identification
    organization = models.ForeignKey(
        "core.Organization",
        on_delete=models.CASCADE,
        related_name="menu_items",
    )
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for external API references"
    )
    category = models.ForeignKey(
        MenuCategory,
        on_delete=models.CASCADE,
        related_name="menu_items",
        help_text="Category this item belongs to"
    )
    name = models.CharField(
        max_length=200,
        help_text="Item name (HTML tags will be stripped)",
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z0-9\s\-&\'".,!()]+$',
                message="Item name contains invalid characters"
            )
        ]
    )
    slug = models.SlugField(
        max_length=220,
        blank=True,
        help_text="URL-friendly version of the name"
    )
    description = models.TextField(
        blank=True,
        max_length=1000,
        help_text="Item description (HTML tags will be stripped)"
    )
    short_description = models.CharField(
        max_length=150,
        blank=True,
        help_text="Brief description for cards and lists"
    )
    
    # Pricing and availability
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0.01')),
            MaxValueValidator(Decimal('99999.99'))
        ],
        help_text="Base item price (0.01 - 99999.99)"
    )
    cost_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Cost price for profit margin calculations"
    )
    
    # Media
    image = models.ImageField(
        upload_to='menu_items/%Y/%m/',
        null=True,
        blank=True,
        help_text="Primary item image (optimized automatically)"
    )
    gallery_images = models.JSONField(
        default=list,
        blank=True,
        null=True,
        help_text="Additional images for gallery display"
    )
    
    # Status and features
    is_available = models.BooleanField(
        default=True,
        help_text="Whether this item is currently available"
    )
    is_featured = models.BooleanField(
        default=False,
        help_text="Featured items appear prominently"
    )
    is_popular = models.BooleanField(
        default=False,
        help_text="Popular items based on sales data"
    )
    is_new = models.BooleanField(
        default=False,
        help_text="New items for promotional display"
    )
    
    # Dietary and allergen information
    is_vegetarian = models.BooleanField(
        default=False,
        help_text="Whether this item is vegetarian"
    )
    is_vegan = models.BooleanField(
        default=False,
        help_text="Whether this item is vegan"
    )
    is_gluten_free = models.BooleanField(
        default=False,
        help_text="Whether this item is gluten-free"
    )
    is_dairy_free = models.BooleanField(
        default=False,
        help_text="Whether this item is dairy-free"
    )
    is_nut_free = models.BooleanField(
        default=False,
        help_text="Whether this item is nut-free"
    )
    is_spicy = models.BooleanField(
        default=False,
        help_text="Whether this item is spicy"
    )
    spice_level = models.PositiveSmallIntegerField(
        default=0,
        validators=[MaxValueValidator(5)],
        help_text="Spice level (0-5, 0 = not spicy)"
    )
    allergens = models.JSONField(
        default=list,
        blank=True,
        help_text="List of allergens present in this item"
    )
    
    # Nutritional information
    calories = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Calorie count per serving"
    )
    protein_grams = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Protein content in grams"
    )
    carbs_grams = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Carbohydrate content in grams"
    )
    fat_grams = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Fat content in grams"
    )
    
    # Operational details
    preparation_time = models.PositiveIntegerField(
        default=15,
        validators=[MinValueValidator(1), MaxValueValidator(480)],
        help_text="Estimated preparation time in minutes"
    )
    serving_size = models.CharField(
        max_length=50,
        blank=True,
        help_text="Serving size description (e.g., '1 piece', '250ml')"
    )
    
    # Inventory and stock
    track_inventory = models.BooleanField(
        default=False,
        help_text="Whether to track inventory for this item"
    )
    stock_quantity = models.PositiveIntegerField(
        default=0,
        help_text="Current stock quantity (if tracking inventory)"
    )
    low_stock_threshold = models.PositiveIntegerField(
        default=5,
        help_text="Alert threshold for low stock"
    )
    
    # Availability scheduling
    available_from = models.TimeField(
        null=True,
        blank=True,
        help_text="Daily availability start time"
    )
    available_until = models.TimeField(
        null=True,
        blank=True,
        help_text="Daily availability end time"
    )
    available_days = models.JSONField(
        default=list,
        blank=True,
        help_text="Days of week when available (0=Monday, 6=Sunday)"
    )
    
    # Display and ordering
    sort_order = models.PositiveIntegerField(
        default=0,
        validators=[MaxValueValidator(9999)],
        help_text="Display order within category (0-9999)"
    )
    
    # Metadata and analytics
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    view_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times this item has been viewed"
    )
    order_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times this item has been ordered"
    )
    rating_average = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        help_text="Average customer rating (0.00-5.00)"
    )
    rating_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of ratings received"
    )

    class Meta:
        verbose_name = "Menu Item"
        verbose_name_plural = "Menu Items"
        ordering = ['category__sort_order', 'sort_order', 'name']
        unique_together = [['organization', 'name'], ['category', 'slug']]
        indexes = [
            models.Index(fields=["category", "is_available", "sort_order"]),
            models.Index(fields=["organization", "is_available"]),
            models.Index(fields=["is_available", "sort_order"]),
            models.Index(fields=["is_vegetarian", "is_available"]),
            models.Index(fields=["is_vegan", "is_available"]),
            models.Index(fields=["is_gluten_free", "is_available"]),
            models.Index(fields=['is_available', 'is_featured']),
            models.Index(fields=['is_available', 'is_popular']),
            models.Index(fields=['price']),
            models.Index(fields=['uuid']),
            models.Index(fields=['slug']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['-order_count']),
            models.Index(fields=['-rating_average']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(price__gte=Decimal('0.01')),
                name="valid_menu_item_price"
            ),
            models.CheckConstraint(
                check=models.Q(preparation_time__gte=1) & models.Q(preparation_time__lte=480),
                name="valid_preparation_time"
            ),
            models.CheckConstraint(
                check=models.Q(spice_level__gte=0) & models.Q(spice_level__lte=5),
                name='menu_item_valid_spice_level'
            ),
            models.CheckConstraint(
                check=models.Q(rating_average__gte=0) & models.Q(rating_average__lte=5),
                name='menu_item_valid_rating'
            ),
            models.CheckConstraint(
                check=models.Q(available_from__isnull=True) | 
                      models.Q(available_until__isnull=True) |
                      models.Q(available_from__lt=models.F('available_until')),
                name='menu_item_valid_availability_times'
            ),
        ]

    def clean(self):
        """Enhanced validation with business rules."""
        super().clean()
        
        # Strip HTML tags and validate text fields
        if self.name:
            self.name = strip_tags(self.name).strip()
            if not self.name:
                raise ValidationError({'name': 'Item name cannot be empty after removing HTML tags.'})
            if len(self.name) < 2:
                raise ValidationError({'name': 'Item name must be at least 2 characters long.'})
        
        if self.description:
            self.description = strip_tags(self.description).strip()
        
        if self.short_description:
            self.short_description = strip_tags(self.short_description).strip()
        
        # Validate dietary restrictions logic
        if self.is_vegan:
            self.is_vegetarian = True  # Vegan items are automatically vegetarian
            self.is_dairy_free = True  # Vegan items are dairy-free
        
        # Validate spice level consistency
        if self.spice_level > 0 and not self.is_spicy:
            self.is_spicy = True
        elif self.spice_level == 0 and self.is_spicy:
            self.spice_level = 1  # Default to mild if marked as spicy
        
        # Validate cost vs selling price
        if self.cost_price and self.cost_price >= self.price:
            raise ValidationError({
                'cost_price': 'Cost price should be less than selling price for profitability.'
            })
        
        # Validate inventory tracking
        if self.track_inventory and self.stock_quantity < 0:
            raise ValidationError({
                'stock_quantity': 'Stock quantity cannot be negative.'
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

    def save(self, *args, **kwargs):
        """Enhanced save with slug generation and validation."""
        # Generate slug if not provided
        if not self.slug and self.name:
            from django.utils.text import slugify
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while MenuItem.objects.filter(
                category=self.category, 
                slug=slug
            ).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        
        # Generate short description if not provided
        if not self.short_description and self.description:
            self.short_description = self.description[:147] + '...' if len(self.description) > 150 else self.description
        
        self.full_clean()
        super().save(*args, **kwargs)
        
        # Update category cache
        if self.category:
            self.category.refresh_cached_fields()

    @property
    def dietary_tags(self):
        """Return list of dietary restriction tags."""
        tags = []
        if self.is_vegetarian:
            tags.append("Vegetarian")
        if self.is_vegan:
            tags.append("Vegan")
        if self.is_gluten_free:
            tags.append("Gluten-Free")
        if self.is_dairy_free:
            tags.append('Dairy-Free')
        if self.is_nut_free:
            tags.append('Nut-Free')
        if self.is_spicy:
            tags.append(f'Spicy ({self.spice_level}/5)')
        return tags

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self):
        """Get the URL for this menu item."""
        from django.urls import reverse
        return reverse('storefront:menu_item_detail', kwargs={
            'category_slug': self.category.slug,
            'item_slug': self.slug
        })

    def get_display_price(self) -> str:
        """Get formatted price for display."""
        return f"${self.price:.2f}"

    def get_profit_margin(self) -> Optional[Decimal]:
        """Calculate profit margin percentage."""
        if not self.cost_price or self.cost_price == 0:
            return None
        return ((self.price - self.cost_price) / self.price * 100).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

    def get_modifier_groups(self):
        """Get all active modifier groups for this item."""
        return self.modifier_groups.filter(is_active=True).order_by('sort_order')

    def get_dietary_tags(self) -> List[str]:
        """Get list of dietary restriction tags."""
        tags = []
        if self.is_vegetarian:
            tags.append('Vegetarian')
        if self.is_vegan:
            tags.append('Vegan')
        if self.is_gluten_free:
            tags.append('Gluten-Free')
        if self.is_dairy_free:
            tags.append('Dairy-Free')
        if self.is_nut_free:
            tags.append('Nut-Free')
        if self.is_spicy:
            tags.append(f'Spicy ({self.spice_level}/5)')
        return tags

    def get_allergen_warnings(self) -> List[str]:
        """Get formatted allergen warnings."""
        if not self.allergens:
            return []
        return [f"Contains {allergen}" for allergen in self.allergens]

    def calculate_total_price(self, selected_modifiers: List[int] = None) -> Decimal:
        """Calculate total price including selected modifiers."""
        total = self.price
        if selected_modifiers:
            modifier_prices = Modifier.objects.filter(
                id__in=selected_modifiers,
                is_available=True
            ).values_list('price', flat=True)
            total += sum(modifier_prices)
        return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def is_available_now(self) -> bool:
        """Check if item is currently available."""
        if not self.is_available or not self.category.is_available_now():
            return False
        
        # Check inventory
        if self.track_inventory and self.stock_quantity <= 0:
            return False
        
        # Check time availability
        if self.available_from and self.available_until:
            now = timezone.now().time()
            if not (self.available_from <= now <= self.available_until):
                return False
        
        # Check day availability
        if self.available_days:
            current_day = timezone.now().weekday()  # 0=Monday, 6=Sunday
            if current_day not in self.available_days:
                return False
        
        return True

    def is_low_stock(self) -> bool:
        """Check if item is low on stock."""
        if not self.track_inventory:
            return False
        return self.stock_quantity <= self.low_stock_threshold

    def increment_view_count(self):
        """Increment view count (use F() to avoid race conditions)."""
        MenuItem.objects.filter(pk=self.pk).update(
            view_count=models.F('view_count') + 1
        )

    def increment_order_count(self):
        """Increment order count (use F() to avoid race conditions)."""
        MenuItem.objects.filter(pk=self.pk).update(
            order_count=models.F('order_count') + 1
        )

    def update_rating(self, new_rating: Decimal):
        """Update average rating with new rating."""
        with transaction.atomic():
            current_total = self.rating_average * self.rating_count
            new_count = self.rating_count + 1
            new_average = (current_total + new_rating) / new_count
            
            MenuItem.objects.filter(pk=self.pk).update(
                rating_average=new_average.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                rating_count=new_count
            )

    @classmethod
    def get_featured_items(cls, limit: int = 8):
        """Get featured menu items."""
        return cls.objects.filter(
            is_available=True,
            is_featured=True,
            category__is_active=True
        ).select_related('category').order_by('sort_order', 'name')[:limit]

    @classmethod
    def get_popular_items(cls, limit: int = 6):
        """Get popular menu items based on order count."""
        return cls.objects.filter(
            is_available=True,
            category__is_active=True
        ).select_related('category').order_by('-order_count', '-rating_average')[:limit]

    @classmethod
    def search_items(cls, query: str, category=None):
        """Search menu items by name and description."""
        qs = cls.objects.filter(
            is_available=True,
            category__is_active=True
        ).select_related('category')
        
        if category:
            qs = qs.filter(category=category)
        
        if query:
            qs = qs.filter(
                models.Q(name__icontains=query) |
                models.Q(description__icontains=query) |
                models.Q(short_description__icontains=query)
            )
        
        return qs.order_by('sort_order', 'name')


class ModifierGroup(models.Model):
    """
    Enhanced modifier groups with flexible selection rules and validation.
    Supports complex modifier scenarios like size upgrades, toppings, and extras.
    """
    # Selection type choices
    SELECTION_SINGLE = 'single'
    SELECTION_MULTIPLE = 'multiple'
    SELECTION_EXACTLY = 'exactly'
    SELECTION_RANGE = 'range'
    
    SELECTION_TYPE_CHOICES = [
        (SELECTION_SINGLE, 'Single Selection'),
        (SELECTION_MULTIPLE, 'Multiple Selection'),
        (SELECTION_EXACTLY, 'Exact Count'),
        (SELECTION_RANGE, 'Range Selection'),
    ]
    
    # Core relationships
    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.CASCADE,
        related_name="direct_modifier_groups",
        help_text="Menu item this modifier group belongs to"
    )
    
    # Basic information
    name = models.CharField(
        max_length=100,
        help_text="Modifier group name (e.g., 'Size', 'Toppings')",
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z0-9\s\-&\'".,!()]+$',
                message="Modifier group name contains invalid characters"
            )
        ]
    )
    slug = models.SlugField(
        max_length=120,
        blank=True,
        help_text="URL-friendly version of the name"
    )
    description = models.TextField(
        blank=True,
        max_length=500,
        help_text="Optional description for the modifier group"
    )
    
    # Selection rules
    selection_type = models.CharField(
        max_length=20,
        choices=SELECTION_TYPE_CHOICES,
        default=SELECTION_SINGLE,
        help_text="Type of selection allowed"
    )
    is_required = models.BooleanField(
        default=False,
        help_text="Whether customer must select from this group"
    )
    min_selections = models.PositiveIntegerField(
        default=0,
        validators=[MaxValueValidator(50)],
        help_text="Minimum number of selections required (0-50)"
    )
    max_selections = models.PositiveIntegerField(
        default=1,
        validators=[MaxValueValidator(50)],
        help_text="Maximum number of selections allowed (1-50)"
    )
    
    # Pricing and display
    display_style = models.CharField(
        max_length=20,
        choices=[
            ('radio', 'Radio Buttons'),
            ('checkbox', 'Checkboxes'),
            ('dropdown', 'Dropdown'),
            ('button_group', 'Button Group'),
            ('stepper', 'Quantity Stepper'),
        ],
        default='radio',
        help_text="How to display this modifier group in the UI"
    )
    
    # Status and ordering
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this modifier group is currently active"
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        validators=[MaxValueValidator(9999)],
        help_text="Display order within menu item (0-9999)"
    )
    
    # Advanced features
    allow_half_portions = models.BooleanField(
        default=False,
        help_text="Allow half portions for applicable modifiers"
    )
    collapse_single_option = models.BooleanField(
        default=True,
        help_text="Hide group if only one available option"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Modifier Group"
        verbose_name_plural = "Modifier Groups"
        ordering = ['menu_item', 'sort_order', 'name']
        indexes = [
            models.Index(fields=['menu_item', 'is_active', 'sort_order']),
            models.Index(fields=['is_required', 'is_active']),
            models.Index(fields=['selection_type']),
            models.Index(fields=['slug']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(min_selections__lte=models.F('max_selections')),
                name='modifier_group_valid_selection_range'
            ),
            models.CheckConstraint(
                check=models.Q(min_selections__gte=0) & models.Q(max_selections__gte=1),
                name='modifier_group_valid_selection_counts'
            ),
        ]
        unique_together = [['menu_item', 'slug']]

    def clean(self):
        """Enhanced validation with business rules."""
        super().clean()
        
        # Strip HTML tags from text fields
        if self.name:
            self.name = strip_tags(self.name).strip()
            if not self.name:
                raise ValidationError({'name': 'Modifier group name cannot be empty after removing HTML tags.'})
            if len(self.name) < 2:
                raise ValidationError({'name': 'Modifier group name must be at least 2 characters long.'})
        
        if self.description:
            self.description = strip_tags(self.description).strip()
        
        # Validate selection logic
        if self.min_selections > self.max_selections:
            raise ValidationError({
                'min_selections': 'Minimum selections cannot exceed maximum selections.'
            })
        
        # Auto-adjust selection rules based on type
        if self.selection_type == self.SELECTION_SINGLE:
            self.max_selections = 1
            if self.is_required:
                self.min_selections = 1
        elif self.selection_type == self.SELECTION_EXACTLY:
            if self.min_selections != self.max_selections:
                self.max_selections = self.min_selections
        
        # If required, ensure min_selections is at least 1
        if self.is_required and self.min_selections == 0:
            self.min_selections = 1
        
        # Validate display style compatibility
        if self.selection_type == self.SELECTION_SINGLE and self.display_style == 'checkbox':
            raise ValidationError({
                'display_style': 'Single selection groups cannot use checkbox display style.'
            })
        
        if self.max_selections > 1 and self.display_style in ['radio', 'dropdown']:
            raise ValidationError({
                'display_style': 'Multiple selection groups cannot use radio or dropdown display styles.'
            })

    def save(self, *args, **kwargs):
        """Enhanced save with slug generation."""
        # Generate slug if not provided
        if not self.slug and self.name:
            from django.utils.text import slugify
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while ModifierGroup.objects.filter(
                menu_item=self.menu_item,
                slug=slug
            ).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.menu_item.name} - {self.name}"

    def get_available_modifiers(self):
        """Get all available modifiers in this group."""
        return self.modifiers.filter(is_available=True).order_by('sort_order', 'name')

    def get_selection_type_display_detailed(self):
        """Get detailed selection type description."""
        if self.selection_type == self.SELECTION_SINGLE:
            return "Select one option"
        elif self.selection_type == self.SELECTION_MULTIPLE:
            if self.min_selections == 0:
                return f"Select up to {self.max_selections} options"
            else:
                return f"Select {self.min_selections}-{self.max_selections} options"
        elif self.selection_type == self.SELECTION_EXACTLY:
            return f"Select exactly {self.min_selections} option(s)"
        elif self.selection_type == self.SELECTION_RANGE:
            return f"Select {self.min_selections}-{self.max_selections} options"
        return "Unknown selection type"

    def should_display(self):
        """Check if this modifier group should be displayed."""
        if not self.is_active:
            return False
        
        available_modifiers = self.get_available_modifiers()
        
        # Don't display if no available modifiers
        if not available_modifiers.exists():
            return False
        
        # Hide if only one option and collapse_single_option is True
        if self.collapse_single_option and available_modifiers.count() == 1 and not self.is_required:
            return False
        
        return True

    def get_default_selections(self):
        """Get default modifier selections for this group."""
        defaults = self.modifiers.filter(
            is_available=True,
            is_default=True
        ).order_by('sort_order')
        
        # Ensure we don't exceed max_selections
        return defaults[:self.max_selections]

    def calculate_price_impact(self, selected_modifier_ids: List[int] = None) -> Decimal:
        """Calculate total price impact of selected modifiers."""
        if not selected_modifier_ids:
            return Decimal('0.00')
        
        total_impact = Decimal('0.00')
        modifiers = self.modifiers.filter(
            id__in=selected_modifier_ids,
            is_available=True
        )
        
        for modifier in modifiers:
            total_impact += modifier.price
        
        return total_impact.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def validate_selections(self, selected_modifier_ids: List[int] = None) -> bool:
        """Validate that the selected modifiers meet the group requirements."""
        if selected_modifier_ids is None:
            selected_modifier_ids = []
        
        if not isinstance(selected_modifier_ids, (list, tuple)):
            selected_modifier_ids = [selected_modifier_ids] if selected_modifier_ids else []
        
        selection_count = len(selected_modifier_ids)
        
        # Check minimum selections
        if selection_count < self.min_selections:
            raise ValidationError(
                f"Must select at least {self.min_selections} option(s) from {self.name}."
            )
        
        # Check maximum selections
        if selection_count > self.max_selections:
            raise ValidationError(
                f"Can select at most {self.max_selections} option(s) from {self.name}."
            )
        
        # Validate that all selected modifiers belong to this group and are available
        if selected_modifier_ids:
            valid_modifier_ids = set(
                self.modifiers.filter(
                    id__in=selected_modifier_ids,
                    is_available=True
                ).values_list('id', flat=True)
            )
            
            invalid_ids = set(selected_modifier_ids) - valid_modifier_ids
            if invalid_ids:
                raise ValidationError(
                    f"Invalid or unavailable modifier selections in {self.name}: {invalid_ids}"
                )
        
        return True

    def get_validation_rules_json(self):
        """Get validation rules as JSON for frontend validation."""
        return {
            'required': self.is_required,
            'min_selections': self.min_selections,
            'max_selections': self.max_selections,
            'selection_type': self.selection_type,
            'display_style': self.display_style,
        }

    @classmethod
    def get_for_menu_item(cls, menu_item, include_inactive=False):
        """Get all modifier groups for a menu item."""
        qs = cls.objects.filter(menu_item=menu_item)
        if not include_inactive:
            qs = qs.filter(is_active=True)
        return qs.order_by('sort_order', 'name')


class Modifier(models.Model):
    """
    Enhanced individual modifier options with advanced pricing and availability features.
    Supports complex scenarios like size upgrades, seasonal items, and inventory tracking.
    """
    # Modifier type choices
    TYPE_ADDON = 'addon'
    TYPE_SUBSTITUTION = 'substitution'
    TYPE_SIZE = 'size'
    TYPE_PREPARATION = 'preparation'
    TYPE_REMOVAL = 'removal'
    
    MODIFIER_TYPE_CHOICES = [
        (TYPE_ADDON, 'Add-on'),
        (TYPE_SUBSTITUTION, 'Substitution'),
        (TYPE_SIZE, 'Size Option'),
        (TYPE_PREPARATION, 'Preparation Style'),
        (TYPE_REMOVAL, 'Remove Item'),
    ]
    
    # Core relationships
    modifier_group = models.ForeignKey(
        ModifierGroup,
        on_delete=models.CASCADE,
        related_name="modifiers",
        help_text="Modifier group this option belongs to"
    )
    
    # Basic information
    name = models.CharField(
        max_length=100,
        help_text="Modifier option name (e.g., 'Large', 'Extra Cheese')",
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z0-9\s\-&\'".,!()%]+$',
                message="Modifier name contains invalid characters"
            )
        ]
    )
    slug = models.SlugField(
        max_length=120,
        blank=True,
        help_text="URL-friendly version of the name"
    )
    description = models.TextField(
        blank=True,
        max_length=300,
        help_text="Optional description for the modifier"
    )
    short_name = models.CharField(
        max_length=20,
        blank=True,
        help_text="Abbreviated name for compact displays"
    )
    
    # Modifier classification
    modifier_type = models.CharField(
        max_length=20,
        choices=MODIFIER_TYPE_CHOICES,
        default=TYPE_ADDON,
        help_text="Type of modifier for business logic"
    )
    
    # Pricing
    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[
            MinValueValidator(Decimal('-999.99')),  # Allow negative for discounts
            MaxValueValidator(Decimal('999.99'))
        ],
        help_text="Price adjustment (-999.99 to 999.99, can be negative for discounts)"
    )
    cost_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Cost for this modifier (for profit calculations)"
    )
    
    # Availability and status
    is_available = models.BooleanField(
        default=True,
        help_text="Whether this modifier is currently available"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this modifier is selected by default"
    )
    is_popular = models.BooleanField(
        default=False,
        help_text="Popular modifier for promotional display"
    )
    is_seasonal = models.BooleanField(
        default=False,
        help_text="Seasonal modifier with limited availability"
    )
    
    # Inventory and limits
    track_inventory = models.BooleanField(
        default=False,
        help_text="Whether to track inventory for this modifier"
    )
    stock_quantity = models.PositiveIntegerField(
        default=0,
        help_text="Current stock quantity (if tracking inventory)"
    )
    daily_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum times this modifier can be ordered per day"
    )
    daily_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times ordered today"
    )
    
    # Nutritional impact
    calorie_adjustment = models.IntegerField(
        default=0,
        help_text="Calorie adjustment (positive or negative)"
    )
    
    # Availability scheduling
    available_from = models.TimeField(
        null=True,
        blank=True,
        help_text="Daily availability start time"
    )
    available_until = models.TimeField(
        null=True,
        blank=True,
        help_text="Daily availability end time"
    )
    available_days = models.JSONField(
        default=list,
        blank=True,
        help_text="Days of week when available (0=Monday, 6=Sunday)"
    )
    
    # Display and ordering
    sort_order = models.PositiveIntegerField(
        default=0,
        validators=[MaxValueValidator(9999)],
        help_text="Display order within group (0-9999)"
    )
    
    # Visual customization
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Icon class or emoji for display"
    )
    color_code = models.CharField(
        max_length=7,
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^#[0-9A-Fa-f]{6}$',
                message="Color must be a valid hex code (e.g., #FF5733)"
            )
        ],
        help_text="Hex color code for visual theming"
    )
    
    # Metadata and analytics
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    order_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times this modifier has been ordered"
    )
    last_ordered = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this modifier was ordered"
    )

    class Meta:
        verbose_name = "Modifier"
        verbose_name_plural = "Modifiers"
        ordering = ['modifier_group', 'sort_order', 'name']
        indexes = [
            models.Index(fields=['modifier_group', 'is_available', 'sort_order']),
            models.Index(fields=['is_default', 'is_available']),
            models.Index(fields=['modifier_type']),
            models.Index(fields=['is_popular', 'is_available']),
            models.Index(fields=['slug']),
            models.Index(fields=['-order_count']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(price__gte=Decimal('-999.99')) & models.Q(price__lte=Decimal('999.99')),
                name='modifier_valid_price_range'
            ),
            models.CheckConstraint(
                check=models.Q(available_from__isnull=True) | 
                      models.Q(available_until__isnull=True) |
                      models.Q(available_from__lt=models.F('available_until')),
                name='modifier_valid_availability_times'
            ),
            models.CheckConstraint(
                check=models.Q(daily_count__gte=0),
                name='modifier_valid_daily_count'
            ),
        ]
        unique_together = [['modifier_group', 'slug']]

    def clean(self):
        """Enhanced validation with business rules."""
        super().clean()
        
        # Strip HTML tags from text fields
        if self.name:
            self.name = strip_tags(self.name).strip()
            if not self.name:
                raise ValidationError({'name': 'Modifier name cannot be empty after removing HTML tags.'})
            if len(self.name) < 1:
                raise ValidationError({'name': 'Modifier name must be at least 1 character long.'})
        
        if self.description:
            self.description = strip_tags(self.description).strip()
        
        if self.short_name:
            self.short_name = strip_tags(self.short_name).strip()
        
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
        
        # Validate daily limit vs daily count
        if self.daily_limit and self.daily_count > self.daily_limit:
            raise ValidationError({
                'daily_count': 'Daily count cannot exceed daily limit.'
            })
        
        # Validate inventory tracking
        if self.track_inventory and self.stock_quantity < 0:
            raise ValidationError({
                'stock_quantity': 'Stock quantity cannot be negative.'
            })

    def save(self, *args, **kwargs):
        """Enhanced save with slug generation and auto-fields."""
        # Generate slug if not provided
        if not self.slug and self.name:
            from django.utils.text import slugify
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Modifier.objects.filter(
                modifier_group=self.modifier_group,
                slug=slug
            ).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        
        # Generate short name if not provided
        if not self.short_name and self.name:
            self.short_name = self.name[:20]
        
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        price_str = f" (+${self.price})" if self.price > 0 else f" (${self.price})" if self.price < 0 else ""
        return f"{self.modifier_group.name}: {self.name}{price_str}"

    def get_display_price(self) -> str:
        """Get formatted price for display."""
        if self.price == 0:
            return "No charge"
        elif self.price > 0:
            return f"+${self.price:.2f}"
        else:
            return f"-${abs(self.price):.2f}"

    def get_price_impact_description(self) -> str:
        """Get human-readable price impact description."""
        if self.price == 0:
            return "No additional charge"
        elif self.price > 0:
            return f"Add ${self.price:.2f}"
        else:
            return f"Save ${abs(self.price):.2f}"

    def get_profit_margin(self) -> Optional[Decimal]:
        """Calculate profit margin for this modifier."""
        if not self.cost_price or self.price <= 0:
            return None
        return ((self.price - self.cost_price) / self.price * 100).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

    def is_upcharge(self) -> bool:
        """Check if this modifier adds cost."""
        return self.price > 0

    def is_discount(self) -> bool:
        """Check if this modifier reduces cost."""
        return self.price < 0

    def is_available_now(self) -> bool:
        """Check if modifier is currently available."""
        if not self.is_available:
            return False
        
        # Check inventory
        if self.track_inventory and self.stock_quantity <= 0:
            return False
        
        # Check daily limit
        if self.daily_limit and self.daily_count >= self.daily_limit:
            return False
        
        # Check time availability
        if self.available_from and self.available_until:
            now = timezone.now().time()
            if not (self.available_from <= now <= self.available_until):
                return False
        
        # Check day availability
        if self.available_days:
            current_day = timezone.now().weekday()  # 0=Monday, 6=Sunday
            if current_day not in self.available_days:
                return False
        
        return True

    def is_at_daily_limit(self) -> bool:
        """Check if modifier has reached its daily limit."""
        if not self.daily_limit:
            return False
        return self.daily_count >= self.daily_limit

    def increment_order_count(self):
        """Increment order count and update last ordered time."""
        from django.utils import timezone
        Modifier.objects.filter(pk=self.pk).update(
            order_count=models.F('order_count') + 1,
            last_ordered=timezone.now()
        )

    def increment_daily_count(self):
        """Increment daily count (use F() to avoid race conditions)."""
        Modifier.objects.filter(pk=self.pk).update(
            daily_count=models.F('daily_count') + 1
        )

    def reset_daily_count(self):
        """Reset daily count (typically called by a daily task)."""
        Modifier.objects.filter(pk=self.pk).update(daily_count=0)

    def get_display_info(self) -> dict:
        """Get comprehensive display information for frontend."""
        return {
            'id': self.id,
            'name': self.name,
            'short_name': self.short_name or self.name,
            'description': self.description,
            'price': float(self.price),
            'price_display': self.get_display_price(),
            'price_impact': self.get_price_impact_description(),
            'modifier_type': self.modifier_type,
            'is_default': self.is_default,
            'is_popular': self.is_popular,
            'is_available': self.is_available_now(),
            'calorie_adjustment': self.calorie_adjustment,
            'icon': self.icon,
            'color_code': self.color_code,
            'at_daily_limit': self.is_at_daily_limit(),
        }

    @classmethod
    def get_popular_modifiers(cls, limit: int = 10):
        """Get most popular modifiers across all groups."""
        return cls.objects.filter(
            is_available=True,
            modifier_group__is_active=True
        ).order_by('-order_count', '-is_popular')[:limit]

    @classmethod
    def reset_all_daily_counts(cls):
        """Reset daily counts for all modifiers (daily maintenance task)."""
        return cls.objects.update(daily_count=0)
