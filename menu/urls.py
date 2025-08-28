from __future__ import annotations

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import MenuItemViewSet, MenuCategoryViewSet, CartView, CartMergeView

app_name = "menu"

router = DefaultRouter()
router.register(r"menu-items", MenuItemViewSet, basename="menu-item")
router.register(r"menu-categories", MenuCategoryViewSet, basename="menu-category")

urlpatterns = [
    # DRF routers for menu data
    path("", include(router.urls)),
    # Minimal cart endpoints used by storefront JS (optional; session-backed)
    path("cart/", CartView.as_view(), name="cart"),
    path("cart/merge/", CartMergeView.as_view(), name="cart-merge"),
]
