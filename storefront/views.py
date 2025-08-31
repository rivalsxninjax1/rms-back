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


@method_decorator(login_required, name="dispatch")
def checkout(request: HttpRequest) -> HttpResponse:
    """
    Checkout shell; pressing 'Pay' triggers JS → /payments/checkout/ POST.
    Login is required for Stripe payments.
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
    return render(request, "storefront/500.html", status=500)


def test_cart_debug(request: HttpRequest) -> HttpResponse:
    """Serve test HTML files for cart debugging"""
    import os
    from django.conf import settings
    
    # Get the test file name from URL parameter
    test_file = request.GET.get('file', 'add_test_items')
    
    # Read the HTML file from the project root
    file_path = os.path.join(settings.BASE_DIR, f"{test_file}.html")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return HttpResponse(content, content_type='text/html')
    except FileNotFoundError:
        return HttpResponse(f"Test file {test_file}.html not found", status=404)


def debug_cart(request: HttpRequest) -> HttpResponse:
    """Debug cart rendering with proper Django template"""
    return render(request, 'storefront/debug_cart.html')


def debug_session_cart(request: HttpRequest) -> JsonResponse:
    """Debug endpoint to check session cart data"""
    session_cart = request.session.get('cart', [])
    return JsonResponse({
        'session_cart': session_cart,
        'session_keys': list(request.session.keys()),
        'cart_length': len(session_cart)
    })


def test_cart_display(request: HttpRequest) -> HttpResponse:
    return render(request, 'storefront/test_cart_display.html')


def debug_cart_controls(request: HttpRequest) -> HttpResponse:
    """Debug page for testing cart quantity controls"""
    debug_html = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Debug Cart Controls</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .cart-item { border: 1px solid #ddd; padding: 15px; margin: 10px 0; }
        .qty-controls { display: flex; align-items: center; gap: 10px; }
        .qty-controls button { padding: 5px 10px; cursor: pointer; }
        .debug-info { background: #f0f0f0; padding: 10px; margin: 10px 0; }
    </style>
</head>
<body>
    <h1>Cart Controls Debug</h1>
    
    <div class="debug-info">
        <h3>Debug Information</h3>
        <div id="debug-output"></div>
    </div>
    
    <div id="cart-items">
        <!-- Cart items will be rendered here -->
    </div>
    
    <script>
        // Debug logging function
        function debugLog(message) {
            console.log(message);
            const debugOutput = document.getElementById('debug-output');
            debugOutput.innerHTML += '<div>' + new Date().toLocaleTimeString() + ': ' + message + '</div>';
        }
        
        // Mock cart API functions for testing
        window.cartApiGet = async function() {
            debugLog('cartApiGet called');
            try {
                const response = await fetch('/api/orders/cart-simple/', {
                    method: 'GET',
                    credentials: 'same-origin'
                });
                const data = await response.json();
                debugLog('Cart data received: ' + JSON.stringify(data));
                return data;
            } catch (error) {
                debugLog('Error in cartApiGet: ' + error.message);
                return { items: [] };
            }
        };
        
        window.cartApiAdd = async function(id, qty = 1) {
            debugLog(`cartApiAdd called: id=${id}, qty=${qty}`);
            try {
                const response = await fetch('/api/cart/sync/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify({
                        menu_item_id: id,
                        quantity: qty
                    })
                });
                const result = await response.json();
                debugLog('cartApiAdd result: ' + JSON.stringify(result));
                return result;
            } catch (error) {
                debugLog('Error in cartApiAdd: ' + error.message);
            }
        };
        
        window.cartApiRemove = async function(id, qty = 1) {
            debugLog(`cartApiRemove called: id=${id}, qty=${qty}`);
            try {
                const response = await fetch('/api/cart/sync/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify({
                        menu_item_id: id,
                        quantity: -qty
                    })
                });
                const result = await response.json();
                debugLog('cartApiRemove result: ' + JSON.stringify(result));
                return result;
            } catch (error) {
                debugLog('Error in cartApiRemove: ' + error.message);
            }
        };
        
        // Get CSRF token
        function getCookie(name) {
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }
        
        // Render cart items
        async function renderCart() {
            debugLog('Rendering cart...');
            const cartData = await cartApiGet();
            const container = document.getElementById('cart-items');
            
            if (!cartData.items || cartData.items.length === 0) {
                container.innerHTML = '<p>Cart is empty</p>';
                return;
            }
            
            let html = '';
            cartData.items.forEach(item => {
                html += `
                    <div class="cart-item" data-id="${item.id}">
                        <h4>${item.name || 'Item ' + item.id}</h4>
                        <p>Price: NPR ${item.unit_price || item.price || '0.00'}</p>
                        <div class="qty-controls">
                            <button class="qty-dec" data-id="${item.id}">-</button>
                            <span class="qty" data-id="${item.id}">${item.quantity || 0}</span>
                            <button class="qty-inc" data-id="${item.id}">+</button>
                            <button class="remove-item" data-id="${item.id}">Remove</button>
                        </div>
                    </div>
                `;
            });
            
            container.innerHTML = html;
            debugLog('Cart rendered with ' + cartData.items.length + ' items');
        }
        
        // Event delegation for cart controls
        document.addEventListener('click', async (e) => {
            const cartContainer = document.getElementById('cart-items');
            if (!cartContainer || !cartContainer.contains(e.target)) return;
            
            const dec = e.target.closest('.qty-dec');
            const inc = e.target.closest('.qty-inc');
            const rem = e.target.closest('.remove-item');
            
            if (dec) {
                const id = Number(dec.getAttribute('data-id'));
                debugLog(`Decrease button clicked for item ${id}`);
                await cartApiAdd(id, -1);
                await renderCart();
                return;
            }
            
            if (inc) {
                const id = Number(inc.getAttribute('data-id'));
                debugLog(`Increase button clicked for item ${id}`);
                await cartApiAdd(id, 1);
                await renderCart();
                return;
            }
            
            if (rem) {
                const id = Number(rem.getAttribute('data-id'));
                debugLog(`Remove button clicked for item ${id}`);
                await cartApiRemove(id, 999); // Remove all
                await renderCart();
                return;
            }
        });
        
        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            debugLog('Page loaded, initializing cart...');
            renderCart();
        });
    </script>
</body>
</html>
    '''
    return HttpResponse(debug_html, content_type='text/html')


def set_test_cart(request: HttpRequest) -> HttpResponse:
    """Set test cart data in session and redirect to debug page"""
    request.session['cart'] = [
        {'id': 1, 'quantity': 2},
        {'id': 2, 'quantity': 1}
    ]
    request.session.save()
    return redirect('/debug-cart-controls/')


def test_cart_buttons(request: HttpRequest) -> HttpResponse:
    """Test page for cart add/subtract button functionality"""
    html_content = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cart Buttons Test</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        .test-section {
            border: 1px solid #ddd;
            margin: 20px 0;
            padding: 20px;
            border-radius: 8px;
        }
        .cart-item {
            display: flex;
            align-items: center;
            gap: 15px;
            padding: 15px;
            border: 1px solid #eee;
            border-radius: 8px;
            margin: 10px 0;
        }
        .qty-controls {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .qty-btn {
            width: 32px;
            height: 32px;
            border: 1px solid #ddd;
            background: #f8f9fa;
            border-radius: 4px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 16px;
        }
        .qty-btn:hover {
            background: #e9ecef;
        }
        .qty-display {
            min-width: 40px;
            text-align: center;
            font-weight: bold;
        }
        .log {
            background: #f8f9fa;
            border: 1px solid #ddd;
            padding: 10px;
            margin: 10px 0;
            border-radius: 4px;
            font-family: monospace;
            font-size: 12px;
            max-height: 200px;
            overflow-y: auto;
        }
        .error { color: #dc3545; }
        .success { color: #28a745; }
        .info { color: #007bff; }
        .btn {
            background: #007bff;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            margin: 5px;
        }
        .btn:hover {
            background: #0056b3;
        }
    </style>
</head>
<body>
    <h1>Cart Add/Subtract Buttons Test</h1>
    
    <div class="test-section">
        <h2>Test Controls</h2>
        <button class="btn" onclick="addTestItem()">Add Test Item to Cart</button>
        <button class="btn" onclick="clearCart()">Clear Cart</button>
        <button class="btn" onclick="refreshCart()">Refresh Cart Display</button>
        <button class="btn" onclick="clearLog()">Clear Log</button>
    </div>

    <div class="test-section">
        <h2>Cart Items</h2>
        <div id="cart-items">No items in cart</div>
    </div>

    <div class="test-section">
        <h2>Test Log</h2>
        <div id="log" class="log"></div>
    </div>

    <script>
        // CSRF token helper
        function getCookie(name) {
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }

        // Logging function
        function log(message, type = 'info') {
            const logDiv = document.getElementById('log');
            const timestamp = new Date().toLocaleTimeString();
            const logEntry = document.createElement('div');
            logEntry.className = type;
            logEntry.textContent = `[${timestamp}] ${message}`;
            logDiv.appendChild(logEntry);
            logDiv.scrollTop = logDiv.scrollHeight;
            console.log(`[${type.toUpperCase()}] ${message}`);
        }

        function clearLog() {
            document.getElementById('log').innerHTML = '';
        }

        // API helper
        async function apiCall(url, options = {}) {
            try {
                const response = await fetch(url, {
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                        ...options.headers
                    },
                    ...options
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                return await response.json();
            } catch (error) {
                log(`API Error: ${error.message}`, 'error');
                throw error;
            }
        }

        // Cart operations
        async function addTestItem() {
            try {
                log('Adding test item (Pizza, ID: 1) with quantity 2...');
                const result = await apiCall('/api/orders/cart/items/', {
                    method: 'POST',
                    body: JSON.stringify({
                        menu_item_id: 1,
                        quantity: 2
                    })
                });
                log('Test item added successfully', 'success');
                await refreshCart();
            } catch (error) {
                log(`Failed to add test item: ${error.message}`, 'error');
            }
        }

        async function clearCart() {
            try {
                log('Clearing cart...');
                await apiCall('/api/cart/sync/', {
                    method: 'POST',
                    body: JSON.stringify({ items: [] })
                });
                log('Cart cleared successfully', 'success');
                await refreshCart();
            } catch (error) {
                log(`Failed to clear cart: ${error.message}`, 'error');
            }
        }

        async function incrementItem(itemId) {
            try {
                log(`Incrementing item ${itemId}...`);
                await apiCall('/api/orders/cart/items/', {
                    method: 'POST',
                    body: JSON.stringify({
                        menu_item_id: itemId,
                        quantity: 1
                    })
                });
                log(`Item ${itemId} incremented successfully`, 'success');
                await refreshCart();
            } catch (error) {
                log(`Failed to increment item ${itemId}: ${error.message}`, 'error');
            }
        }

        async function decrementItem(itemId) {
            try {
                // Get current quantity first
                const cartData = await apiCall('/api/orders/cart-simple/');
                const items = cartData.items || [];
                const currentItem = items.find(item => item.id === itemId);
                const currentQty = currentItem ? currentItem.quantity : 0;
                
                if (currentQty <= 1) {
                    log(`Cannot decrement item ${itemId} - quantity is already at minimum (${currentQty})`, 'error');
                    return;
                }
                
                log(`Decrementing item ${itemId} (current qty: ${currentQty})...`);
                await apiCall('/api/orders/cart/items/', {
                    method: 'POST',
                    body: JSON.stringify({
                        menu_item_id: itemId,
                        quantity: -1
                    })
                });
                log(`Item ${itemId} decremented successfully`, 'success');
                await refreshCart();
            } catch (error) {
                log(`Failed to decrement item ${itemId}: ${error.message}`, 'error');
            }
        }

        async function refreshCart() {
            try {
                log('Refreshing cart display...');
                const cartData = await apiCall('/api/orders/cart-simple/');
                displayCart(cartData);
                log('Cart display refreshed', 'success');
            } catch (error) {
                log(`Failed to refresh cart: ${error.message}`, 'error');
            }
        }

        function displayCart(cartData) {
            const cartContainer = document.getElementById('cart-items');
            const items = cartData.items || [];
            
            if (items.length === 0) {
                cartContainer.innerHTML = '<p>No items in cart</p>';
                return;
            }

            cartContainer.innerHTML = items.map(item => `
                <div class="cart-item">
                    <div>
                        <strong>${item.name || `Item ${item.id}`}</strong><br>
                        <small>NPR ${(item.unit_price || 0).toFixed(2)} each</small>
                    </div>
                    <div class="qty-controls">
                        <button class="qty-btn" onclick="decrementItem(${item.id})" title="Decrease quantity" ${item.quantity <= 1 ? 'disabled style="opacity: 0.5; cursor: not-allowed;"' : ''}>−</button>
                        <span class="qty-display">${item.quantity}</span>
                        <button class="qty-btn" onclick="incrementItem(${item.id})" title="Increase quantity">+</button>
                    </div>
                    <div>
                        <strong>NPR ${(item.line_total || 0).toFixed(2)}</strong>
                    </div>
                </div>
            `).join('');
        }

        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            log('Cart buttons test page loaded', 'success');
            refreshCart();
        });
    </script>
</body>
</html>
    '''
    return HttpResponse(html_content, content_type='text/html')
