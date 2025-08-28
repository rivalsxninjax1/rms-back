from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View

from menu.models import MenuItem, MenuCategory

# Copy the _ctx helper
def _ctx(section: str, request: Optional[HttpRequest] = None, **extra: Any) -> Dict[str, Any]:
    """
    Common template context used across storefront pages.
    """
    user = getattr(request, "user", None)
    return {
        "section": section,
        "is_auth": bool(user and user.is_authenticated),
        "user": user,
        # Delivery deep links (read by the frontend to open popups)
        "UBEREATS_ORDER_URL": getattr(__import__("django.conf").conf.settings, "UBEREATS_ORDER_URL", ""),
        "DOORDASH_ORDER_URL": getattr(__import__("django.conf").conf.settings, "DOORDASH_ORDER_URL", ""),
        **extra,
    }

class MenuItemsView(View):
    """
    Menu landing page that loads all menu items from the database.
    """
    template_name = "storefront/menu.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        # Fetch all available menu items with their categories
        items = MenuItem.objects.filter(is_available=True).select_related('category', 'organization').order_by('sort_order', 'name')
        categories = MenuCategory.objects.filter(is_active=True).select_related('organization').order_by('sort_order', 'name')
        
        context = _ctx("menu", request)
        context.update({
            'items': items,
            'categories': categories,
            'DEFAULT_CURRENCY': 'NPR',  # Add default currency
        })
        
        return render(request, self.template_name, context)
