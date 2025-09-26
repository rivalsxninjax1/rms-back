# rms-back/storefront/views.py
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.urls import reverse
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt

from menu.models import MenuItem, MenuCategory, Modifier, ModifierGroup
from core.models import Table, Organization, Location
from orders.models import Cart, CartItem, Order
from orders.utils.cart import get_or_create_cart
from orders.utils.cart import merge_carts
from coupons.services import find_active_coupon, compute_discount_for_order
from payments.services import create_checkout_session
from core.seed import seed_default_tables
from engagement.models import ReservationHold

def _to_cents(amount):
    d = Decimal(str(amount or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int((d * 100).to_integral_value(rounding=ROUND_HALF_UP))

def _touch_expiration(cart: Cart) -> None:
    cart.set_expiration(minutes=25)
    cart.save(update_fields=["expires_at", "updated_at", "last_activity"])

def _cart_or_404(request: HttpRequest) -> Cart:
    result = get_or_create_cart(request)
    cart = result.cart
    _touch_expiration(cart)
    return cart

def _is_htmx(request: HttpRequest) -> bool:
    # Treat both HTMX and classic AJAX (XMLHttpRequest) as JSON clients
    if request.headers.get('HX-Request', '').lower() == 'true':
        return True
    xr = request.headers.get('X-Requested-With', '')
    return xr.lower() == 'xmlhttprequest'


def _ensure_min_tables(min_tables: int = 6) -> None:
    """If there are no tables in RMS admin, seed a sensible default set.
    This is a development convenience to avoid empty dine-in flows.
    Idempotent: only seeds when Table count is zero.
    """
    try:
        if Table.objects.exists():
            return
        # Create a default organization and location
        org, _ = Organization.objects.get_or_create(name="Default Organization")
        loc, _ = Location.objects.get_or_create(organization=org, name="Main")
        # Seed tables: A1..A6 (or min_tables)
        import string
        letters = ["A", "B"]
        created = 0
        for letter in letters:
            for num in range(1, min_tables + 1):
                if created >= min_tables:
                    break
                Table.objects.get_or_create(
                    location=loc,
                    table_number=f"{letter}{num}",
                    defaults={"capacity": 4, "is_active": True, "table_type": "dining"},
                )
                created += 1
    except Exception:
        # If seeding fails, silently ignore; UI will just show no tables
        pass

@require_GET
def menu_list(request: HttpRequest) -> HttpResponse:
    categories = MenuCategory.objects.filter(is_active=True).order_by("sort_order", "name")
    items = (
        MenuItem.objects.filter(is_available=True)
        .select_related("category")
        .order_by("sort_order", "name")[:200]
    )
    cart = _cart_or_404(request)
    return render(request, "storefront/menu_list.html", {"categories": categories, "items": items, "cart": cart})

@require_GET
def item_detail(request: HttpRequest, slug: str) -> HttpResponse:
    item = get_object_or_404(MenuItem.objects.select_related("category"), slug=slug, is_available=True)
    cart = _cart_or_404(request)
    groups = (
        ModifierGroup.objects.filter(menu_item=item, is_active=True)
        .prefetch_related("modifiers")
        .order_by("name")
    )
    return render(request, "storefront/item_detail.html", {"item": item, "groups": groups, "cart": cart})

@require_GET
def cart_bar(request: HttpRequest) -> HttpResponse:
    cart = _cart_or_404(request)
    return render(request, "storefront/_cart_bar.html", {"cart": cart})

@require_GET
def cart_full(request: HttpRequest) -> HttpResponse:
    cart = _cart_or_404(request)
    _ensure_min_tables()
    now = timezone.now()
    in_two = now + timedelta(hours=2)
    # Show all active tables; mark reserved separately so UI can disable/select accordingly
    tables = Table.objects.filter(is_active=True).order_by("location_id", "table_number")
    sel_ids = []
    if cart.table_id:
        sel_ids.append(cart.table_id)
    try:
        if isinstance(cart.metadata, dict):
            extra = cart.metadata.get("tables") or []
            for tid in extra:
                if isinstance(tid, int) and tid not in sel_ids:
                    sel_ids.append(tid)
    except Exception:
        pass
    # Compute reserved ids in the next 2 hours
    try:
        from reservations.models import Reservation
        active_status = ["pending", "confirmed"]
        reserved_ids = set(
            Reservation.objects.filter(
                status__in=active_status,
                start_time__lt=in_two,
                end_time__gt=now,
            ).values_list("table_id", flat=True)
        )
    except Exception:
        reserved_ids = set()
    return render(request, "storefront/cart_full.html", {"cart": cart, "tables": tables, "sel_table_ids": sel_ids, "reserved_ids": reserved_ids})

@require_GET
def order_on_ubereats(request: HttpRequest) -> HttpResponse:
    url = getattr(settings, "UBEREATS_ORDER_URL", "")
    if not url:
        return HttpResponseBadRequest("UberEats order URL not configured.")
    return HttpResponseRedirect(url)

@require_GET
def order_on_doordash(request: HttpRequest) -> HttpResponse:
    url = getattr(settings, "DOORDASH_ORDER_URL", "")
    if not url:
        return HttpResponseBadRequest("DoorDash order URL not configured.")
    return HttpResponseRedirect(url)

@require_POST
@transaction.atomic
def cart_add(request: HttpRequest) -> HttpResponse:
    cart = _cart_or_404(request)
    menu_id = request.POST.get("menu_id")
    qty = int(request.POST.get("qty", "1"))
    if not menu_id:
        return HttpResponseBadRequest("Missing menu_id")

    item = get_object_or_404(MenuItem, pk=menu_id, is_available=True)
    modifier_ids = [int(x) for x in request.POST.get("modifiers", "").split(",") if x.strip().isdigit()]
    valid_mods = list(Modifier.objects.filter(id__in=modifier_ids, is_available=True))
    selected_mods = sorted([
        {"modifier_id": m.id, "quantity": 1} for m in valid_mods
    ], key=lambda d: d["modifier_id"])

    line = CartItem.objects.filter(cart=cart, menu_item=item, selected_modifiers=selected_mods).first()
    if line:
        line.quantity = line.quantity + max(1, qty)
        line.save(update_fields=["quantity", "updated_at"])
    else:
        CartItem.objects.create(
            cart=cart,
            menu_item=item,
            quantity=max(1, qty),
            unit_price=item.price,
            selected_modifiers=selected_mods,
        )

    cart.calculate_totals(); cart.save()
    if _is_htmx(request):
        html_bar = render_to_string("storefront/_cart_bar.html", {"cart": cart}, request=request)
        return JsonResponse({"ok": True, "bar": html_bar})
    # Simple HTML: redirect back to menu (or referrer) so page renders normally
    return HttpResponseRedirect(request.META.get('HTTP_REFERER') or reverse('storefront:menu_list'))

@require_POST
@transaction.atomic
def cart_update(request: HttpRequest) -> HttpResponse:
    cart = _cart_or_404(request)
    line_id = request.POST.get("line_id")
    try:
        delta = int(request.POST.get("delta", "0"))
    except Exception:
        delta = 0
    if not line_id or delta == 0:
        return HttpResponseBadRequest("Missing line_id or delta")
    # Be resilient: if the line is missing, just refresh cart instead of 404
    line = CartItem.objects.filter(pk=line_id, cart=cart).first()
    if line:
        new_qty = max(0, int(line.quantity) + delta)
        if new_qty == 0:
            line.delete()
        else:
            line.quantity = new_qty
            line.save(update_fields=["quantity", "updated_at"])
    # Always recalc and return current cart snapshot
    cart.calculate_totals(); cart.save()
    if _is_htmx(request):
        html_cart = render_to_string("storefront/_cart_items.html", {"cart": cart}, request=request)
        html_totals = render_to_string("storefront/_cart_totals.html", {"cart": cart}, request=request)
        html_bar = render_to_string("storefront/_cart_bar.html", {"cart": cart}, request=request)
        return JsonResponse({"ok": True, "cart": html_cart, "totals": html_totals, "bar": html_bar})
    return HttpResponseRedirect(reverse('storefront:cart_full'))

@require_POST
@transaction.atomic
def cart_remove(request: HttpRequest) -> HttpResponse:
    cart = _cart_or_404(request)
    line_id = request.POST.get("line_id")
    if not line_id:
        return HttpResponseBadRequest("Missing line_id")
    # Resilient remove: if not found, treat as already removed
    line = CartItem.objects.filter(pk=line_id, cart=cart).first()
    if line:
        line.delete()
    cart.calculate_totals(); cart.save()
    if _is_htmx(request):
        html_cart = render_to_string("storefront/_cart_items.html", {"cart": cart}, request=request)
        html_totals = render_to_string("storefront/_cart_totals.html", {"cart": cart}, request=request)
        html_bar = render_to_string("storefront/_cart_bar.html", {"cart": cart}, request=request)
        return JsonResponse({"ok": True, "cart": html_cart, "totals": html_totals, "bar": html_bar})
    return HttpResponseRedirect(reverse('storefront:cart_full'))

@require_POST
@transaction.atomic
def cart_option(request: HttpRequest) -> HttpResponse:
    cart = _cart_or_404(request)
    order_type = (request.POST.get("order_type") or "").upper()
    table_id = request.POST.get("table_id")

    if order_type not in {"DINE_IN", "TAKEAWAY", "UBEREATS", "DOORDASH"}:
        return HttpResponseBadRequest("Invalid order_type")

    # Determine requested option but don't violate DB constraints
    requested_option = order_type
    if requested_option == "DINE_IN":
        # If no table provided, just render options with DINE_IN selected (no save)
        if not (request.POST.getlist("table_ids") or request.POST.get("table_id")):
            now = timezone.now()
            in_two = now + timedelta(hours=2)
            _ensure_min_tables()
            tables = Table.objects.filter(is_active=True).order_by("location_id", "table_number")
            sel_ids = []
            if cart.table_id:
                sel_ids.append(cart.table_id)
            if isinstance(cart.metadata, dict):
                for tid in (cart.metadata.get("tables") or []):
                    if isinstance(tid, int) and tid not in sel_ids:
                        sel_ids.append(tid)
            if _is_htmx(request):
                html_opts = render_to_string(
                    "storefront/_order_options.html",
                    {"cart": cart, "tables": tables, "sel_table_ids": sel_ids, "sel_override": "DINE_IN"},
                    request=request,
                )
                table_modal = render_to_string(
                    "storefront/_table_modal.html",
                    {"cart": cart, "tables": tables, "sel_table_ids": sel_ids},
                    request=request,
                )
                html_bar = render_to_string("storefront/_cart_bar.html", {"cart": cart}, request=request)
                return JsonResponse({"ok": True, "options": html_opts, "bar": html_bar, "table_modal": table_modal})
            return HttpResponseRedirect(reverse('storefront:cart_full'))
        # We have table(s); safe to persist DINE_IN
        cart.delivery_option = Cart.DELIVERY_DINE_IN
    elif requested_option == "TAKEAWAY":
        cart.delivery_option = Cart.DELIVERY_PICKUP
    else:
        cart.delivery_option = Cart.DELIVERY_DELIVERY

    meta = cart.metadata or {}
    meta["provider"] = None
    if order_type in {"UBEREATS", "DOORDASH"}:
        meta["provider"] = order_type

    # Handle single or multiple table selection
    table_ids_raw = request.POST.getlist("table_ids") or []
    if not table_ids_raw:
        ids_csv = request.POST.get("table_ids", "").strip()
        if ids_csv:
            table_ids_raw = [x for x in ids_csv.split(",") if x]
    table_ids: list[int] = []
    for x in table_ids_raw:
        try:
            table_ids.append(int(x))
        except Exception:
            continue
    if cart.delivery_option == Cart.DELIVERY_DINE_IN:
        # Allow switching to Dine-in without forcing a table immediately; apply table(s) only if provided
        if table_ids or table_id:
            primary_id = None
            if table_ids:
                primary_id = table_ids[0]
            elif table_id:
                primary_id = int(table_id)
            table = get_object_or_404(Table, pk=primary_id)
            cart.table = table
            # Persist all selected tables in metadata
            sel_list = table_ids if table_ids else ([primary_id] if primary_id else [])
            meta["tables"] = sel_list
            # Do not create a hold at selection time; holds are created after payment only.
            # This prevents blocking other days/times before checkout completes.
    else:
        cart.table = None
        meta.pop("tables", None)

    # Apply platform service fees if configured
    service_fee = Decimal("0.00")
    if meta.get("provider") == "UBEREATS":
        try:
            fee = getattr(settings, "UBEREATS_FEE", 0) or 0
            service_fee = Decimal(str(fee))
        except Exception:
            service_fee = Decimal("0.00")
    elif meta.get("provider") == "DOORDASH":
        try:
            fee = getattr(settings, "DOORDASH_FEE", 0) or 0
            service_fee = Decimal(str(fee))
        except Exception:
            service_fee = Decimal("0.00")

    cart.service_fee = service_fee
    cart.metadata = meta
    cart.calculate_totals(); cart.save(update_fields=[
        "delivery_option", "table", "metadata", "service_fee",
        "subtotal", "modifier_total", "tax_amount", "total", "updated_at"
    ])
    # Recompute available tables for rendering
    now = timezone.now()
    in_two = now + timedelta(hours=2)
    tables = Table.objects.filter(is_active=True).exclude(
        reservations__start_time__lt=in_two, reservations__end_time__gt=now
    ).order_by("location_id", "table_number")
    sel_ids = []
    if cart.table_id:
        sel_ids.append(cart.table_id)
    if isinstance(cart.metadata, dict):
        for tid in (cart.metadata.get("tables") or []):
            if isinstance(tid, int) and tid not in sel_ids:
                sel_ids.append(tid)
    if _is_htmx(request):
        html_opts = render_to_string("storefront/_order_options.html", {"cart": cart, "tables": tables, "sel_table_ids": sel_ids}, request=request)
        html_totals = render_to_string("storefront/_cart_totals.html", {"cart": cart}, request=request)
        html_bar = render_to_string("storefront/_cart_bar.html", {"cart": cart}, request=request)
        return JsonResponse({"ok": True, "options": html_opts, "totals": html_totals, "bar": html_bar})
    return HttpResponseRedirect(reverse('storefront:cart_full'))

@require_POST
@transaction.atomic
def cart_tip(request: HttpRequest) -> HttpResponse:
    cart = _cart_or_404(request)
    amount_raw = request.POST.get("amount", "0")
    try:
        tip = Decimal(str(amount_raw or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return HttpResponseBadRequest("Invalid tip")
    if tip < 0:
        return HttpResponseBadRequest("Tip must be >= 0")
    cart.tip_amount = tip
    cart.tip_percentage = None
    cart.calculate_totals(); cart.save(update_fields=["tip_amount", "tip_percentage", "subtotal", "total", "updated_at"])
    if _is_htmx(request):
        html_cart = render_to_string("storefront/_cart_totals.html", {"cart": cart}, request=request)
        html_bar = render_to_string("storefront/_cart_bar.html", {"cart": cart}, request=request)
        return JsonResponse({"ok": True, "totals": html_cart, "bar": html_bar})
    return HttpResponseRedirect(reverse('storefront:cart_full'))

@csrf_exempt  # Avoid CSRF issues for AJAX checkout POST
@require_POST
def cart_checkout(request: HttpRequest) -> HttpResponse:
    cart = _cart_or_404(request)
    if hasattr(cart, "is_expired") and cart.is_expired():
        return JsonResponse({"ok": False, "error": "Your cart has expired. Please rebuild your order."}, status=409)
    if cart.delivery_option == Cart.DELIVERY_DINE_IN and not cart.table_id:
        return JsonResponse({"ok": False, "error": "Please select a table for dine-in."}, status=400)
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return JsonResponse({"ok": False, "auth_required": True}, status=401)

    # If customer selected a marketplace provider, redirect to its URL
    try:
        provider = None
        if isinstance(cart.metadata, dict):
            provider = (cart.metadata.get("provider") or "").upper() or None
        if cart.delivery_option == Cart.DELIVERY_DELIVERY and provider in {"UBEREATS", "DOORDASH"}:
            target = reverse('storefront:order_on_ubereats') if provider == "UBEREATS" else reverse('storefront:order_on_doordash')
            return JsonResponse({"ok": True, "redirect_url": target})
    except Exception:
        pass

    cart.calculate_totals(); cart.save()
    order = Order.create_from_cart(cart)
    # Persist coupon as OrderExtras for Stripe discount logic (payments.services)
    try:
        from engagement.models import OrderExtras
        if getattr(order, "coupon_discount", 0):
            OrderExtras.objects.update_or_create(
                order=order,
                name="coupon_discount",
                defaults={"amount": order.coupon_discount},
            )
    except Exception:
        pass
    # Build absolute URLs using the current request host to preserve session domain
    try:
        suc = request.build_absolute_uri(reverse('payments:checkout-success'))
        can = request.build_absolute_uri(reverse('payments:checkout-cancel'))
    except Exception:
        suc = None; can = None
    session = create_checkout_session(order, success_url=suc, cancel_url=can)
    redirect_url = ""
    try:
        # Stripe SDK returns an object with attribute access
        redirect_url = getattr(session, "url", "")
        if not redirect_url and isinstance(session, dict):
            redirect_url = session.get("url", "")
    except Exception:
        redirect_url = ""
    return JsonResponse({"ok": True, "redirect_url": redirect_url})

@require_POST
@transaction.atomic
def cart_clear(request: HttpRequest) -> HttpResponse:
    cart = _cart_or_404(request)
    for it in cart.items.all():
        it.delete()
    cart.calculate_totals(); cart.save()
    if _is_htmx(request):
        html_cart = render_to_string("storefront/_cart_items.html", {"cart": cart}, request=request)
        html_totals = render_to_string("storefront/_cart_totals.html", {"cart": cart}, request=request)
        html_bar = render_to_string("storefront/_cart_bar.html", {"cart": cart}, request=request)
        return JsonResponse({"ok": True, "cart": html_cart, "totals": html_totals, "bar": html_bar})
    return HttpResponseRedirect(reverse('storefront:cart_full'))


@csrf_exempt
@require_POST
def cart_merge_session(request: HttpRequest) -> HttpResponse:
    """If authenticated, merge any active session cart into the user's cart.
    No-op for guests. Returns JSON suitable for AJAX.
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return JsonResponse({"ok": False, "detail": "auth required"}, status=401)
    # Find a guest cart tied to current session
    guest = (
        Cart.objects.filter(session_key=request.session.session_key, user__isnull=True, status=Cart.STATUS_ACTIVE)
        .order_by("-updated_at")
        .first()
    )
    # Get/create user cart
    user_cart = get_or_create_cart(request).cart
    if not guest or guest.pk == user_cart.pk:
        return JsonResponse({"ok": True, "merged": False})
    try:
        stats = merge_carts(guest, user_cart)
    except Exception:
        stats = {"moved": 0, "merged": 0, "created": 0}
    # Return refreshed bar HTML for convenience
    html_bar = render_to_string("storefront/_cart_bar.html", {"cart": user_cart}, request=request)
    return JsonResponse({"ok": True, "merged": True, "stats": stats, "bar": html_bar})


@require_POST
@transaction.atomic
def cart_extras(request: HttpRequest) -> HttpResponse:
    """Update selected extras for a specific cart line."""
    cart = _cart_or_404(request)
    line_id = request.POST.get("line_id")
    if not line_id:
        return HttpResponseBadRequest("Missing line_id")
    line = get_object_or_404(CartItem, pk=line_id, cart=cart)

    modifier_ids = [int(x) for x in request.POST.get("modifiers", "").split(",") if x.strip().isdigit()]
    valid_mods = list(Modifier.objects.filter(id__in=modifier_ids, is_available=True))
    selected_mods = sorted([
        {"modifier_id": m.id, "quantity": 1} for m in valid_mods
    ], key=lambda d: d["modifier_id"])

    line.selected_modifiers = selected_mods
    line.save(update_fields=["selected_modifiers", "updated_at"])
    cart.calculate_totals(); cart.save()
    if _is_htmx(request):
        html_cart = render_to_string("storefront/_cart_items.html", {"cart": cart}, request=request)
        html_totals = render_to_string("storefront/_cart_totals.html", {"cart": cart}, request=request)
        html_bar = render_to_string("storefront/_cart_bar.html", {"cart": cart}, request=request)
        return JsonResponse({"ok": True, "cart": html_cart, "totals": html_totals, "bar": html_bar})
    return HttpResponseRedirect(reverse('storefront:cart_full'))


@require_GET
def cart_extras_modal(request: HttpRequest) -> HttpResponse:
    """Return modal HTML to edit extras for a cart line."""
    cart = _cart_or_404(request)
    line_id = request.GET.get("line_id")
    if not line_id:
        return HttpResponseBadRequest("Missing line_id")
    line = get_object_or_404(CartItem.objects.select_related("menu_item"), pk=line_id, cart=cart)
    groups = (
        ModifierGroup.objects.filter(menu_item=line.menu_item, is_active=True)
        .prefetch_related("modifiers")
        .order_by("name")
    )
    # Extract currently selected modifier ids
    selected_ids = set()
    try:
        for m in (line.selected_modifiers or []):
            mid = m.get("modifier_id")
            if mid:
                selected_ids.add(int(mid))
    except Exception:
        selected_ids = set()
    return render(request, "storefront/_extras_modal.html", {
        "line": line,
        "groups": groups,
        "selected_ids": selected_ids,
    })


@require_GET
def cart_table_modal(request: HttpRequest) -> HttpResponse:
    """Return modal HTML to select table(s) for dine-in."""
    cart = _cart_or_404(request)
    now = timezone.now()
    in_two = now + timedelta(hours=2)
    _ensure_min_tables()
    tables = Table.objects.filter(is_active=True).order_by("location_id", "table_number")
    sel_ids: list[int] = []
    if cart.table_id:
        sel_ids.append(cart.table_id)
    if isinstance(cart.metadata, dict):
        for tid in (cart.metadata.get("tables") or []):
            if isinstance(tid, int) and tid not in sel_ids:
                sel_ids.append(tid)
    # Compute reserved ids in next 2 hours and active holds
    try:
        from reservations.models import Reservation
        active_status = ["pending", "confirmed"]
        reserved_ids = set(
            Reservation.objects.filter(
                status__in=active_status,
                start_time__lt=in_two,
                end_time__gt=now,
            ).values_list("table_id", flat=True)
        )
    except Exception:
        reserved_ids = set()
    try:
        hold_ids = set(
            ReservationHold.objects.filter(status="PENDING", expires_at__gt=now).values_list("table_id", flat=True)
        )
        reserved_ids = reserved_ids.union(hold_ids)
    except Exception:
        pass
    return render(request, "storefront/_table_modal.html", {
        "cart": cart,
        "tables": tables,
        "sel_table_ids": sel_ids,
        "reserved_ids": reserved_ids,
    })


@require_POST
@transaction.atomic
def cart_seed_tables(request: HttpRequest) -> HttpResponse:
    """Seed default tables and return refreshed modal HTML.
    Useful when DB is empty and no tables exist.
    """
    # Seed a minimal set
    seed_default_tables(min_tables=6)
    # Then render modal
    return cart_table_modal(request)


@require_POST
@transaction.atomic
def cart_coupon(request: HttpRequest) -> HttpResponse:
    """Apply a coupon code and refresh totals."""
    cart = _cart_or_404(request)
    code = (request.POST.get("code") or "").strip()
    if not code:
        return HttpResponseBadRequest("Missing code")

    coupon = find_active_coupon(code)
    if not coupon:
        return JsonResponse({"ok": False, "error": "Invalid or expired coupon"}, status=400)

    pre_total = cart.subtotal + cart.modifier_total
    discount, _breakdown = compute_discount_for_order(
        coupon=coupon,
        order_total=pre_total,
        item_count=sum(it.quantity for it in cart.items.all()),
        user=getattr(request, "user", None),
        is_first_order=False,
    )
    cart.applied_coupon_code = coupon.code
    cart.coupon_discount = discount
    cart.calculate_totals(); cart.save()
    if _is_htmx(request):
        html_totals = render_to_string("storefront/_cart_totals.html", {"cart": cart}, request=request)
        html_bar = render_to_string("storefront/_cart_bar.html", {"cart": cart}, request=request)
        # Also refresh order options panel so the coupon section reflects applied code
        # Recompute selected table ids similarly to cart_full/cart_option
        _ensure_min_tables()
        tables = Table.objects.filter(is_active=True).order_by("location_id", "table_number")
        sel_ids = []
        if cart.table_id:
            sel_ids.append(cart.table_id)
        try:
            if isinstance(cart.metadata, dict):
                extra = cart.metadata.get("tables") or []
                for tid in extra:
                    if isinstance(tid, int) and tid not in sel_ids:
                        sel_ids.append(tid)
        except Exception:
            pass
        html_opts = render_to_string(
            "storefront/_order_options.html",
            {"cart": cart, "tables": tables, "sel_table_ids": sel_ids},
            request=request,
        )
        return JsonResponse({
            "ok": True,
            "totals": html_totals,
            "bar": html_bar,
            "options": html_opts,
            "code": coupon.code,
            "discount": str(discount)
        })
    return HttpResponseRedirect(reverse('storefront:cart_full'))


@require_GET
def my_orders(request: HttpRequest) -> HttpResponse:
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return render(request, "storefront/my_orders.html", {"orders": [], "need_login": True})
    orders = Order.objects.filter(user=request.user).order_by("-created_at").prefetch_related("items")
    return render(request, "storefront/my_orders.html", {"orders": orders, "need_login": False})


@require_GET
def reservations_list(request: HttpRequest) -> HttpResponse:
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return render(request, "storefront/reservations_list.html", {"reservations": [], "need_login": True})
    try:
        from reservations.models import Reservation
        reservations = Reservation.objects.filter(created_by=request.user).order_by("-start_time")
    except Exception:
        reservations = []
    return render(request, "storefront/reservations_list.html", {"reservations": reservations, "need_login": False})
