from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, F, Q
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.pagination import PageNumberPagination
from rest_framework.authentication import SessionAuthentication
from django_filters.rest_framework import DjangoFilterBackend
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import uuid
import json

from .models import Cart, CartItem, Order, OrderItem
from .services.totals import compute_cart_totals, compute_order_totals
from menu.models import MenuItem, Modifier, ModifierGroup
from .serializers import (
    CartSerializer, CartCreateSerializer, CartItemSerializer,
    AddToCartSerializer, UpdateCartItemSerializer,
    OrderSerializer, OrderCreateSerializer, OrderListSerializer,
    OrderItemSerializer
)


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """SessionAuthentication that bypasses CSRF validation for API endpoints."""
    
    def enforce_csrf(self, request):
        return  # Skip CSRF validation


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for API responses."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class CartViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing shopping carts with comprehensive functionality.
    Supports both session-based and user-based carts.
    """
    serializer_class = CartSerializer
    permission_classes = [AllowAny]
    authentication_classes = [CsrfExemptSessionAuthentication]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Get cart based on user authentication or session."""
        if self.request.user.is_authenticated:
            return Cart.objects.filter(
                user=self.request.user,
                status=Cart.STATUS_ACTIVE
            ).prefetch_related(
                'items__menu_item__category',
                'items__menu_item__modifier_groups__modifiers'
            )
        else:
            # For anonymous users, use session key
            session_key = self.request.session.session_key
            if not session_key:
                self.request.session.create()
                session_key = self.request.session.session_key
            
            return Cart.objects.filter(
                session_key=session_key,
                status=Cart.STATUS_ACTIVE
            ).prefetch_related(
                'items__menu_item__category',
                'items__menu_item__modifier_groups__modifiers'
            )
    
    def get_or_create_cart(self):
        """Get or create a cart for the current user/session."""
        if self.request.user.is_authenticated:
            # Try to get existing active cart, if multiple exist, get the most recent one
            try:
                cart = Cart.objects.filter(
                    user=self.request.user,
                    status=Cart.STATUS_ACTIVE
                ).order_by('-updated_at').first()
                
                if cart:
                    created = False
                else:
                    cart = Cart.objects.create(
                        user=self.request.user,
                        status=Cart.STATUS_ACTIVE,
                        cart_uuid=uuid.uuid4(),
                        session_key=self.request.session.session_key or ''
                    )
                    created = True
            except Exception:
                # Fallback: create new cart
                cart = Cart.objects.create(
                    user=self.request.user,
                    status=Cart.STATUS_ACTIVE,
                    cart_uuid=uuid.uuid4(),
                    session_key=self.request.session.session_key or ''
                )
                created = True
        else:
            session_key = self.request.session.session_key
            if not session_key:
                self.request.session.create()
                session_key = self.request.session.session_key
            
            cart, created = Cart.objects.get_or_create(
                session_key=session_key,
                user=None,
                status=Cart.STATUS_ACTIVE,
                defaults={
                    'cart_uuid': uuid.uuid4()
                }
            )
        
        return cart, created
    
    def list(self, request):
        """Get current cart or create if doesn't exist."""
        cart, created = self.get_or_create_cart()
        serializer = self.get_serializer(cart)
        
        response_data = serializer.data
        response_data['created'] = created
        
        return Response(response_data)
    
    def retrieve(self, request, pk=None):
        """Get specific cart by UUID."""
        try:
            cart_uuid = uuid.UUID(pk)
            cart = get_object_or_404(Cart, cart_uuid=cart_uuid)
            
            # Check permissions
            if request.user.is_authenticated:
                if cart.user != request.user:
                    return Response(
                        {'error': 'Cart not found'}, 
                        status=status.HTTP_404_NOT_FOUND
                    )
            else:
                if cart.session_key != request.session.session_key:
                    return Response(
                        {'error': 'Cart not found'}, 
                        status=status.HTTP_404_NOT_FOUND
                    )
            
            serializer = self.get_serializer(cart)
            return Response(serializer.data)
            
        except (ValueError, ValidationError):
            return Response(
                {'error': 'Invalid cart ID'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def add_item(self, request):
        """
        Add an item to the cart with optional modifiers.
        """
        try:
            with transaction.atomic():
                cart, _ = self.get_or_create_cart()
                
                # Use the serializer with cart context
                serializer = AddToCartSerializer(data=request.data, context={'cart': cart})
                if not serializer.is_valid():
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
                # Create or update cart item using serializer
                cart_item = serializer.create(serializer.validated_data)
                
                # Update cart totals via centralized service
                compute_cart_totals(cart, save=True)
                
                # Return updated cart
                cart_serializer = CartSerializer(cart, context={'request': request})
                return Response({
                    'message': 'Item added to cart successfully',
                    'cart': cart_serializer.data,
                    'added_item': CartItemSerializer(cart_item, context={'request': request}).data
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return Response(
                {'error': f'Failed to add item to cart: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['patch'])
    def update_item(self, request):
        """
        Update quantity or modifiers of a cart item.
        """
        serializer = UpdateCartItemSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data
        cart_item_id = validated_data['cart_item_id']
        quantity = validated_data.get('quantity')
        # Use 'notes' field to preserve special instructions
        notes = validated_data.get('notes')
        
        try:
            with transaction.atomic():
                cart, _ = self.get_or_create_cart()
                cart_item = get_object_or_404(CartItem, id=cart_item_id, cart=cart)
                
                if quantity is not None:
                    if quantity <= 0:
                        cart_item.delete()
                        message = 'Item removed from cart'
                    else:
                        cart_item.quantity = quantity
                        cart_item.save()
                        message = 'Item quantity updated'
                else:
                    message = 'Item updated'
                
                if notes is not None:
                    cart_item.notes = notes
                    cart_item.save(update_fields=["notes"]) if hasattr(cart_item, "notes") else cart_item.save()
                
                # Update cart totals via centralized service
                compute_cart_totals(cart, save=True)
                
                # Return updated cart
                cart_serializer = CartSerializer(cart, context={'request': request})
                return Response({
                    'message': message,
                    'cart': cart_serializer.data
                })
                
        except Exception as e:
            return Response(
                {'error': f'Failed to update cart item: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['delete'])
    def remove_item(self, request):
        """
        Remove an item from the cart.
        """
        cart_item_id = request.data.get('cart_item_id')
        if not cart_item_id:
            return Response(
                {'error': 'cart_item_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                cart, _ = self.get_or_create_cart()
                cart_item = get_object_or_404(CartItem, id=cart_item_id, cart=cart)
                
                cart_item.delete()
                
                # Update cart totals
                compute_cart_totals(cart, save=True)
                
                # Return updated cart
                cart_serializer = CartSerializer(cart, context={'request': request})
                return Response({
                    'message': 'Item removed from cart successfully',
                    'cart': cart_serializer.data
                })
                
        except Exception as e:
            return Response(
                {'error': f'Failed to remove cart item: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['delete'])
    def clear(self, request):
        """
        Clear all items from the cart.
        """
        try:
            with transaction.atomic():
                cart, _ = self.get_or_create_cart()
                cart.items.all().delete()
                compute_cart_totals(cart, save=True)
                
                cart_serializer = CartSerializer(cart, context={'request': request})
                return Response({
                    'message': 'Cart cleared successfully',
                    'cart': cart_serializer.data
                })
                
        except Exception as e:
            return Response(
                {'error': f'Failed to clear cart: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get cart summary with totals and item count.
        """
        cart, _ = self.get_or_create_cart()
        
        summary = {
            'cart_uuid': str(cart.cart_uuid),
            'item_count': cart.items.count(),
            'total_quantity': cart.items.aggregate(
                total=Sum('quantity')
            )['total'] or 0,
            'subtotal': cart.subtotal,
            'tax_amount': cart.tax_amount,
            'total_amount': cart.total_amount,
            'delivery_option': cart.delivery_option,
            'created_at': cart.created_at,
            'updated_at': cart.updated_at
        }
        
        return Response(summary)
    
    @action(detail=False, methods=['post'])
    def merge(self, request):
        """
        Merge anonymous cart with user cart after login.
        """
        if not request.user.is_authenticated:
            return Response(
                {'error': 'User must be authenticated'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        anonymous_cart_uuid = request.data.get('anonymous_cart_uuid')
        if not anonymous_cart_uuid:
            return Response(
                {'error': 'anonymous_cart_uuid is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                # Get anonymous cart
                anonymous_cart = get_object_or_404(Cart, cart_uuid=anonymous_cart_uuid, user=None)
                
                # Get or create an ACTIVE user cart
                user_cart = (
                    Cart.objects.filter(user=request.user, status=Cart.STATUS_ACTIVE)
                    .order_by('-updated_at')
                    .first()
                )
                if not user_cart:
                    user_cart = Cart.objects.create(
                        user=request.user,
                        status=Cart.STATUS_ACTIVE,
                        cart_uuid=uuid.uuid4(),
                        session_key=request.session.session_key or ''
                    )
                
                # Merge items from anonymous cart to user cart
                for anon_item in anonymous_cart.items.all():
                    # Check if similar item exists in user cart
                    existing_item = user_cart.items.filter(
                        menu_item=anon_item.menu_item,
                        selected_modifiers=anon_item.selected_modifiers
                    ).first()
                    
                    if existing_item:
                        existing_item.quantity += anon_item.quantity
                        existing_item.save()
                    else:
                        # Move item to user cart
                        anon_item.cart = user_cart
                        anon_item.save()
                
                # Delete anonymous cart
                anonymous_cart.delete()
                
                # Update user cart totals
                from .services.totals import compute_cart_totals
                compute_cart_totals(user_cart, save=True)
                
                cart_serializer = CartSerializer(user_cart, context={'request': request})
                return Response({
                    'message': 'Carts merged successfully',
                    'cart': cart_serializer.data
                })
                
        except Exception as e:
            return Response(
                {'error': f'Failed to merge carts: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def modifiers(self, request):
        """
        Get available modifiers for menu items in cart or specific menu item.
        """
        menu_item_id = request.query_params.get('menu_item')
        
        if menu_item_id:
            # Get modifiers for specific menu item
            try:
                menu_item = get_object_or_404(MenuItem, id=menu_item_id)
                modifier_groups = menu_item.modifier_groups.prefetch_related('modifiers').all()
            except (ValueError, ValidationError):
                return Response(
                    {'error': 'Invalid menu item ID'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
             # Get modifiers for all items in current cart
             cart, _ = self.get_or_create_cart()
             menu_item_ids = cart.items.values_list('menu_item_id', flat=True)
             modifier_groups = ModifierGroup.objects.filter(
                 menu_item_id__in=menu_item_ids
             ).prefetch_related('modifiers').order_by('sort_order')
        
        result = []
        for group in modifier_groups:
            modifiers = []
            for modifier in group.modifiers.filter(is_available=True).order_by('sort_order'):
                modifiers.append({
                    "id": modifier.id,
                    "name": modifier.name,
                    "price": str(modifier.price),
                })
            
            if modifiers:  # Only include groups that have available modifiers
                result.append({
                    "id": group.id,
                    "name": group.name,
                    "menu_item_id": group.menu_item_id,
                    "is_required": group.is_required,
                    "min_select": group.min_select,
                    "max_select": group.max_select,
                    "modifiers": modifiers,
                })
        
        return Response({"modifier_groups": result})

    @action(detail=False, methods=['post'])
    def assign_table(self, request):
        """Assign a table and optional delivery option to the active cart.

        Body: { "table_id": number, "delivery_option": "DINE_IN" | "PICKUP" | "DELIVERY" }
        Returns updated cart snapshot.
        """
        table_id = request.data.get('table_id')
        delivery_option = request.data.get('delivery_option')
        try:
            with transaction.atomic():
                cart, _ = self.get_or_create_cart()
                # Validate and assign table if provided
                if table_id is not None:
                    try:
                        from core.models import Table
                        table = Table.objects.get(pk=int(table_id))
                        cart.table = table
                    except Exception:
                        return Response({"error": "Invalid table_id"}, status=status.HTTP_400_BAD_REQUEST)
                # Assign delivery option if provided
                if delivery_option:
                    valid = [choice[0] for choice in Cart.DELIVERY_CHOICES]
                    if delivery_option not in valid:
                        return Response({"error": f"Invalid delivery_option. Choose from {valid}"}, status=status.HTTP_400_BAD_REQUEST)
                    cart.delivery_option = delivery_option
                cart.save()
                ser = CartSerializer(cart, context={'request': request})
                return Response({"message": "Cart updated", "cart": ser.data})
        except Exception as e:
            return Response({"error": f"Failed to assign table: {e}"}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def apply_coupon(self, request):
        """Apply a coupon code to the cart."""
        cart, _ = self.get_or_create_cart()
        coupon_code = request.data.get('coupon_code', '').strip()
        
        if not coupon_code:
            return Response(
                {'error': 'Coupon code is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            success = cart.apply_coupon(coupon_code)
            if success:
                cart.save()
                serializer = self.get_serializer(cart)
                return Response({
                    'message': 'Coupon applied successfully',
                    'cart': serializer.data
                })
            else:
                return Response(
                    {'error': 'Invalid or expired coupon code'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {'error': f'Failed to apply coupon: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def remove_coupon(self, request):
        """Remove applied coupon from cart."""
        cart, _ = self.get_or_create_cart()
        
        try:
            cart.remove_coupon()
            cart.save()
            serializer = self.get_serializer(cart)
            return Response({
                'message': 'Coupon removed successfully',
                'cart': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': f'Failed to remove coupon: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def set_tip(self, request):
        """Set tip amount or percentage for the cart."""
        cart, _ = self.get_or_create_cart()
        tip_amount = request.data.get('tip_amount')
        tip_percentage = request.data.get('tip_percentage')
        
        if tip_amount is not None and tip_percentage is not None:
            return Response(
                {'error': 'Provide either tip_amount or tip_percentage, not both'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if tip_amount is None and tip_percentage is None:
            return Response(
                {'error': 'Either tip_amount or tip_percentage is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            if tip_amount is not None:
                cart.set_tip(amount=Decimal(str(tip_amount)))
            else:
                cart.set_tip(percentage=Decimal(str(tip_percentage)))
            
            cart.save()
            serializer = self.get_serializer(cart)
            return Response({
                'message': 'Tip updated successfully',
                'cart': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': f'Failed to set tip: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Get cart analytics data."""
        cart, _ = self.get_or_create_cart()
        
        try:
            analytics_data = cart.get_analytics_data()
            return Response(analytics_data)
        except Exception as e:
            return Response(
                {'error': f'Failed to get analytics: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )


class OrderItemViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing individual order items with status tracking.
    """
    serializer_class = OrderItemSerializer
    permission_classes = [AllowAny]  # Allow access for order tracking
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'order__status']
    
    def get_queryset(self):
        """Get order items based on user authentication and order access."""
        if self.request.user.is_authenticated:
            return OrderItem.objects.filter(
                order__user=self.request.user
            ).select_related(
                'order', 'order__user', 'order__table', 'menu_item', 'menu_item__category'
            ).order_by('-created_at')
        else:
            # For anonymous users, only show items from orders in current session
            session_key = self.request.session.session_key
            if session_key:
                return OrderItem.objects.filter(
                    order__source_cart__session_key=session_key
                ).select_related(
                    'order', 'order__user', 'order__table', 'menu_item', 'menu_item__category'
                ).order_by('-created_at')
            return OrderItem.objects.none()
    
    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        """Update order item status with audit trail."""
        order_item = self.get_object()
        new_status = request.data.get('status')
        notes = request.data.get('notes', '')
        
        if not new_status:
            return Response(
                {'error': 'Status is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate status
        if new_status not in dict(order_item.STATUS_CHOICES):
            return Response(
                {'error': 'Invalid status'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Update status with audit trail
            order_item.update_status(
                new_status=new_status,
                user=request.user if request.user.is_authenticated else None,
                notes=notes
            )
            order_item.save()
            
            serializer = self.get_serializer(order_item)
            return Response({
                'message': 'Order item status updated successfully',
                'item': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': f'Failed to update item status: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def by_order(self, request):
        """Get all items for a specific order."""
        order_id = request.query_params.get('order_id')
        
        if not order_id:
            return Response(
                {'error': 'order_id parameter is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Verify order access
            if request.user.is_authenticated:
                order = get_object_or_404(Order, id=order_id, user=request.user)
            else:
                session_key = request.session.session_key
                if not session_key:
                    return Response(
                        {'error': 'No session found'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                order = get_object_or_404(
                    Order, 
                    id=order_id, 
                    source_cart__session_key=session_key
                )
            
            items = order.items.select_related(
                'menu_item', 'menu_item__category'
            ).order_by('created_at')
            
            serializer = self.get_serializer(items, many=True)
            return Response({
                'order_id': order.id,
                'order_status': order.status,
                'items': serializer.data,
                'total_items': items.count()
            })
        except Exception as e:
            return Response(
                {'error': f'Failed to get order items: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def preparation_queue(self, request):
        """Get items in preparation queue (for kitchen staff)."""
        try:
            # Get items that are confirmed or preparing
            queue_items = OrderItem.objects.filter(
                status__in=[OrderItem.STATUS_CONFIRMED, OrderItem.STATUS_PREPARING],
                order__status__in=[Order.STATUS_CONFIRMED, Order.STATUS_PREPARING]
            ).select_related(
                'order', 'menu_item', 'menu_item__category'
            ).order_by('order__confirmed_at', 'created_at')
            
            serializer = self.get_serializer(queue_items, many=True)
            return Response({
                'queue_items': serializer.data,
                'total_items': queue_items.count(),
                'status_breakdown': {
                    'confirmed': queue_items.filter(status=OrderItem.STATUS_CONFIRMED).count(),
                    'preparing': queue_items.filter(status=OrderItem.STATUS_PREPARING).count()
                }
            })
        except Exception as e:
            return Response(
                {'error': f'Failed to get preparation queue: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def validate_integrity(self, request):
        """Validate cart data integrity."""
        cart, _ = self.get_or_create_cart()
        
        try:
            is_valid = cart.validate_cart_integrity()
            return Response({
                'is_valid': is_valid,
                'message': 'Cart integrity validated' if is_valid else 'Cart integrity check failed'
            })
        except Exception as e:
            return Response(
                {'error': f'Failed to validate cart: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )


class OrderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing orders with comprehensive functionality.
    """
    permission_classes = [AllowAny]  # Allow anonymous orders
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'delivery_option']
    
    def get_queryset(self):
        """Get orders based on user authentication with eager loading.

        Staff users see all orders.
        Authenticated users in operational roles (Manager, Cashier, Kitchen, Host)
        also see all orders to support the admin SPA Live Dashboard.
        Regular authenticated users see only their own orders.
        Anonymous users see only orders tied to their current session cart.
        """
        base = Order.objects.select_related('user', 'table').prefetch_related(
            'items__menu_item', 'items__menu_item__category'
        )
        user = getattr(self.request, 'user', None)
        if getattr(user, "is_staff", False):
            return base.order_by('-created_at')
        if getattr(user, 'is_authenticated', False):
            try:
                roles = set(user.groups.values_list('name', flat=True))
            except Exception:
                roles = set()
            if roles.intersection({"Manager", "Cashier", "Kitchen", "Host"}):
                return base.order_by('-created_at')
            return base.filter(user=user).order_by('-created_at')
        # For anonymous users, only show orders from current session
        session_key = self.request.session.session_key
        if session_key:
            return base.filter(source_cart__session_key=session_key).order_by('-created_at')
        return Order.objects.none()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return OrderCreateSerializer
        elif self.action == 'list':
            return OrderListSerializer
        return OrderSerializer
    
    def create(self, request):
        """
        Create a new order from cart.
        """
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data
        cart_uuid = validated_data['cart_uuid']
        
        try:
            with transaction.atomic():
                # Get cart
                cart = get_object_or_404(Cart, cart_uuid=cart_uuid)
                
                # Verify cart ownership
                if request.user.is_authenticated:
                    if cart.user != request.user:
                        return Response(
                            {'error': 'Cart not found'}, 
                            status=status.HTTP_404_NOT_FOUND
                        )
                else:
                    if cart.session_key != request.session.session_key:
                        return Response(
                            {'error': 'Cart not found'}, 
                            status=status.HTTP_404_NOT_FOUND
                        )
                
                # Check if cart has items
                if not cart.items.exists():
                    return Response(
                        {'error': 'Cart is empty'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Recalculate cart totals before creating order
                compute_cart_totals(cart, save=True)
                
                # Create order using the enhanced create_from_cart method
                order = Order.create_from_cart(
                    cart=cart,
                    user=request.user if request.user.is_authenticated else None,
                    notes=validated_data.get('notes', ''),
                    delivery_option=validated_data.get('delivery_option')
                )
                
                # Ensure order totals consistent (defensive)
                compute_order_totals(order, save=True)
                # Return created order
                order_serializer = OrderSerializer(order, context={'request': request})
                return Response({
                    'message': 'Order created successfully',
                    'order': order_serializer.data
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return Response(
                {'error': f'Failed to create order: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def track(self, request, pk=None):
        """
        Track order status and details.
        """
        order = self.get_object()
        
        tracking_info = {
            'order_id': order.id,
            'order_number': f'ORD-{order.id:06d}',
            'status': order.status,
            'created_at': order.created_at,
            'estimated_delivery': order.estimated_delivery_time,
            'delivery_option': order.delivery_option,
            'total_amount': order.total_amount,
            'customer_name': order.customer_name,
            'customer_phone': order.customer_phone
        }
        
        return Response(tracking_info)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """
        Get recent orders for the current user/session.
        """
        recent_orders = self.get_queryset()[:5]
        serializer = OrderListSerializer(recent_orders, many=True, context={'request': request})
        
        return Response({
            'recent_orders': serializer.data,
            'total_orders': self.get_queryset().count()
        })
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel an order if possible."""
        order = self.get_object()
        reason = request.data.get('reason', '')
        
        try:
            if order.can_be_cancelled():
                order.transition_to('cancelled', by_user=(request.user if request.user.is_authenticated else None))
                
                serializer = self.get_serializer(order)
                return Response({
                    'message': 'Order cancelled successfully',
                    'order': serializer.data
                })
            else:
                return Response(
                    {'error': 'Order cannot be cancelled at this stage'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {'error': f'Failed to cancel order: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def refund(self, request, pk=None):
        """Apply refund to an order."""
        order = self.get_object()
        refund_amount = request.data.get('refund_amount')
        reason = request.data.get('reason', '')
        
        if not refund_amount:
            return Response(
                {'error': 'Refund amount is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            refund_amount = Decimal(str(refund_amount))
            if order.can_be_refunded():
                success = order.apply_refund(refund_amount, reason)
                if success:
                    order.save()
                    serializer = self.get_serializer(order)
                    return Response({
                        'message': 'Refund applied successfully',
                        'order': serializer.data
                    })
                else:
                    return Response(
                        {'error': 'Invalid refund amount'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                return Response(
                    {'error': 'Order cannot be refunded'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {'error': f'Failed to apply refund: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        """Update order status with audit trail."""
        order = self.get_object()
        new_status = request.data.get('status')
        reason = request.data.get('reason', '')
        notes = request.data.get('notes', '')
        
        if not new_status:
            return Response(
                {'error': 'Status is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # transition_to validates and supports both simplified and enum statuses
        
        try:
            # Update status via canonical transition method
            order.transition_to(new_status=new_status, by_user=(request.user if request.user.is_authenticated else None))
            
            serializer = self.get_serializer(order)
            return Response({
                'message': 'Order status updated successfully',
                'order': serializer.data,
                # Keep response light; history endpoint returns rich details
                'status_history_count': order.status_history.count()
            })
        except Exception as e:
            return Response(
                {'error': f'Failed to update status: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def status_history(self, request, pk=None):
        """Get complete order status history."""
        order = self.get_object()
        
        try:
            history = order.get_status_history()
            history_data = [
                {
                    'id': h.id,
                    'previous_status': h.previous_status,
                    'new_status': h.new_status,
                    'user': h.user.username if h.user else 'System',
                    'user_id': h.user.id if h.user else None,
                    'reason': h.reason,
                    'notes': h.notes,
                    'timestamp': h.timestamp,
                    'ip_address': h.ip_address,
                    'user_agent': h.user_agent,
                    'metadata': h.metadata
                }
                for h in history
            ]
            
            # Calculate status durations
            status_durations = {}
            for status_choice in order.STATUS_CHOICES:
                status_code = status_choice[0]
                duration = order.get_status_duration(status_code)
                if duration:
                    status_durations[status_code] = {
                        'duration_seconds': duration.total_seconds(),
                        'duration_formatted': str(duration)
                    }
            
            return Response({
                'order_id': order.id,
                'current_status': order.status,
                'history': history_data,
                'status_durations': status_durations,
                'total_changes': len(history_data)
            })
        except Exception as e:
            return Response(
                {'error': f'Failed to get status history: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Get order analytics data."""
        order = self.get_object()
        
        try:
            analytics_data = order.get_analytics_data()
            return Response(analytics_data)
        except Exception as e:
            return Response(
                {'error': f'Failed to get analytics: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def cleanup_expired_carts(self, request):
        """Cleanup expired carts (admin only)."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            deleted_count = Cart.cleanup_expired_carts()
            return Response({
                'message': f'Cleaned up {deleted_count} expired carts'
            })
        except Exception as e:
            return Response(
                {'error': f'Failed to cleanup carts: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
