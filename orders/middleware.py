# FILE: orders/middleware.py
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from datetime import timedelta


class EnsureCartInitializedMiddleware(MiddlewareMixin):
    """
    Ensures that anonymous users have a cart initialized in their session.
    Also handles cart expiration after 25 minutes of inactivity.
    """
    
    CART_EXPIRY_MINUTES = 25

    def process_request(self, request):
        now = timezone.now()
        
        # Check for cart expiration for both authenticated and anonymous users
        last_activity = request.session.get('cart_last_activity')
        if last_activity:
            try:
                last_activity_time = timezone.datetime.fromisoformat(last_activity)
                if now - last_activity_time > timedelta(minutes=self.CART_EXPIRY_MINUTES):
                    # Cart has expired, clear it
                    self._clear_expired_cart(request)
                    # Set a flag to show expiration message
                    request.session['cart_expired'] = True
            except (ValueError, TypeError):
                # Invalid timestamp, reset activity
                pass
        
        # Update last activity timestamp
        request.session['cart_last_activity'] = now.isoformat()
        
        # Only initialize for anonymous users
        if hasattr(request, 'user') and not request.user.is_authenticated:
            # Check if cart is already initialized to avoid redundant operations
            if not request.session.get("_cart_init_done", False):
                request.session["cart"] = []
                request.session["_cart_init_done"] = True
        elif not hasattr(request, 'user'):
            # User attribute not available yet, initialize cart for all requests
            if not request.session.get("_cart_init_done", False):
                request.session["cart"] = []
                request.session["_cart_init_done"] = True
    
    def _clear_expired_cart(self, request):
        """Clear expired cart for both session and authenticated users."""
        # Clear session cart
        request.session["cart"] = []
        
        # Clear authenticated user's cart if they have one
        if hasattr(request, 'user') and request.user.is_authenticated:
            from orders.models import Order
            try:
                # Find and clear the user's active cart order
                active_order = Order.objects.filter(
                    user=request.user,
                    status='cart'
                ).first()
                if active_order:
                    active_order.delete()
            except Exception:
                # Silently handle any database errors
                pass
