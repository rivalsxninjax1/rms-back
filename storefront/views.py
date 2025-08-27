# FILE: storefront/views.py
from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Q
from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import TemplateView
from django.utils import timezone


from decimal import Decimal
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# Optional, robust imports
try:
    from menu.models import MenuItem
except Exception:  # pragma: no cover
    MenuItem = None

try:
    from orders.models import Order
except Exception:  # pragma: no cover
    Order = None

# Reservations models (optional)
try:
    from reservations.models import Reservation, Table as RMSTable
except Exception:  # pragma: no cover
    Reservation = None
    RMSTable = None


def _ctx(page: str, **extra):
    ctx = {"page": page}
    ctx.update(extra)
    return ctx


# -------------------------
# Function-based pages (existing)
# -------------------------
def home(request):
    return render(request, "storefront/index.html", _ctx("home"))

def about(request):
    return render(request, "storefront/about.html", _ctx("about"))

def branches(request):
    return render(request, "storefront/branches.html", _ctx("branches"))

def menu_item(request, item_id: int):
    if MenuItem is None:
        return render(request, "storefront/menu_item.html", _ctx("menu_item", item=None))
    item = get_object_or_404(MenuItem, pk=item_id)
    return render(request, "storefront/menu_item.html", _ctx("menu_item", item=item))

def cart(request):
    # Provide active tables for Dine-in selection (from RMS Admin → Tables)
    tables = []
    if RMSTable:
        try:
            tables = RMSTable.objects.filter(is_active=True).select_related("location").order_by("location__name", "table_number")
        except Exception:
            tables = []
    return render(request, "storefront/cart.html", _ctx("cart", tables=tables))

def checkout(request):
    return render(request, "storefront/checkout.html", _ctx("checkout"))

def orders(request):
    return render(request, "storefront/orders.html", _ctx("orders"))

def contact(request):
    return render(request, "storefront/contact.html", _ctx("contact"))

def login_page(request):
    return render(request, "storefront/login.html", _ctx("login"))

def reservations(request):
    """
    Show the user's upcoming and recent reservations (if logged in).
    If not logged in or no reservations app, show the booking UI only.
    """
    upcoming, recent = [], []
    if Reservation and request.user.is_authenticated:
        try:
            now = timezone.now()
            qs = Reservation.objects.all()
            # Match by user if there is a FK; else by email field if available
            if hasattr(Reservation, "user_id"):
                qs = qs.filter(user=request.user)
            elif hasattr(Reservation, "email"):
                email = (getattr(request.user, "email", "") or "").strip()
                if email:
                    qs = qs.filter(email__iexact=email)
            # Split into upcoming vs recent (past 30 days)
            upcoming = qs.filter(start_time__gte=now).select_related("table", "table__location").order_by("start_time")[:50]
            recent = qs.filter(start_time__lt=now, start_time__gte=now - timezone.timedelta(days=30)).select_related("table", "table__location").order_by("-start_time")[:50]
        except Exception:
            pass
    return render(request, "storefront/reservations.html", _ctx("reservations", upcoming=upcoming, recent=recent))


# -------------------------
# Class-based views
# -------------------------
class MenuItemsView(TemplateView):
    template_name = "storefront/menu_items.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["item_id"] = int(kwargs.get("item_id") or 0)

        qs = MenuItem.objects.all() if MenuItem else []
        if MenuItem:
            try:
                MenuItem._meta.get_field("is_active")
            except FieldDoesNotExist:
                pass
            else:
                qs = qs.filter(is_active=True)

            try:
                MenuItem._meta.get_field("category")
            except FieldDoesNotExist:
                pass
            else:
                qs = qs.select_related("category")

        order_by = ["name"]
        try:
            MenuItem._meta.get_field("rank")
        except FieldDoesNotExist:
            pass
        else:
            order_by = ["-rank", "name"]

        qs = qs.order_by(*order_by)
        ctx["items"] = qs
        ctx.update(_ctx("menu"))
        return ctx


class MyOrdersView(LoginRequiredMixin, TemplateView):
    template_name = "storefront/my_orders.html"
    login_url = reverse_lazy("storefront:login")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if Order is None:
            ctx["orders"] = []
            return ctx

        paid_q = Q(payment__is_paid=True) | Q(is_paid=True) | Q(status="PAID")
        qs = (
            Order.objects.filter(Q(created_by=self.request.user) & paid_q)
            .select_related("payment")
            .prefetch_related("items__menu_item")
            .order_by("-created_at")
        )
        ctx["orders"] = qs
        ctx.update(_ctx("my_orders"))
        return ctx


# -------------------------
# Error handlers (as before)
# -------------------------
def http_400(request, exception=None):
    return render(request, "errors/400.html", status=400)

def http_403(request, exception=None):
    return render(request, "errors/403.html", status=403)

def http_404(request, exception=None):
    return render(request, "errors/404.html", status=404)

def http_500(request):
    return render(request, "errors/500.html", status=500)
def _ctx(page, **extra):
    # existing helper in your file; if not present, just return extra
    data = {"page": page}
    data.update(extra)
    return data

@require_POST
@csrf_exempt
def api_cart_set_tip(request):
    try:
        body = json.loads(request.body.decode() or "{}")
    except Exception:
        body = {}
    raw = body.get("tip_amount", 0)
    try:
        tip = max(Decimal(str(raw)), Decimal("0.00"))
    except Exception:
        tip = Decimal("0.00")
    request.session["cart_tip_amount"] = float(tip)
    request.session.modified = True
    return JsonResponse({"ok": True, "tip_amount": float(tip)})