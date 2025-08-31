# FILE: rms-back/storefront/api.py
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Dict, List

from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_protect
from django.http import JsonResponse, HttpRequest

# Import Table models from all three apps
try:
    from reservations.models import Table as ReservationTable
except ImportError:
    ReservationTable = None

try:
    from core.models import Table as CoreTable
except ImportError:
    CoreTable = None

try:
    from inventory.models import Table as InventoryTable
except ImportError:
    InventoryTable = None


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
    request.session["cart_tip_amount"] = float(tip)
    request.session.modified = True
    return JsonResponse({"ok": True, "tip_amount": float(tip)})


@require_GET
def api_tables(request: HttpRequest):
    """
    API endpoint to get all active tables from all three sources:
    - Reservations (for booking management)
    - Core (for centralized table management)
    - Inventory (for asset/equipment tracking)
    """
    table_data = []
    
    # Get tables from Reservations app
    if ReservationTable:
        reservation_tables = ReservationTable.objects.filter(is_active=True).select_related('location')
        for table in reservation_tables:
            table_data.append({
                "id": f"reservation_{table.id}",
                "table_number": table.table_number,
                "capacity": table.capacity,
                "location_id": table.location_id,
                "location_name": getattr(table.location, "name", ""),
                "source": "reservations",
                "source_id": table.id,
            })
    
    # Get tables from Core app
    if CoreTable:
        core_tables = CoreTable.objects.filter(is_active=True).select_related('location')
        for table in core_tables:
            table_data.append({
                "id": f"core_{table.id}",
                "table_number": table.table_number,
                "capacity": table.capacity,
                "location_id": table.location_id,
                "location_name": getattr(table.location, "name", ""),
                "source": "core",
                "source_id": table.id,
                "table_type": getattr(table, 'table_type', 'dining'),
            })
    
    # Get tables from Inventory app
    if InventoryTable:
        inventory_tables = InventoryTable.objects.filter(is_active=True).select_related('location')
        for table in inventory_tables:
            table_data.append({
                "id": f"inventory_{table.id}",
                "table_number": table.table_number,
                "capacity": table.capacity,
                "location_id": table.location_id,
                "location_name": getattr(table.location, "name", ""),
                "source": "inventory",
                "source_id": table.id,
                "condition": getattr(table, 'condition', 'good'),
            })
    
    # Sort by location and table number
    table_data.sort(key=lambda x: (x['location_id'], x['table_number']))
    
    # Group tables by location and table_number, showing source diversity
    table_groups = {}
    for table in table_data:
        key = (table['location_id'], table['table_number'])
        if key not in table_groups:
            table_groups[key] = []
        table_groups[key].append(table)
    
    # Create unified table entries showing all source information
    unified_tables = []
    for (location_id, table_number), tables in table_groups.items():
        # Use the first table as base, but aggregate source information
        base_table = tables[0].copy()
        
        # Add source information from all apps
        sources = []
        source_details = {}
        
        for table in tables:
            sources.append(table['source'])
            if table['source'] == 'core' and 'table_type' in table:
                source_details['table_type'] = table['table_type']
            elif table['source'] == 'inventory' and 'condition' in table:
                source_details['condition'] = table['condition']
        
        # Update the base table with aggregated information
        base_table['sources'] = sources
        base_table['source_count'] = len(sources)
        base_table.update(source_details)
        
        # Use the primary source (reservations if available, otherwise first)
        if 'reservations' in sources:
            primary_table = next(t for t in tables if t['source'] == 'reservations')
            base_table['id'] = primary_table['id']
            base_table['source'] = primary_table['source']
            base_table['source_id'] = primary_table['source_id']
        
        unified_tables.append(base_table)
    
    return JsonResponse({"tables": unified_tables, "total_sources": sum([1 for model in [ReservationTable, CoreTable, InventoryTable] if model is not None])})
