from decimal import Decimal
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import Cart, CartItem, Order, OrderItem
from menu.models import MenuItem, Modifier, MenuCategory
from menu.serializers import MenuItemSerializer

User = get_user_model()


class ModifierDetailSerializer(serializers.ModelSerializer):
    """
    Clean serializer for modifier details in cart items.
    """
    class Meta:
        model = Modifier
        fields = ['id', 'name', 'price', 'is_available']
        read_only_fields = ['id', 'name', 'price', 'is_available']


class CartItemModifierSerializer(serializers.Serializer):
    """
    Serializer for selected modifiers in cart items.
    """
    modifier_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=10, default=1)
    
    def validate_modifier_id(self, value):
        """Validate that modifier exists and is available."""
        try:
            modifier = Modifier.objects.get(id=value)
            if not modifier.is_available:
                raise serializers.ValidationError("This modifier is not available.")
            return value
        except Modifier.DoesNotExist:
            raise serializers.ValidationError("Modifier does not exist.")


class CartItemSerializer(serializers.ModelSerializer):
    """
    Enhanced serializer for cart items with comprehensive validation.
    """
    menu_item = MenuItemSerializer(read_only=True)
    menu_item_id = serializers.IntegerField(write_only=True, min_value=1)
    selected_modifiers = CartItemModifierSerializer(many=True, required=False, default=list)
    total_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, source='line_total')
    modifier_details = serializers.SerializerMethodField()
    is_discounted = serializers.SerializerMethodField()
    
    class Meta:
        model = CartItem
        fields = [
            'id', 'item_uuid', 'menu_item', 'menu_item_id', 'quantity', 'unit_price',
            'selected_modifiers', 'modifier_total', 'line_total', 'total_price',
            'notes', 'is_gift', 'gift_message', 'scheduled_for', 'original_price',
            'discount_applied', 'added_via', 'modifier_details', 'is_discounted',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'item_uuid', 'unit_price', 'modifier_total', 'line_total', 
            'original_price', 'modifier_details', 'is_discounted', 'created_at', 'updated_at'
        ]
    
    def get_modifier_details(self, obj):
        """Get detailed modifier information."""
        try:
            return obj.get_modifier_details()
        except AttributeError:
            return []
    
    def get_is_discounted(self, obj):
        """Check if item has discount applied."""
        return obj.discount_applied > 0 if obj.discount_applied else False
    
    def validate_menu_item_id(self, value):
        """Validate that menu item exists and is available."""
        try:
            menu_item = MenuItem.objects.get(id=value)
            if not menu_item.is_available:
                raise serializers.ValidationError("This menu item is not available.")
            return value
        except MenuItem.DoesNotExist:
            raise serializers.ValidationError("Menu item does not exist.")
    
    def validate_quantity(self, value):
        """Validate quantity is within reasonable limits."""
        if value < 1:
            raise serializers.ValidationError("Quantity must be at least 1.")
        if value > 999:
            raise serializers.ValidationError("Quantity cannot exceed 999.")
        return value
    
    def validate_selected_modifiers(self, value):
        """Validate selected modifiers structure and availability."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Selected modifiers must be a list.")
        
        # Check for duplicate modifiers
        modifier_ids = [mod.get('modifier_id') for mod in value if isinstance(mod, dict)]
        if len(modifier_ids) != len(set(modifier_ids)):
            raise serializers.ValidationError("Duplicate modifiers are not allowed.")
        
        return value
    
    def create(self, validated_data):
        """Create cart item with proper menu item assignment."""
        menu_item_id = validated_data.pop('menu_item_id')
        menu_item = MenuItem.objects.get(id=menu_item_id)
        
        cart_item = CartItem.objects.create(
            menu_item=menu_item,
            unit_price=menu_item.price,  # Capture current price
            **validated_data
        )
        return cart_item
    
    def update(self, instance, validated_data):
        """Update cart item with validation."""
        # Don't allow changing menu_item after creation
        validated_data.pop('menu_item_id', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance


class CartSerializer(serializers.ModelSerializer):
    """
    Enhanced serializer for carts with comprehensive validation.
    """
    items = CartItemSerializer(many=True, read_only=True)
    user = serializers.StringRelatedField(read_only=True)
    table_name = serializers.CharField(source='table.name', read_only=True)
    item_count = serializers.SerializerMethodField()
    total_discount = serializers.SerializerMethodField()
    estimated_total_with_tax = serializers.SerializerMethodField()
    can_be_modified = serializers.SerializerMethodField()
    
    class Meta:
        model = Cart
        fields = [
            'cart_uuid', 'user', 'status', 'delivery_option', 'table_name',
            'subtotal', 'modifier_total', 'discount_amount', 
            'coupon_discount', 'loyalty_discount', 'total_discount',
            'tip_amount', 'tip_percentage', 'delivery_fee', 'service_fee',
            'tax_amount', 'tax_rate', 'total', 'notes', 'items', 'item_count',
            'delivery_address', 'delivery_instructions', 'estimated_delivery_time',
            'customer_name', 'customer_phone', 'customer_email', 'applied_coupon_code',
            'source', 'modification_count', 'estimated_total_with_tax', 'can_be_modified',
            'created_at', 'updated_at', 'last_activity', 'expires_at', 'converted_at', 'abandoned_at'
        ]
        read_only_fields = [
            'cart_uuid', 'user', 'subtotal', 'modifier_total',
            'tax_amount', 'total', 'modification_count',
            'total_discount', 'estimated_total_with_tax', 'can_be_modified',
            'created_at', 'updated_at', 'last_activity', 'converted_at', 'abandoned_at'
        ]
    
    def get_item_count(self, obj):
        """Get total number of items in cart."""
        return sum(item.quantity for item in obj.items.all())
    
    def get_total_discount(self, obj):
        """Get total discount amount."""
        return (obj.discount_amount or 0) + (obj.coupon_discount or 0) + (obj.loyalty_discount or 0)
    
    def get_estimated_total_with_tax(self, obj):
        """Get estimated total including tax."""
        return obj.total
    
    def get_can_be_modified(self, obj):
        """Check if cart can be modified."""
        return obj.status == Cart.STATUS_ACTIVE
    
    def validate_delivery_option(self, value):
        """Validate delivery option."""
        valid_options = [choice[0] for choice in Cart.DELIVERY_CHOICES]
        if value not in valid_options:
            raise serializers.ValidationError(f"Invalid delivery option. Choose from: {valid_options}")
        return value
    
    def validate_tip_amount(self, value):
        """Validate tip amount."""
        if value < 0:
            raise serializers.ValidationError("Tip amount cannot be negative.")
        if value > Decimal('9999.99'):
            raise serializers.ValidationError("Tip amount is too large.")
        return value
    
    def validate_discount_amount(self, value):
        """Validate discount amount."""
        if value < 0:
            raise serializers.ValidationError("Discount amount cannot be negative.")
        return value


class CartCreateSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for creating new carts.
    """
    class Meta:
        model = Cart
        fields = ['delivery_option', 'notes']
    
    def create(self, validated_data):
        """Create cart with user or session assignment."""
        request = self.context.get('request')
        
        if request and request.user.is_authenticated:
            validated_data['user'] = request.user
        elif request and hasattr(request, 'session'):
            validated_data['session_key'] = request.session.session_key
        
        cart = Cart.objects.create(**validated_data)
        cart.set_expiration(minutes=60)  # Set 1-hour expiration
        cart.save()
        
        return cart


class AddToCartSerializer(serializers.Serializer):
    """
    Serializer for adding items to cart.
    """
    menu_item_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=999, default=1)
    selected_modifiers = CartItemModifierSerializer(many=True, required=False, default=list)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_menu_item_id(self, value):
        """Validate menu item exists and is available."""
        try:
            menu_item = MenuItem.objects.get(id=value)
            if not menu_item.is_available:
                raise serializers.ValidationError("This menu item is not available.")
            return value
        except MenuItem.DoesNotExist:
            raise serializers.ValidationError("Menu item does not exist.")
    
    def create(self, validated_data):
        """Add item to cart or update existing item."""
        cart = self.context['cart']
        menu_item_id = validated_data['menu_item_id']
        menu_item = MenuItem.objects.get(id=menu_item_id)
        
        # Check if same item with same modifiers and notes already exists
        existing_item = cart.items.filter(
            menu_item=menu_item,
            selected_modifiers=validated_data.get('selected_modifiers', []),
            notes=validated_data.get('notes', '')
        ).first()
        
        if existing_item:
            # Update quantity of existing item
            existing_item.quantity += validated_data['quantity']
            existing_item.save()
            return existing_item
        else:
            # Create new cart item
            return CartItem.objects.create(
                cart=cart,
                menu_item=menu_item,
                unit_price=menu_item.price,
                quantity=validated_data['quantity'],
                selected_modifiers=validated_data.get('selected_modifiers', []),
                notes=validated_data.get('notes', '')
            )


class UpdateCartItemSerializer(serializers.Serializer):
    """
    Serializer for updating cart item quantity and notes.
    """
    cart_item_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=0, max_value=999)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def update(self, instance, validated_data):
        """Update cart item or remove if quantity is 0."""
        quantity = validated_data.get('quantity')
        
        if quantity == 0:
            # Remove item from cart
            instance.delete()
            return None
        else:
            # Update item
            instance.quantity = quantity
            if 'notes' in validated_data:
                instance.notes = validated_data['notes']
            instance.save()
            return instance


# Order Serializers (for future use)
class OrderItemSerializer(serializers.ModelSerializer):
    """
    Enhanced serializer for order items with comprehensive details.
    """
    menu_item = MenuItemSerializer(read_only=True)
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    modifier_details = serializers.SerializerMethodField()
    is_discounted = serializers.SerializerMethodField()
    preparation_time_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = OrderItem
        fields = [
            'id', 'item_uuid', 'menu_item', 'quantity', 'unit_price', 'modifiers',
            'modifier_total', 'line_total', 'discount_applied', 'notes', 'is_gift',
            'gift_message', 'status', 'preparation_notes', 'modifier_details',
            'is_discounted', 'preparation_time_remaining', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'item_uuid', 'modifier_total', 'line_total', 'modifier_details',
            'is_discounted', 'preparation_time_remaining', 'created_at', 'updated_at'
        ]
    
    def get_modifier_details(self, obj):
        """Get detailed modifier information."""
        try:
            return obj.get_modifier_details() if hasattr(obj, 'get_modifier_details') else []
        except AttributeError:
            return []
    
    def get_is_discounted(self, obj):
        """Check if item has discount applied."""
        return obj.discount_applied > 0 if obj.discount_applied else False
    
    def get_preparation_time_remaining(self, obj):
        """Get remaining preparation time in minutes."""
        try:
            return obj.get_preparation_time() if hasattr(obj, 'get_preparation_time') else None
        except AttributeError:
            return None


class OrderSerializer(serializers.ModelSerializer):
    """
    Enhanced serializer for orders with comprehensive details.
    """
    items = OrderItemSerializer(many=True, read_only=True)
    user = serializers.StringRelatedField(read_only=True)
    table_name = serializers.CharField(source='table.name', read_only=True)
    item_count = serializers.SerializerMethodField()
    total_discount = serializers.SerializerMethodField()
    can_be_cancelled = serializers.SerializerMethodField()
    can_be_refunded = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    preparation_time = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'order_uuid', 'order_number', 'user', 'status', 'delivery_option',
            'table_name', 'subtotal', 'modifier_total', 'discount_amount',
            'coupon_discount', 'loyalty_discount', 'total_discount', 'tip_amount',
            'tip_percentage', 'delivery_fee', 'service_fee', 'tax_amount', 'tax_rate',
            'total_amount', 'refund_amount', 'notes', 'items', 'item_count',
            'delivery_address', 'delivery_instructions', 'estimated_delivery_time',
            'actual_delivery_time', 'customer_name', 'customer_phone', 'customer_email',
            'applied_coupon_code', 'source', 'can_be_cancelled', 'can_be_refunded',
            'is_overdue', 'preparation_time', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'order_uuid', 'order_number', 'user', 'subtotal', 'modifier_total',
            'tax_amount', 'total_amount', 'total_discount', 'can_be_cancelled',
            'can_be_refunded', 'is_overdue', 'preparation_time', 'created_at', 'updated_at'
        ]
    
    def get_item_count(self, obj):
        """Get total number of items in order."""
        return sum(item.quantity for item in obj.items.all())
    
    def get_total_discount(self, obj):
        """Get total discount amount."""
        return (obj.discount_amount or 0) + (obj.coupon_discount or 0) + (obj.loyalty_discount or 0)
    
    def get_can_be_cancelled(self, obj):
        """Check if order can be cancelled."""
        return obj.status in ['pending', 'confirmed'] if hasattr(obj, 'status') else False
    
    def get_can_be_refunded(self, obj):
        """Check if order can be refunded."""
        return obj.status in ['completed', 'delivered'] if hasattr(obj, 'status') else False
    
    def get_is_overdue(self, obj):
        """Check if order is overdue."""
        try:
            return obj.is_overdue() if hasattr(obj, 'is_overdue') else False
        except AttributeError:
            return False
    
    def get_preparation_time(self, obj):
        """Get estimated preparation time."""
        try:
            return obj.get_preparation_time() if hasattr(obj, 'get_preparation_time') else None
        except AttributeError:
            return None


class OrderCreateSerializer(serializers.Serializer):
    """
    Serializer for creating orders from carts.
    """
    cart_uuid = serializers.UUIDField()
    notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    
    def validate_cart_uuid(self, value):
        """Validate cart exists and is active."""
        try:
            cart = Cart.objects.get(cart_uuid=value)
            if cart.status != Cart.STATUS_ACTIVE:
                raise serializers.ValidationError("Cart is not active.")
            if not cart.items.exists():
                raise serializers.ValidationError("Cart is empty.")
            return value
        except Cart.DoesNotExist:
            raise serializers.ValidationError("Cart does not exist.")
    
    def create(self, validated_data):
        """Create order from cart."""
        cart_uuid = validated_data['cart_uuid']
        cart = Cart.objects.get(cart_uuid=cart_uuid)
        
        # Create order from cart
        order = Order.objects.create(
            user=cart.user,
            delivery_option=cart.delivery_option,
            table=cart.table,
            subtotal=cart.subtotal,
            modifier_total=cart.modifier_total,
            tip_amount=cart.tip_amount,
            discount_amount=cart.discount_amount,
            tax_amount=cart.tax_amount,
            total_amount=cart.total,
            notes=validated_data.get('notes', cart.notes),
            source_cart=cart
        )
        
        # Convert cart items to order items
        for cart_item in cart.items.all():
            # Convert modifiers to include prices
            order_modifiers = []
            for modifier_data in cart_item.selected_modifiers:
                try:
                    modifier = Modifier.objects.get(id=modifier_data['modifier_id'])
                    order_modifiers.append({
                        'modifier_id': modifier.id,
                        'name': modifier.name,
                        'price': str(modifier.price),
                        'quantity': modifier_data.get('quantity', 1)
                    })
                except Modifier.DoesNotExist:
                    continue
            
            OrderItem.objects.create(
                order=order,
                menu_item=cart_item.menu_item,
                quantity=cart_item.quantity,
                unit_price=cart_item.unit_price,
                modifiers=order_modifiers,
                notes=cart_item.notes
            )
        
        # Mark cart as converted
        cart.status = Cart.STATUS_CONVERTED
        cart.save()
        
        return order


class OrderListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for order lists.
    """
    user = serializers.StringRelatedField(read_only=True)
    item_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'order_uuid', 'order_number', 'user', 'status', 'delivery_option',
            'total_amount', 'item_count', 'created_at'
        ]
        read_only_fields = ['order_uuid', 'order_number', 'user', 'total_amount', 'created_at']
    
    def get_item_count(self, obj):
        """Get total number of items in order."""
        return obj.items.count()
