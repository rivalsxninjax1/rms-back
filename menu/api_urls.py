# menu/api_urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .api_views import (
    MenuCategoryViewSet, MenuItemViewSet, ModifierGroupViewSet, ModifierViewSet,
    MenuDisplayViewSet
)

# Create router for API endpoints
router = DefaultRouter()
router.register(r'categories', MenuCategoryViewSet, basename='menucategory')
router.register(r'items', MenuItemViewSet, basename='menuitem')
router.register(r'modifier-groups', ModifierGroupViewSet, basename='modifiergroup')
router.register(r'modifiers', ModifierViewSet, basename='modifier')
router.register(r'display', MenuDisplayViewSet, basename='menudisplay')

urlpatterns = [
    path('', include(router.urls)),
]

# URL patterns will be:
# Public API:
# /menu/api/categories/ - List menu categories
# /menu/api/categories/{id}/ - Retrieve specific category
# /menu/api/categories/{id}/items/ - Get items for category
# /menu/api/items/ - List menu items (with search, filters)
# /menu/api/items/{id}/ - Retrieve specific item
# /menu/api/items/{id}/modifiers/ - Get modifiers for item
# /menu/api/items/featured/ - Get featured items
# /menu/api/items/popular/ - Get popular items
# /menu/api/modifier-groups/ - List modifier groups
# /menu/api/modifier-groups/{id}/ - Retrieve specific modifier group
# /menu/api/modifier-groups/{id}/modifiers/ - Get modifiers for group
# /menu/api/modifiers/ - List modifiers
# /menu/api/modifiers/{id}/ - Retrieve specific modifier
#
# Admin API:
# /menu/api/admin/categories/ - Full CRUD for categories
# /menu/api/admin/items/ - Full CRUD for items
# /menu/api/admin/items/{id}/toggle_availability/ - Toggle item availability