// rms-back/storefront/static/storefront/app.js
/* storefront/static/storefront/js/app.js - Fixed & Backward-Compatible */

/* ============================================================================
 * Utilities
 * ========================================================================== */

function money(n) {
  // Format as 2dp numeric string (not localized) so Number() works everywhere.
  const num = Number(n || 0);
  return num.toFixed(2);
}

function csrfToken() {
  // Prefer hidden input (works with HttpOnly CSRF cookies), then fallback to cookie
  try {
    const inp = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (inp && inp.value) return inp.value;
  } catch(_) {}
  const value = `; ${document.cookie}`;
  const parts = value.split(`; csrftoken=`);
  if (parts.length === 2) return decodeURIComponent(parts.pop().split(";").shift() || "");
  return "";
}

function jsonFetch(url, opts = {}) {
  const defaults = {
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "XMLHttpRequest",
      "X-CSRFToken": csrfToken(),
    },
    credentials: "include",
  };
  return fetch(url, { ...defaults, ...opts });
}

/* ============================================================================
 * API wrapper used by multiple pages
 * ========================================================================== */

const api = {
  async get(url) {
    const r = await jsonFetch(url);
    if (!r.ok) throw new Error(`${r.status}`);
    return r.json();
  },
  async post(url, body) {
    const r = await jsonFetch(url, { method: "POST", body: JSON.stringify(body || {}) });
    if (!r.ok) throw new Error(`${r.status}`);
    return r.json();
  },
  async del(url) {
    const r = await jsonFetch(url, { method: "DELETE" });
    if (!r.ok) throw new Error(`${r.status}`);
    return r.json();
  },
};

/* ============================================================================
 * Client Cart (localStorage with session merge support)
 * ========================================================================== */

const CART_KEY = "cart_v1";
const LEGACY_CART_KEY = "cart";

/**
 * Build a legacy "cart" array from the new cart state
 */
function _stateToLegacyArray(state) {
  // state.items is an object keyed by id -> {qty, name, price, image}
  const arr = [];
  if (!state || !state.items) return arr;
  for (const [id, it] of Object.entries(state.items)) {
    const qty = Number(it.qty || 0);
    if (qty <= 0) continue;
    arr.push({
      id: Number(id),
      quantity: qty,
      name: it.name || "",
      price: Number(it.price || 0),
      image: it.image || null,
    });
  }
  return arr;
}

/**
 * Convert legacy array to the formatted items shape the cart renderer expects
 */
function _legacyArrayToFormattedItems(arr) {
  const items = Array.isArray(arr) ? arr : [];
  return items
    .map((item) => {
      const id = parseInt(
        item.menu_item || item.id || item.menu || item.menu_id || item.product || item.product_id,
        10
      );
      const qty = parseInt(item.quantity || item.qty || item.q || 1, 10);
      const price = Number(item.price || 0);
      if (!id || id <= 0 || !qty || qty <= 0) return null;
      return {
        id,
        name: item.name || `Item ${id}`,
        quantity: qty,
        unit_price: price,
        line_total: qty * price,
        total_unit_price: price,
        modifier_price: 0,
        modifier_names: [],
      };
    })
    .filter(Boolean);
}

const cart = {
  _state() {
    try {
      const raw = localStorage.getItem(CART_KEY);
      if (!raw) return { items: {}, tip: 0, discount: 0, delivery: "PICKUP" };
      const obj = JSON.parse(raw);
      if (!obj.items) obj.items = {};
      if (typeof obj.tip !== "number") obj.tip = 0;
      if (typeof obj.discount !== "number") obj.discount = 0;
      if (!obj.delivery) obj.delivery = "PICKUP";
      return obj;
    } catch (e) {
      return { items: {}, tip: 0, discount: 0, delivery: "PICKUP" };
    }
  },
  _save(state) {
    // Save new format
    localStorage.setItem(CART_KEY, JSON.stringify(state));
    // Mirror to legacy "cart" array for older scripts (do NOT remove)
    try {
      const legacy = _stateToLegacyArray(state);
      localStorage.setItem(LEGACY_CART_KEY, JSON.stringify(legacy));
    } catch (e) {
      console.warn("Failed to mirror cart to legacy key:", e);
    }
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
    const qtyNum = Number(qty || 1);
    if (qtyNum < 0) {
      this.remove(id, Math.abs(qtyNum));
      return;
    }
    const q = Math.max(1, qtyNum);
    const s = this._state();
    const key = String(id);
    if (!s.items[key]) s.items[key] = { qty: 0, name: "", price: 0, image: null };
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
    if (next < 0) return;
    if (next === 0) {
      delete s.items[key];
    } else {
      s.items[key].qty = next;
    }
    this._save(s);
  },
  setQty(id, qty) {
    const s = this._state();
    const key = String(id);
    const n = Math.max(0, parseInt(qty || 0, 10));
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
    return this.itemsArray().reduce((sum, it) => sum + it.qty * it.price, 0);
  },
  total() {
    const s = this._state();
    const sub = this.subtotal();
    return Math.max(0, sub + Number(s.tip || 0) - Number(s.discount || 0));
  },
  count() {
    return this.itemsArray().reduce((sum, it) => sum + it.qty, 0);
  },
  snapshot() {
    const s = this._state();
    return {
      items: this.itemsArray(),
      subtotal: this.subtotal(),
      tip: s.tip || 0,
      discount: s.discount || 0,
      total: this.total(),
      delivery: s.delivery || "DINE_IN",
      count: this.count(),
    };
  },
};

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

  // Update totals if present
  document.querySelectorAll("[data-cart-subtotal]").forEach((el) => {
    el.textContent = money(snap.subtotal);
  });
  document.querySelectorAll("[data-cart-tip]").forEach((el) => {
    el.textContent = money(snap.tip);
  });
  document.querySelectorAll("[data-cart-discount]").forEach((el) => {
    el.textContent = money(snap.discount);
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
      const image = addBtn.getAttribute("data-image") || "";
      const qtyInput = document.querySelector("[data-qty-input]");
      const qty = qtyInput ? parseInt(qtyInput.value, 10) || 1 : 1;
      cart.add(id, { name, price, image }, qty);
      renderCartBadges();
      return;
    }

    // Handle minus buttons
    const minusBtn = _closest(ev.target, "[data-minus]");
    if (minusBtn) {
      ev.preventDefault();
      const id = minusBtn.getAttribute("data-minus");
      cart.remove(id, 1);
      renderCartBadges();
      return;
    }

    // Handle plus buttons
    const plusBtn = _closest(ev.target, "[data-plus]");
    if (plusBtn) {
      ev.preventDefault();
      const id = plusBtn.getAttribute("data-plus");
      cart.add(id, {}, 1);
      renderCartBadges();
      return;
    }

    // Handle remove buttons
    const remBtn = _closest(ev.target, "[data-remove]");
    if (remBtn) {
      ev.preventDefault();
      const id = remBtn.getAttribute("data-remove");
      cart.setQty(id, 0);
      renderCartBadges();
      return;
    }
  });
}

bindCartButtons();
renderCartBadges();

/* ============================================================================
 * Cart API helpers used by cart-render.js (shims; do NOT remove other funcs)
 * ========================================================================== */

// Client-authoritative cart operations with optimistic updates
let _syncQueue = [];
let _syncInProgress = false;
let _syncSequence = 0;

if (typeof window.cartApiAdd !== "function") {
  window.cartApiAdd = async function cartApiAdd(id, delta) {
    try {
      const n = Number(delta || 0);
      
      // OPTIMISTIC UPDATE: Update local cart immediately (client-authoritative)
      if (n > 0) cart.add(id, {}, n);
      else if (n < 0) cart.remove(id, Math.abs(n));
      
      // Update UI immediately
      renderCartBadges();
      window.dispatchEvent(new CustomEvent("cart:change"));
      
      // Queue server sync (non-blocking, debounced)
      queueServerSync({
        type: 'set',
        id: id,
        quantity: cart._state().items[id] ? cart._state().items[id].qty : 0,
        sequence: ++_syncSequence
      });
      
      return { ok: true };
    } catch (e) {
      console.warn("cartApiAdd failed:", e);
      return { ok: false };
    }
  };
}

if (typeof window.cartApiRemove !== "function") {
  window.cartApiRemove = async function cartApiRemove(id, qty) {
    try {
      const n = Number(qty || 1);
      
      // OPTIMISTIC UPDATE: Update local cart immediately (client-authoritative)
      if (n >= 999) cart.setQty(id, 0);
      else cart.remove(id, n);
      
      // Update UI immediately
      renderCartBadges();
      window.dispatchEvent(new CustomEvent("cart:change"));
      
      // Queue server sync (non-blocking, debounced)
      const newQty = cart._state().items[id] ? cart._state().items[id].qty : 0;
      queueServerSync({
        type: newQty === 0 ? 'delete' : 'set',
        id: id,
        quantity: newQty,
        sequence: ++_syncSequence
      });
      
      return { ok: true };
    } catch (e) {
      console.warn("cartApiRemove failed:", e);
      return { ok: false };
    }
  };
}

/* ============================================================================
 * Cart API Get function for cart-render.js compatibility
 * Uses DB cart endpoints from orders API, then falls back to local storage
 * ========================================================================== */
async function __cartApiGet_impl() {
  const tryParse = async (res) => {
    try {
      return await res.json();
    } catch {
      return { items: [] };
    }
  };

  // 1) DB cart from orders API
  try {
    let r = await fetch("/api/cart/", { credentials: "include" });
    let data = r.ok ? await tryParse(r) : { items: [] };
    if (data && Array.isArray(data.items) && data.items.length) return data;
  } catch (e) {
    console.warn("DB cart fetch failed:", e);
  }

  // 3) Local new format
  try {
    const snap = cart.snapshot();
    if (snap.items && snap.items.length) {
      const items = snap.items.map((item) => ({
        id: parseInt(item.id),
        name: item.name || `Item ${item.id}`,
        quantity: item.qty || 0,
        unit_price: item.price || 0,
        line_total: (item.qty || 0) * (item.price || 0),
        total_unit_price: item.price || 0,
        modifier_price: 0,
        modifier_names: [],
      }));
      return {
        items,
        subtotal: items.reduce((s, it) => s + (it.line_total || 0), 0).toFixed(2),
        meta: snap,
      };
    }
  } catch (e) {
    console.warn("cart_v1 snapshot failed:", e);
  }

  // 4) Legacy array
  try {
    const legacyRaw = localStorage.getItem(LEGACY_CART_KEY);
    if (legacyRaw) {
      const legacyArr = JSON.parse(legacyRaw);
      const formatted = _legacyArrayToFormattedItems(legacyArr);
      if (formatted.length) {
        return {
          items: formatted,
          subtotal: formatted.reduce((s, it) => s + (it.line_total || 0), 0).toFixed(2),
          meta: { source: "legacy" },
        };
      }
    }
  } catch (e) {
    console.warn("legacy cart parse failed:", e);
  }

  return { items: [] };
}

/* ============================================================================
 * Expose globals for compatibility
 * IMPORTANT: Do not override an existing window.cartApiGet (base.html defines one).
 * ========================================================================== */
window.cart = window.cart || cart;
window.api = window.api || api;
window.money = window.money || money;
window.renderCartBadges = window.renderCartBadges || renderCartBadges;

// Only set if not already defined elsewhere (e.g., base.html inline script)
if (typeof window.cartApiGet !== "function") {
  window.cartApiGet = __cartApiGet_impl;
}

/* ============================================================================
 * Ordered, debounced server sync mechanism (prevents race conditions)
 * ========================================================================== */

let _syncTimer = null;

// Queue server sync operations to prevent race conditions
function queueServerSync(operation) {
  _syncQueue.push(operation);
  debounceServerSync();
}

function debounceServerSync(delay = 300) {
  clearTimeout(_syncTimer);
  _syncTimer = setTimeout(processServerSyncQueue, delay);
}

async function processServerSyncQueue() {
  if (_syncInProgress || _syncQueue.length === 0) return;
  
  _syncInProgress = true;
  const failedOperations = [];
  
  try {
    // Process operations in sequence order to prevent conflicts
    _syncQueue.sort((a, b) => a.sequence - b.sequence);
    
    // Group operations by item ID, keeping only the latest operation per item
    const latestOps = new Map();
    for (const op of _syncQueue) {
      const existing = latestOps.get(op.id);
      if (!existing || op.sequence > existing.sequence) {
        latestOps.set(op.id, op);
      }
    }
    
    // Execute the latest operations
    for (const [itemId, operation] of latestOps) {
      try {
        await executeServerSync(operation);
      } catch (error) {
        console.warn(`Server sync failed for item ${itemId}:`, error);
        
        // Add retry logic for certain types of errors
        const shouldRetry = (
          error.name === 'TypeError' && error.message.includes('fetch')
        ) || (
          error.message.includes('Server error (5')
        );
        
        if (shouldRetry && (!operation.retryCount || operation.retryCount < 3)) {
          operation.retryCount = (operation.retryCount || 0) + 1;
          operation.retryDelay = Math.min(1000 * Math.pow(2, operation.retryCount - 1), 10000); // Exponential backoff
          failedOperations.push(operation);
          console.log(`Will retry operation in ${operation.retryDelay}ms (attempt ${operation.retryCount}/3)`);
        } else {
          console.error('Operation failed permanently:', operation, error);
          // For critical errors, we might want to show a persistent notification
          if (operation.retryCount >= 3) {
            showCartNotification('Some cart changes could not be saved. Please refresh the page.', 'error');
          }
        }
      }
    }
    
    // Clear processed operations
    _syncQueue = [];
    
    // Schedule retries for failed operations
    failedOperations.forEach(operation => {
      setTimeout(() => {
        _syncQueue.unshift(operation); // Add back to front of queue
        debounceServerSync(100); // Quick retry
      }, operation.retryDelay);
    });
    
  } finally {
    _syncInProgress = false;
    
    // Process any new operations that were queued during sync
    if (_syncQueue.length > 0) {
      debounceServerSync(100);
    }
  }
}

// User notification helper
function showCartNotification(message, type = 'info') {
  // Try to use existing notification system if available
  if (typeof window.showNotification === 'function') {
    window.showNotification(message, type);
    return;
  }
  
  // Fallback: simple console notification
  const prefix = type === 'error' ? '❌' : type === 'warning' ? '⚠️' : 'ℹ️';
  console.log(`${prefix} ${message}`);
  
  // Try to show in UI if there's a notification area
  const notificationArea = document.querySelector('.notification-area, .alerts, .messages');
  if (notificationArea) {
    const div = document.createElement('div');
    div.className = `alert alert-${type === 'error' ? 'danger' : type === 'warning' ? 'warning' : 'info'}`;
    div.textContent = message;
    div.style.cssText = 'margin: 10px 0; padding: 10px; border-radius: 4px; opacity: 0.9;';
    notificationArea.appendChild(div);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
      if (div.parentNode) div.parentNode.removeChild(div);
    }, 5000);
  }
}

async function executeServerSync(operation) {
  const { type, id, quantity } = operation;
  
  try {
    let response;
    
    switch (type) {
      case 'set':
        if (quantity > 0) {
          response = await jsonFetch("/api/cart/set_quantity/", {
            method: "POST",
            body: JSON.stringify({ menu_item_id: id, quantity: quantity }),
          });
        } else {
          response = await jsonFetch("/api/cart/remove_item/", {
            method: "POST",
            body: JSON.stringify({ menu_item_id: id }),
          });
        }
        break;
        
      case 'delete':
        response = await jsonFetch("/api/cart/remove_item/", {
          method: "POST",
          body: JSON.stringify({ menu_item_id: id }),
        });
        break;
        
      case 'clear':
        response = await jsonFetch("/api/cart/clear/", {
          method: "POST",
        });
        break;
        
      default:
        throw new Error(`Unknown sync operation type: ${type}`);
    }
    
    // Check if response indicates an error
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const errorMessage = errorData.error || `Server error (${response.status})`;
      const errorCode = errorData.code || 'UNKNOWN_ERROR';
      
      // Handle specific error codes
      switch (errorCode) {
        case 'MENU_ITEM_NOT_FOUND':
          showCartNotification('This item is no longer available', 'warning');
          break;
        case 'QUANTITY_TOO_LARGE':
          showCartNotification('Maximum quantity exceeded (999)', 'warning');
          break;
        case 'CART_ITEM_LIMIT':
          showCartNotification('Cart is full (maximum 50 items)', 'warning');
          break;
        case 'INVALID_QUANTITY':
          showCartNotification('Invalid quantity specified', 'error');
          break;
        default:
          showCartNotification(`Cart sync failed: ${errorMessage}`, 'error');
      }
      
      throw new Error(`${errorCode}: ${errorMessage}`);
    }
    
  } catch (error) {
    console.error('Cart sync error:', error);
    
    // Handle network errors
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      showCartNotification('Network error - changes will sync when connection is restored', 'warning');
    } else if (!error.message.includes('Cart sync failed:')) {
      // Only show generic error if we haven't already shown a specific one
      showCartNotification('Failed to sync cart with server', 'error');
    }
    
    // Re-throw to allow caller to handle if needed
    throw error;
  }
}

// Add cart clear function
if (typeof window.cartApiClear !== "function") {
  window.cartApiClear = async function cartApiClear() {
    try {
      // OPTIMISTIC UPDATE: Clear local cart immediately
      cart.clear();
      
      // Update UI immediately
      renderCartBadges();
      window.dispatchEvent(new CustomEvent("cart:change"));
      
      // Queue server sync
      queueServerSync({
        type: 'clear',
        sequence: ++_syncSequence
      });
      
      return { ok: true };
    } catch (e) {
      console.warn("cartApiClear failed:", e);
      return { ok: false };
    }
  };
}

// Legacy sync function for backward compatibility
async function syncCartWithServer() {
  try {
    const snap = cart.snapshot();
    if (snap.items && snap.items.length > 0) {
      // Sync items to DB cart using add_item endpoint
      for (const item of snap.items) {
        await jsonFetch("/api/cart/items/add/", {
          method: "POST",
          body: JSON.stringify({ menu_item_id: item.id, quantity: item.qty }),
        });
      }
    }
  } catch (e) {
    console.warn("Cart sync failed:", e);
  }
}

// Remove automatic sync on cart:change to prevent conflicts
// window.addEventListener("cart:change", () => {
//   debounceSync(syncCartWithServer, 500);
// });
