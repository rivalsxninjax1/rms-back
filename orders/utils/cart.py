# orders/utils/cart.py
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Tuple

from django.db import transaction
from django.http import HttpRequest

from orders.models import Cart, CartItem
from menu.models import Modifier


def _normalize_modifiers(mods: Iterable[Dict[str, Any]] | None) -> Tuple[Tuple[int, int], ...]:
    """
    Canonical tuple for a set of modifiers, order-independent:
    Each entry becomes (modifier_id, quantity>=1), sorted by id.
    """
    if not mods:
        return tuple()
    norm: List[Tuple[int, int]] = []
    for m in mods:
        if not isinstance(m, dict):
            continue
        mid = m.get("modifier_id") or m.get("id")
        if mid is None:
            continue
        qty = int(m.get("quantity", 1))
        norm.append((int(mid), max(1, qty)))
    norm.sort(key=lambda x: x[0])
    return tuple(norm)


def _item_signature(menu_item_id: int, modifiers: Iterable[Dict[str, Any]] | None) -> Tuple[int, Tuple[Tuple[int, int], ...]]:
    return (int(menu_item_id), _normalize_modifiers(modifiers))


@dataclass(frozen=True)
class CartResult:
    cart: Cart
    created: bool


def get_or_create_cart(request: HttpRequest) -> CartResult:
    """
    Get the active cart for this request:
      - Authenticated → user's active cart
      - Guest         → session's active cart (ensures a session key exists and is persisted)
    """
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=user, status=Cart.STATUS_ACTIVE)
        # touch updated_at for activity tracking
        cart.save(update_fields=["updated_at"])
        return CartResult(cart, created)

    # Guest flow: ensure a sticky session key (and force Set-Cookie by marking modified)
    if not request.session.session_key:
        request.session.create()
    request.session.modified = True  # <- important so browser gets Set-Cookie

    try:
        # Try to get the most recent active cart for this session
        cart = Cart.objects.filter(
            session_key=request.session.session_key,
            status=Cart.STATUS_ACTIVE
        ).order_by('-created_at').first()
        
        if cart:
            created = False
        else:
            cart = Cart.objects.create(
                session_key=request.session.session_key,
                status=Cart.STATUS_ACTIVE
            )
            created = True
    except Exception:
        # Fallback: create a new cart
        cart = Cart.objects.create(
            session_key=request.session.session_key,
            status=Cart.STATUS_ACTIVE
        )
        created = True
    
    cart.save(update_fields=["updated_at"])
    return CartResult(cart, created)


@transaction.atomic
def merge_carts(source: Cart, destination: Cart, *, strategy: str = "increment") -> dict:
    """
    Merge *source* cart into *destination* cart atomically.

    - strategy="increment": same line → increase quantity
    - strategy="replace"  : same line → take source quantity
    """
    if source.pk == destination.pk:
        return {"moved": 0, "merged": 0, "created": 0}

    # Index destination by signature (menu_item + normalized modifiers)
    dest_index: dict[Tuple[int, Tuple[Tuple[int, int], ...]], CartItem] = {}
    for it in destination.items.select_related("menu_item"):
        sig = _item_signature(it.menu_item_id, getattr(it, "selected_modifiers", []))
        dest_index[sig] = it

    moved = merged = created = 0

    for src in source.items.select_related("menu_item"):
        sig = _item_signature(src.menu_item_id, getattr(src, "selected_modifiers", []))
        if sig in dest_index:
            dst = dest_index[sig]
            if strategy == "replace":
                dst.quantity = src.quantity
            else:
                dst.quantity = dst.quantity + src.quantity
            dst.save(update_fields=["quantity", "updated_at"])
            merged += 1
        else:
            CartItem.objects.create(
                cart=destination,
                menu_item_id=src.menu_item_id,
                quantity=src.quantity,
                unit_price=src.unit_price,
                selected_modifiers=getattr(src, "selected_modifiers", []),
                notes=src.notes,
            )
            created += 1
        moved += 1

    # Merge cart-level options (delivery, table, metadata)
    try:
        if not destination.table_id and source.table_id:
            destination.table_id = source.table_id
        # Prefer explicit delivery option if destination is default
        if getattr(destination, "delivery_option", None) in (None, "PICKUP") and getattr(source, "delivery_option", None):
            destination.delivery_option = source.delivery_option
        # Merge metadata dicts (preserve selected tables)
        dmeta = destination.metadata or {}
        smeta = source.metadata or {}
        merged = {**dmeta, **smeta}
        # Merge tables list if both have
        dtables = dmeta.get("tables") or []
        stables = smeta.get("tables") or []
        if dtables or stables:
            seen = set()
            tbls = []
            for tid in list(dtables) + list(stables):
                try:
                    t = int(tid)
                except Exception:
                    continue
                if t not in seen:
                    seen.add(t)
                    tbls.append(t)
            merged["tables"] = tbls
        destination.metadata = merged
    except Exception:
        pass

    # Server-side authoritative totals
    destination.calculate_totals()
    destination.save()

    # Clear/deactivate source (keep row for audit)
    source.items.all().delete()
    source.status = Cart.STATUS_ABANDONED  # mark as no longer current
    source.save(update_fields=["status", "updated_at"])

    return {"moved": moved, "merged": merged, "created": created}
