/* storefront/static/storefront/js/app.js - Fixed Version */

/* ============================================================================
 * Utilities
 * ========================================================================== */

function money(n) {
  // Format as 2dp numeric string (not localized) so Number() works everywhere.
  const num = Number(n || 0);
  return num.toFixed(2);
}

function getCookie(name) {
  // CSRF helper (Django default)
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
  return "";
}

/* ============================================================================
 * API wrapper (Session-based, no JWT confusion)
 * ============================================================================ */

async function _fetch(url, opts) {
  const res = await fetch(url, opts);
  let data = {};
  try {
    data = await res.json();
  } catch (_) {}
  return { res, data };
}

async function api(url, opts = {}) {
  const headers = Object.assign(
    {
      "Content-Type": "application/json",
      "X-Requested-With": "XMLHttpRequest",
    },
    opts.headers || {}
  );

  // CSRF for session-auth endpoints
  const csrftoken = getCookie("csrftoken");
  if (csrftoken && !("X-CSRFToken" in headers) && (opts.method || "GET") !== "GET") {
    headers["X-CSRFToken"] = csrftoken;
  }

  return await _fetch(url, { ...opts, headers, credentials: "include" });
}

/* ============================================================================
 * Client Cart (localStorage with session merge support)
 * ============================================================================ */

const CART_KEY = "cart_v1";

const cart = {
  _state() {
    try {
      const raw = localStorage.getItem(CART_KEY);
      if (!raw) return { items: {}, tip: 0, discount: 0, delivery: "DINE_IN" };
      const obj = JSON.parse(raw);
      if (!obj.items) obj.items = {};
      if (typeof obj.tip !== "number") obj.tip = 0;
      if (typeof obj.discount !== "number") obj.discount = 0;
      if (!obj.delivery) obj.delivery = "DINE_IN";
      return obj;
    } catch (e) {
      return { items: {}, tip: 0, discount: 0, delivery: "DINE_IN" };
    }
  },
  _save(state) {
    localStorage.setItem(CART_KEY, JSON.stringify(state));
    window.dispatchEvent(new CustomEvent("cart:change", { detail: { state } }));
  },
  clear() {
    this._save({ items: {}, tip: 0, discount: 0, delivery: "DINE_IN" });
  },
  setDelivery(kind) {
    const s = this._state();
    s.delivery = String(kind || "DINE_IN").toUpperCase();
    this._save(s);
  },
  setTip(amount) {
    const s = this._state();
    s.tip = Math.max(0, Number(amount || 0));
    this._save(s);
  },
  setDiscount(amount) {
    const s = this._state();
    s.discount = Math.max(0, Number(amount || 0));
    this._save(s);
  },
  add(id, meta = {}, qty = 1) {
    const s = this._state();
    const key = String(id);
    const q = Math.max(1, Number(qty || 1));
    if (!s.items[key]) s.items[key] = { qty: 0, name: meta.name || "", price: Number(meta.price || 0), image: meta.image || null };
    s.items[key].qty = Number(s.items[key].qty || 0) + q;
    if (meta.price != null) s.items[key].price = Number(meta.price);
    if (meta.name) s.items[key].name = meta.name;
    if (meta.image) s.items[key].image = meta.image;
    this._save(s);
  },
  remove(id, qty = 1) {
    const s = this._state();
    const key = String(id);
    const delta = Math.max(1, Number(qty || 1));
    if (!s.items[key]) return;
    const currentQty = Number(s.items[key].qty || 0);
    const next = currentQty - delta;
    
    // Only allow removal if it would result in quantity >= 1
    // For complete removal, use a special high quantity (999) or call removeCompletely
    if (next >= 1) {
      s.items[key].qty = next;
      this._save(s);
    } else if (delta >= 999) {
      // Allow complete removal only with high delta (999+)
      delete s.items[key];
      this._save(s);
    }
    // Otherwise, do nothing - prevent quantity from going below 1
  },
  setQty(id, qty) {
    const s = this._state();
    const key = String(id);
    const n = Math.max(0, Number(qty || 0));
    if (n === 0) {
      delete s.items[key];
    } else {
      if (!s.items[key]) s.items[key] = { qty: 0, name: "", price: 0, image: null };
      s.items[key].qty = n;
    }
    this._save(s);
  },
  itemsArray() {
    const s = this._state();
    return Object.entries(s.items).map(([id, it]) => ({
      id: Number(id),
      qty: Number(it.qty || 0),
      name: it.name || "",
      price: Number(it.price || 0),
      image: it.image || null,
      line_total: Number(it.qty || 0) * Number(it.price || 0),
    }));
  },
  subtotal() {
    return this.itemsArray().reduce((sum, it) => sum + (it.qty * it.price), 0);
  },
  total() {
    const s = this._state();
    const sub = this.subtotal();
    const total = Math.max(0, sub + Number(s.tip || 0) - Number(s.discount || 0));
    return total;
  },
  count() {
    return this.itemsArray().reduce((sum, it) => sum + it.qty, 0);
  },
  snapshot() {
    const s = this._state();
    return {
      items: this.itemsArray(),
      tip: Number(s.tip || 0),
      discount: Number(s.discount || 0),
      delivery: s.delivery || "DINE_IN",
      subtotal: this.subtotal(),
      total: this.total(),
      count: this.count(),
    };
  },
};

/* ============================================================================
 * UI Bindings
 * ============================================================================ */

function _closest(target, selector) {
  if (!target) return null;
  if (target.matches && target.matches(selector)) return target;
  return target.closest ? target.closest(selector) : null;
}

function renderCartBadges() {
  const snap = cart.snapshot();
  
  // Update cart count in navigation
  const cartCount = document.getElementById("cart-count");
  if (cartCount) {
    cartCount.textContent = String(snap.count);
  }
  
  // Update any data-cart-count elements
  document.querySelectorAll("[data-cart-count]").forEach((el) => {
    el.textContent = String(snap.count);
  });
  document.querySelectorAll("[data-cart-subtotal]").forEach((el) => {
    el.textContent = money(snap.subtotal);
  });
  document.querySelectorAll("[data-cart-total]").forEach((el) => {
    el.textContent = money(snap.total);
  });
}

function bindCartButtons() {
  // Single delegated listener for performance
  document.addEventListener("click", (ev) => {
    // Handle add to cart buttons
    const addBtn = _closest(ev.target, "[data-add]");
    if (addBtn) {
      ev.preventDefault();
      const id = addBtn.getAttribute("data-add");
      const name = addBtn.getAttribute("data-name") || "";
      const price = Number(addBtn.getAttribute("data-price") || 0);
      const image = addBtn.getAttribute("data-image") || null;
      
      cart.add(id, { name, price, image }, 1);
      
      // Show feedback
      const originalText = addBtn.textContent;
      addBtn.textContent = "Added!";
      addBtn.style.backgroundColor = "#10b981";
      setTimeout(() => {
        addBtn.textContent = originalText;
        addBtn.style.backgroundColor = "";
      }, 1000);
      
      return;
    }

    // Handle remove from cart buttons
    const subBtn = _closest(ev.target, "[data-sub]");
    if (subBtn) {
      ev.preventDefault();
      const id = subBtn.getAttribute("data-sub");
      cart.remove(id, 1);
      return;
    }

    // Handle clear cart button
    const clearBtn = _closest(ev.target, "[data-cart-clear]");
    if (clearBtn) {
      ev.preventDefault();
      if (confirm("Clear your cart?")) {
        cart.clear();
      }
      return;
    }

    // Handle delivery type buttons
    const dineBtn = _closest(ev.target, "[data-delivery]");
    if (dineBtn) {
      ev.preventDefault();
      cart.setDelivery(dineBtn.getAttribute("data-delivery") || "DINE_IN");
      return;
    }
  });

  // Handle quantity inputs and other form controls
  document.addEventListener("change", (ev) => {
    const qtyInput = _closest(ev.target, "[data-qty]");
    if (qtyInput) {
      const id = qtyInput.getAttribute("data-qty");
      const qty = parseInt(qtyInput.value, 10);
      cart.setQty(id, isNaN(qty) ? 0 : qty);
      return;
    }

    if (ev.target && ev.target.matches && ev.target.matches("[data-tip]")) {
      const val = Number(ev.target.value || 0);
      cart.setTip(isNaN(val) ? 0 : val);
      return;
    }
    if (ev.target && ev.target.matches && ev.target.matches("[data-discount]")) {
      const val = Number(ev.target.value || 0);
      cart.setDiscount(isNaN(val) ? 0 : val);
      return;
    }
  });
}

function renderCartTable() {
  const tbody = document.querySelector("[data-cart-body]");
  if (!tbody) return;
  
  const snap = cart.snapshot();
  tbody.innerHTML = "";
  
  if (snap.items.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Your cart is empty.</td></tr>';
    renderCartBadges();
    return;
  }
  
  for (const it of snap.items) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="align-middle">
        ${it.image ? `<img src="${it.image}" alt="" style="height:40px;width:40px;object-fit:cover;border-radius:6px;">` : ""}
      </td>
      <td class="align-middle">${it.name}</td>
      <td class="align-middle">NPR ${money(it.price)}</td>
      <td class="align-middle">
        <div class="btn-group" role="group">
          <button type="button" class="btn btn-outline-secondary" data-sub="${it.id}">−</button>
          <input type="number" class="form-control text-center" style="width:80px" min="0" step="1" value="${it.qty}" data-qty="${it.id}">
          <button type="button" class="btn btn-outline-secondary" data-add="${it.id}" data-name="${it.name}" data-price="${it.price}" ${it.image ? `data-image="${it.image}"` : ""}>＋</button>
        </div>
      </td>
      <td class="align-middle fw-semibold">NPR ${money(it.line_total)}</td>
    `;
    tbody.appendChild(tr);
  }
  renderCartBadges();
}

function bindCartRendering() {
  // Re-render badges + table whenever cart changes
  window.addEventListener("cart:change", () => {
    renderCartBadges();
    renderCartTable();
  });
  // First paint
  renderCartBadges();
  renderCartTable();
}

/* ============================================================================
 * Navigation Auth Links Handler
 * ============================================================================ */

function updateAuthNavigation(isAuthenticated) {
  const navLogin = document.getElementById('nav-login');
  const navLogout = document.getElementById('nav-logout');
  const navOrders = document.getElementById('nav-orders');
  
  if (navLogin) navLogin.style.display = isAuthenticated ? 'none' : '';
  if (navLogout) navLogout.style.display = isAuthenticated ? '' : 'none';
  if (navOrders) navOrders.style.display = isAuthenticated ? '' : 'none';
}

async function checkAuthStatus() {
  try {
    const { res, data } = await api('/session/ping/');
    if (res.ok && data.is_auth) {
      updateAuthNavigation(true);
      return true;
    } else {
      updateAuthNavigation(false);
      return false;
    }
  } catch (error) {
    updateAuthNavigation(false);
    return false;
  }
}

/* ============================================================================
 * DOM Ready Handler
 * ============================================================================ */

document.addEventListener('DOMContentLoaded', function() {
  const navLogin = document.getElementById('nav-login');
  const navLogout = document.getElementById('nav-logout');
  
  // Handle login button click
  if (navLogin) {
    navLogin.addEventListener('click', function(e) {
      e.preventDefault();
      if (window.__openAuthModal) {
        window.__openAuthModal("choice");
      }
    });
  }

  // Handle logout button click  
  if (navLogout) {
    navLogout.addEventListener('click', async function(e) {
      e.preventDefault();
      try {
        await api('/accounts/logout/', { method: 'POST' });
        cart.clear();
        updateAuthNavigation(false);
        // Redirect to home if on protected page
        if (window.location.pathname.includes('my-orders')) {
          window.location.href = '/';
        }
      } catch (error) {
        console.error('Logout failed:', error);
      }
    });
  }

  // Check auth status on page load
  checkAuthStatus();

  // Listen for auth events
  window.addEventListener('auth:login', () => {
    updateAuthNavigation(true);
    checkAuthStatus(); // Refresh to make sure
  });
  
  window.addEventListener('auth:logout', () => {
    updateAuthNavigation(false);
  });

  // Initialize cart functionality
  bindCartRendering();
  bindCartButtons();
});

/* ============================================================================
 * Cart API functions for cart-render.js compatibility
 * ============================================================================ */
async function cartApiAdd(id, qty = 1) {
  console.log(`cartApiAdd called: id=${id}, qty=${qty}`);
  
  if (qty > 0) {
    cart.add(id, {}, qty);
  } else if (qty < 0) {
    cart.remove(id, Math.abs(qty));
  }
  
  // Re-render cart badges after update
  renderCartBadges();
  
  // Sync with server
  await syncCartWithServer();
  
  console.log('Cart updated, new count:', cart.count());
}

async function cartApiRemove(id, qty = 1) {
  console.log(`cartApiRemove called: id=${id}, qty=${qty}`);
  cart.remove(id, qty);
  renderCartBadges();
  
  // Sync with server
  await syncCartWithServer();
  
  console.log('Item removed, new count:', cart.count());
}

/* ============================================================================
 * Cart synchronization with server
 * ============================================================================ */
async function syncCartWithServer() {
  try {
    const cartSnapshot = cart.snapshot();
    const cartItems = cartSnapshot.items || [];
    
    if (cartItems.length === 0) {
      // If cart is empty, still sync to clear server cart
      await api('/api/cart/sync/', {
        method: 'POST',
        body: JSON.stringify({ items: [] })
      });
      return;
    }
    
    // Convert cart format to server expected format
    const serverItems = cartItems.map(item => ({
      id: parseInt(item.id),
      quantity: parseInt(item.qty)
    }));
    
    await api('/api/cart/sync/', {
      method: 'POST',
      body: JSON.stringify({ items: serverItems })
    });
    
    console.log('Cart synced with server:', serverItems.length, 'items');
  } catch (error) {
    console.error('Failed to sync cart with server:', error);
  }
}

/* ============================================================================
 * Cart API Get function for cart-render.js compatibility
 * ============================================================================ */
async function cartApiGet() {
  // First try to get data from server
  try {
    const r = await fetch("/api/orders/cart-simple/", { 
      credentials: "include"
    });
    
    let serverData = { items: [] };
    if (r.ok) {
      serverData = await r.json();
    }
    
    // If server has no items, check localStorage cart_v1
    if (!serverData.items || serverData.items.length === 0) {
      try {
        const cartSnapshot = cart.snapshot();
        const items = cartSnapshot.items || [];
        
        // Convert cart format to expected format
        const formattedItems = items.map(item => ({
          id: parseInt(item.id),
          name: item.name || `Item ${item.id}`,
          quantity: item.qty || 0,
          unit_price: item.price || 0,
          line_total: (item.qty || 0) * (item.price || 0),
          total_unit_price: item.price || 0,
          modifier_price: 0,
          modifier_names: []
        }));
        
        return {
          items: formattedItems,
          subtotal: formattedItems.reduce((sum, item) => sum + (item.line_total || 0), 0).toFixed(2),
          meta: cartSnapshot
        };
      } catch (e) {
        console.error('Error reading cart from localStorage:', e);
      }
    }
    
    return serverData;
  } catch (error) {
    console.error('Error in cartApiGet:', error);
    return { items: [] };
  }
}

/* ============================================================================
 * Expose globals for compatibility
 * ============================================================================ */
window.cart = cart;
window.api = api;
window.money = money;
window.renderCartBadges = renderCartBadges;
window.cartApiAdd = cartApiAdd;
window.cartApiRemove = cartApiRemove;
window.cartApiGet = cartApiGet;
