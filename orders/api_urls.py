# orders/api_urls.py
from __future__ import annotations

from django.urls import path, include
from . import views
from rest_framework.routers import DefaultRouter

from .api_views import CartViewSet, OrderViewSet, OrderItemViewSet

# Create router for comprehensive REST API endpoints
router = DefaultRouter()
router.register(r'carts', CartViewSet, basename='cart')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'order-items', OrderItemViewSet, basename='orderitem')

urlpatterns = [
    path("", include(router.urls)),
    # Third-party delivery webhooks (Uber Eats / DoorDash)
    path('webhooks/ubereats/', views.ubereats_webhook, name='ubereats_webhook'),
    path('webhooks/doordash/', views.doordash_webhook, name='doordash_webhook'),
]

# The router automatically creates the following endpoints:
# 
# Cart endpoints:
# GET    /api/carts/                    - List/get current cart
# POST   /api/carts/                    - Create new cart
# GET    /api/carts/{id}/               - Retrieve specific cart
# PUT    /api/carts/{id}/               - Update cart
# PATCH  /api/carts/{id}/               - Partial update cart
# DELETE /api/carts/{id}/               - Delete cart
# POST   /api/carts/add_item/           - Add item to cart
# PATCH  /api/carts/update_item/        - Update cart item
# DELETE /api/carts/remove_item/        - Remove item from cart
# DELETE /api/carts/clear/               - Clear cart
# GET    /api/carts/summary/            - Get cart summary
# POST   /api/carts/merge/              - Merge carts
# GET    /api/carts/modifiers/          - Get available modifiers
# POST   /api/carts/apply_coupon/       - Apply coupon code
# POST   /api/carts/remove_coupon/      - Remove coupon
# POST   /api/carts/set_tip/            - Set tip amount/percentage
# GET    /api/carts/analytics/          - Get cart analytics
# POST   /api/carts/validate_integrity/ - Validate cart integrity
#
# Order endpoints:
# GET    /api/orders/                   - List orders
# POST   /api/orders/                   - Create order from cart
# GET    /api/orders/{id}/              - Retrieve specific order
# PUT    /api/orders/{id}/              - Update order
# PATCH  /api/orders/{id}/              - Partial update order
# DELETE /api/orders/{id}/              - Delete order
# GET    /api/orders/{id}/track/        - Track order status
# GET    /api/orders/recent/            - Get recent orders
# POST   /api/orders/{id}/cancel/       - Cancel order
# POST   /api/orders/{id}/refund/       - Apply refund
# PATCH  /api/orders/{id}/update_status/ - Update order status
# GET    /api/orders/{id}/status_history/ - Get order status history
# GET    /api/orders/{id}/analytics/    - Get order analytics
# POST   /api/orders/cleanup_expired_carts/ - Cleanup expired carts (admin)
#
# Order Item endpoints:
# GET    /api/order-items/              - List order items (filtered by user/session)
# GET    /api/order-items/{id}/         - Retrieve specific order item
# PATCH  /api/order-items/{id}/update_status/ - Update order item status
# GET    /api/order-items/order/{order_id}/ - Get all items for specific order
# GET    /api/order-items/preparation_queue/ - Get items in preparation queue (kitchen)
