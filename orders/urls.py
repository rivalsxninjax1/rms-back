# FILE: orders/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import OrderViewSet, SessionCartViewSet, simple_cart_view, cart_expiration_view
from .views_my import MyOrdersAPIView

router = DefaultRouter()
router.register(r"orders", OrderViewSet, basename="orders")
router.register(r"cart", SessionCartViewSet, basename="cart")

urlpatterns = [
    path("cart-simple/", simple_cart_view, name="cart-simple"),
    path("cart-expired/", cart_expiration_view, name="cart-expired"),
    path("", include(router.urls)),
    path("orders/my/", MyOrdersAPIView.as_view(), name="orders-my"),
]
