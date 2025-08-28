from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

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


# -----------------------------------------------------------------------------
# Page Views (names kept to match original urls.py from ZIP)
# -----------------------------------------------------------------------------

def home(request: HttpRequest) -> HttpResponse:
    return render(request, "storefront/index.html", _ctx("home", request))


def about(request: HttpRequest) -> HttpResponse:
    return render(request, "storefront/about.html", _ctx("about", request))


def branches(request: HttpRequest) -> HttpResponse:
    return render(request, "storefront/branches.html", _ctx("branches", request))


class MenuItemsView(View):
    """
    Menu landing page that loads all menu items from the database.
    """
    template_name = "storefront/menu.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        from menu.models import MenuItem, MenuCategory
        
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


def menu_item(request: HttpRequest, item_id: int) -> HttpResponse:
    """
    Menu item detail page - fetches actual item from database.
    """
    from menu.models import MenuItem
    from django.shortcuts import get_object_or_404
    
    try:
        item = get_object_or_404(MenuItem, id=item_id, is_available=True)
        context = _ctx("menu-item", request, item_id=item_id)
        context.update({
            'item': item,
            'DEFAULT_CURRENCY': 'NPR',
        })
        return render(request, "storefront/menu_item.html", context)
    except Exception as e:
        # If item not found, redirect to menu
        return redirect("storefront:menu")


def cart(request: HttpRequest) -> HttpResponse:
    return render(request, "storefront/cart.html", _ctx("cart", request))


def checkout(request: HttpRequest) -> HttpResponse:
    """
    Checkout shell; pressing 'Pay' triggers JS → /payments/checkout/ POST.
    """
    return render(request, "storefront/checkout.html", _ctx("checkout", request))


def orders(request: HttpRequest) -> HttpResponse:
    """
    Backwards-compat alias that redirects to /my-orders/ (kept from old code).
    """
    return redirect("storefront:my_orders")


@method_decorator(login_required, name="dispatch")
class MyOrdersView(View):
    """
    Authenticated user orders page; JS loads order history via API.
    """
    template_name = "storefront/my_orders.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(request, self.template_name, _ctx("orders", request))


def contact(request: HttpRequest) -> HttpResponse:
    return render(request, "storefront/contact.html", _ctx("contact", request))


def login_page(request: HttpRequest) -> HttpResponse:
    """
    Renders a login/register shell (the actual auth is JSON via accounts.urls).
    """
    return render(request, "storefront/login.html", _ctx("login", request))


def reservations(request: HttpRequest) -> HttpResponse:
    """
    Reservation flow entry; page renders a calendar/table shell.
    JS hits /api/reservations/... endpoints to check availability and create.
    """
    # Provide any soft hints you want in the UI (non-critical)
    upcoming = request.session.get("sf_upcoming_reservations", []) or []
    recent = request.session.get("sf_recent_reservations", []) or []
    return render(
        request,
        "storefront/reservations.html",
        _ctx("reservations", request, upcoming=upcoming, recent=recent),
    )


# -----------------------------------------------------------------------------
# Small JSON endpoints used by legacy templates/JS
# -----------------------------------------------------------------------------

def api_cart_set_tip(request: HttpRequest) -> JsonResponse:
    """
    Kept for backward compatibility: store a fixed tip in the session so the
    server can read it during payment if needed. New flow uses localStorage.
    """
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed."}, status=405)
    try:
        import json
        body = json.loads(request.body.decode("utf-8"))
        tip = float(body.get("tip") or 0)
    except Exception:
        tip = 0.0
    request.session["sf_tip_fixed"] = max(0.0, tip)
    return JsonResponse({"ok": True, "tip": request.session["sf_tip_fixed"]})


# -----------------------------------------------------------------------------
# Error handlers wired in root urls
# -----------------------------------------------------------------------------

def http_400(request: HttpRequest, exception=None) -> HttpResponse:  # pragma: no cover
    return render(request, "storefront/errors/400.html", _ctx("error", request), status=400)


def http_403(request: HttpRequest, exception=None) -> HttpResponse:  # pragma: no cover
    return render(request, "storefront/errors/403.html", _ctx("error", request), status=403)


def http_404(request: HttpRequest, exception=None) -> HttpResponse:  # pragma: no cover
    return render(request, "storefront/errors/404.html", _ctx("error", request), status=404)


def http_500(request: HttpRequest) -> HttpResponse:  # pragma: no cover
    return render(request, "storefront/errors/500.html", _ctx("error", request), status=500)
