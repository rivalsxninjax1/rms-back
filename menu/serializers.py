from decimal import Decimal
from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import MenuCategory, MenuItem, ModifierGroup, Modifier


class ModifierSerializer(serializers.ModelSerializer):
    """
    Clean serializer for modifiers with proper validation.
    """
    modifier_group_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    available_from = serializers.TimeField(required=False, allow_null=True)
    available_until = serializers.TimeField(required=False, allow_null=True)

    class Meta:
        model = Modifier
        fields = [
            'id', 'name', 'description', 'price', 'is_available',
            'available_from', 'available_until',
            'modifier_group', 'modifier_group_id',
            'sort_order', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_price(self, value):
        """Validate modifier price."""
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative.")
        if value > Decimal('999.99'):
            raise serializers.ValidationError("Price cannot exceed $999.99.")
        return value
    
    def validate_name(self, value):
        """Validate modifier name."""
        if not value or not value.strip():
            raise serializers.ValidationError("Name is required.")
        if len(value.strip()) > 100:
            raise serializers.ValidationError("Name cannot exceed 100 characters.")
        return value.strip()

    def create(self, validated_data):
        group_id = validated_data.pop('modifier_group_id', None)
        obj = Modifier.objects.create(**validated_data)
        if group_id:
            try:
                obj.modifier_group_id = int(group_id)
                obj.save(update_fields=['modifier_group'])
            except Exception:
                pass
        return obj

    def update(self, instance, validated_data):
        group_id = validated_data.pop('modifier_group_id', None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        if group_id is not None:
            instance.modifier_group_id = group_id or None
        instance.save()
        return instance


class ModifierGroupSerializer(serializers.ModelSerializer):
    """
    Clean serializer for modifier groups with nested modifiers.
    """
    modifiers = ModifierSerializer(many=True, read_only=True)
    available_modifiers_count = serializers.SerializerMethodField()
    
    menu_item_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    class Meta:
        model = ModifierGroup
        fields = [
            'id', 'menu_item', 'menu_item_id', 'name', 'description', 'is_required', 'max_selections',
            'min_selections', 'sort_order', 'modifiers', 'available_modifiers_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_available_modifiers_count(self, obj):
        """Get count of available modifiers in this group."""
        return obj.modifiers.filter(is_available=True).count()
    
    def validate_name(self, value):
        """Validate modifier group name."""
        if not value or not value.strip():
            raise serializers.ValidationError("Name is required.")
        if len(value.strip()) > 100:
            raise serializers.ValidationError("Name cannot exceed 100 characters.")
        return value.strip()
    
    def validate_max_selections(self, value):
        """Validate max selections."""
        if value < 0:
            raise serializers.ValidationError("Max selections cannot be negative.")
        if value > 50:
            raise serializers.ValidationError("Max selections cannot exceed 50.")
        return value
    
    def validate_min_selections(self, value):
        """Validate min selections."""
        if value < 0:
            raise serializers.ValidationError("Min selections cannot be negative.")
        return value
    
    def validate(self, attrs):
        """Cross-field validation."""
        min_sel = attrs.get('min_selections', 0)
        max_sel = attrs.get('max_selections', 0)
        
        if min_sel > max_sel and max_sel > 0:
            raise serializers.ValidationError(
                "Min selections cannot be greater than max selections."
            )
        
        return attrs

    def create(self, validated_data):
        item_id = validated_data.pop('menu_item_id', None)
        obj = ModifierGroup.objects.create(**validated_data)
        if item_id:
            try:
                obj.menu_item_id = int(item_id)
                obj.save(update_fields=['menu_item'])
            except Exception:
                pass
        return obj

    def update(self, instance, validated_data):
        item_id = validated_data.pop('menu_item_id', None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        if item_id is not None:
            instance.menu_item_id = item_id or None
        instance.save()
        return instance


class MenuCategorySerializer(serializers.ModelSerializer):
    """
    Clean serializer for menu categories.
    """
    available_items_count = serializers.SerializerMethodField()
    
    available_from = serializers.TimeField(required=False, allow_null=True)
    available_until = serializers.TimeField(required=False, allow_null=True)
    class Meta:
        model = MenuCategory
        fields = [
            'id', 'name', 'description', 'is_active', 'sort_order',
            'available_from', 'available_until',
            'available_items_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_available_items_count(self, obj):
        """Get count of available menu items in this category."""
        return obj.menu_items.filter(is_available=True).count()
    
    def validate_name(self, value):
        """Validate category name."""
        if not value or not value.strip():
            raise serializers.ValidationError("Name is required.")
        if len(value.strip()) > 100:
            raise serializers.ValidationError("Name cannot exceed 100 characters.")
        return value.strip()


class MenuItemSerializer(serializers.ModelSerializer):
    """
    Clean serializer for menu items with comprehensive details.
    """
    category = MenuCategorySerializer(read_only=True)
    category_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    modifier_groups = ModifierGroupSerializer(many=True, read_only=True)
    available_modifier_groups_count = serializers.SerializerMethodField()
    dietary_info = serializers.SerializerMethodField()
    
    available_from = serializers.TimeField(required=False, allow_null=True)
    available_until = serializers.TimeField(required=False, allow_null=True)
    image = serializers.ImageField(required=False, allow_null=True)
    class Meta:
        model = MenuItem
        fields = [
            'id', 'name', 'description', 'price', 'category', 'category_id',
            'is_available', 'is_vegetarian', 'is_vegan', 'is_gluten_free',
            'available_from', 'available_until', 'image',
            'preparation_time', 'sort_order', 'modifier_groups',
            'available_modifier_groups_count', 'dietary_info',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_available_modifier_groups_count(self, obj):
        """Get count of modifier groups for this item."""
        return obj.modifier_groups.count()
    
    def get_dietary_info(self, obj):
        """Get dietary information as a list of tags."""
        info = []
        if obj.is_vegetarian:
            info.append('Vegetarian')
        if obj.is_vegan:
            info.append('Vegan')
        if obj.is_gluten_free:
            info.append('Gluten-Free')
        return info
    
    def validate_name(self, value):
        """Validate menu item name."""
        if not value or not value.strip():
            raise serializers.ValidationError("Name is required.")
        if len(value.strip()) > 200:
            raise serializers.ValidationError("Name cannot exceed 200 characters.")
        return value.strip()
    
    def validate_price(self, value):
        """Validate menu item price."""
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative.")
        if value > Decimal('9999.99'):
            raise serializers.ValidationError("Price cannot exceed $9999.99.")
        return value
    
    def validate_category_id(self, value):
        """Validate category exists and is active."""
        if value is not None:
            try:
                category = MenuCategory.objects.get(id=value)
                if not category.is_active:
                    raise serializers.ValidationError("Category is not active.")
                return value
            except MenuCategory.DoesNotExist:
                raise serializers.ValidationError("Category does not exist.")
        return value
    
    def validate_preparation_time(self, value):
        """Validate preparation time."""
        if value is not None:
            if value < 1:
                raise serializers.ValidationError("Preparation time must be at least 1 minute.")
            if value > 480:
                raise serializers.ValidationError("Preparation time cannot exceed 480 minutes.")
        return value
    
    def create(self, validated_data):
        """Create menu item with proper category assignment."""
        category_id = validated_data.pop('category_id', None)
        
        menu_item = MenuItem.objects.create(**validated_data)
        
        if category_id:
            category = MenuCategory.objects.get(id=category_id)
            menu_item.category = category
            menu_item.save()
        
        return menu_item
    
    def update(self, instance, validated_data):
        """Update menu item with validation."""
        category_id = validated_data.pop('category_id', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if category_id is not None:
            if category_id:
                category = MenuCategory.objects.get(id=category_id)
                instance.category = category
            else:
                instance.category = None
        
        instance.save()
        return instance


class MenuItemListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for menu item lists (better performance).
    """
    category_name = serializers.CharField(source='category.name', read_only=True)
    dietary_info = serializers.SerializerMethodField()
    
    class Meta:
        model = MenuItem
        fields = [
            'id', 'name', 'description', 'price', 'category_name',
            'is_available', 'is_vegetarian', 'is_vegan', 'is_gluten_free',
            'dietary_info', 'preparation_time', 'sort_order'
        ]
        read_only_fields = ['id']
    
    def get_dietary_info(self, obj):
        """Get dietary information as a list of tags."""
        info = []
        if obj.is_vegetarian:
            info.append('Vegetarian')
        if obj.is_vegan:
            info.append('Vegan')
        if obj.is_gluten_free:
            info.append('Gluten-Free')
        return info


class MenuItemDetailSerializer(MenuItemSerializer):
    """
    Detailed serializer for single menu item views with all relationships.
    """
    modifier_groups = ModifierGroupSerializer(many=True, read_only=True)
    
    class Meta(MenuItemSerializer.Meta):
        fields = MenuItemSerializer.Meta.fields + ['modifier_groups']


class MenuCategoryWithItemsSerializer(MenuCategorySerializer):
    """
    Category serializer with nested menu items for menu display.
    """
    menu_items = MenuItemListSerializer(source='items', many=True, read_only=True)
    
    class Meta(MenuCategorySerializer.Meta):
        fields = MenuCategorySerializer.Meta.fields + ['menu_items']
    
    def to_representation(self, instance):
        """Filter to only show available items."""
        data = super().to_representation(instance)
        # Only show available items in the menu display
        available_items = [item for item in data['menu_items'] if item['is_available']]
        data['menu_items'] = available_items
        return data


class MenuDisplaySerializer(serializers.Serializer):
    """
    Serializer for complete menu display with categories and items.
    """
    categories = MenuCategoryWithItemsSerializer(many=True, read_only=True)
    featured_items = MenuItemListSerializer(many=True, read_only=True)
    total_categories = serializers.IntegerField(read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    last_updated = serializers.DateTimeField(read_only=True)
    
    def to_representation(self, instance):
        """Custom representation for menu display."""
        # instance should be a dict with menu data
        return {
            'categories': instance.get('categories', []),
            'featured_items': instance.get('featured_items', []),
            'total_categories': instance.get('total_categories', 0),
            'total_items': instance.get('total_items', 0),
            'last_updated': instance.get('last_updated')
        }


class MenuSearchSerializer(serializers.Serializer):
    """
    Serializer for menu search functionality.
    """
    query = serializers.CharField(max_length=200, required=True)
    category_id = serializers.IntegerField(required=False, allow_null=True)
    is_vegan = serializers.BooleanField(required=False)
    is_gluten_free = serializers.BooleanField(required=False)
    min_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, min_value=0)
    max_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, min_value=0)
    
    def validate_query(self, value):
        """Validate search query."""
        if not value or not value.strip():
            raise serializers.ValidationError("Search query cannot be empty.")
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Search query must be at least 2 characters.")
        return value.strip()
    
    def validate_category_id(self, value):
        """Validate category exists."""
        if value is not None:
            try:
                MenuCategory.objects.get(id=value, is_active=True)
                return value
            except MenuCategory.DoesNotExist:
                raise serializers.ValidationError("Category does not exist or is not active.")
        return value
    
    def validate(self, attrs):
        """Cross-field validation."""
        min_price = attrs.get('min_price')
        max_price = attrs.get('max_price')
        
        if min_price is not None and max_price is not None:
            if min_price > max_price:
                raise serializers.ValidationError(
                    "Min price cannot be greater than max price."
                )
        
        return attrs
