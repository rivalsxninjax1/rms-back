# FILE: orders/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import OrderViewSet, SessionCartViewSet
from .views_my import MyOrdersAPIView

router = DefaultRouter()
router.register(r"orders", OrderViewSet, basename="orders")
router.register(r"cart", SessionCartViewSet, basename="cart")

urlpatterns = [
    path("", include(router.urls)),
    path("orders/my/", MyOrdersAPIView.as_view(), name="orders-my"),
]
