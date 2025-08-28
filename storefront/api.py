from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Dict, List

from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.http import JsonResponse, HttpRequest

def _parse_items(body: Dict[str, Any]) -> List[Dict[str, int]]:
    items = body.get("items") or body.get("cart") or []
    out: List[Dict[str, int]] = []
    for it in items:
        try:
            pid = int(it.get("id") or it.get("menu_item_id"))
            qty = int(it.get("quantity", 1))
        except Exception:
            continue
        if pid > 0 and qty > 0:
            out.append({"id": pid, "quantity": qty})
    return out

@require_POST
@csrf_protect
def api_cart_sync(request: HttpRequest):
    """
    Persist the current guest cart from the browser into the Django session.
    Expected JSON:
        {"items": [{"id": <menu_item_id>, "quantity": <int>}, ...]}
    """
    try:
        body = json.loads(request.body.decode() or "{}")
    except Exception:
        body = {}
    items = _parse_items(body)
    request.session["cart"] = items
    request.session.modified = True
    return JsonResponse({"ok": True, "saved": len(items)})

@require_POST
@csrf_protect
def api_cart_set_tip(request: HttpRequest):
    """
    Save a positive tip amount to the session so we can apply it at checkout.
    Expected JSON: {"tip_amount": "10.00"}
    """
    try:
        body = json.loads(request.body.decode() or "{}")
    except Exception:
        body = {}
    raw = body.get("tip_amount", 0)
    try:
        tip = max(Decimal(str(raw)), Decimal("0.00"))
    except Exception:
        tip = Decimal("0.00")
    # Store as a primitive for JSON serialization back to the client
    request.session["cart_tip_amount"] = float(tip)
    request.session.modified = True
    return JsonResponse({"ok": True, "tip_amount": float(tip)})
