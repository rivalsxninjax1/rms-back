/* storefront/static/storefront/js/app.js */

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
 * Auth (JWT optional) + API wrapper
 * ============================================================================
 * We keep JWT because parts of your project use it; session auth also works.
 */

const auth = {
  access() {
    return localStorage.getItem("jwt_access") || "";
  },
  refresh() {
    return localStorage.getItem("jwt_refresh") || "";
  },
  set(a, r) {
    if (a) localStorage.setItem("jwt_access", a);
    if (r) localStorage.setItem("jwt_refresh", r);
    // Fire a login event so cart can merge
    window.dispatchEvent(new CustomEvent("auth:login"));
  },
  clear() {
    localStorage.removeItem("jwt_access");
    localStorage.removeItem("jwt_refresh");
    window.dispatchEvent(new CustomEvent("auth:logout"));
  },
};

async function _fetch(url, opts) {
  const res = await fetch(url, opts);
  let data = {};
  try {
    data = await res.json();
  } catch (_) {}
  return { res, data };
}

async function api(url, opts = {}, retry = true) {
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

  // JWT if present
  const t = auth.access();
  if (t) headers.Authorization = "Bearer " + t;

  const first = await _fetch(url, { ...opts, headers, credentials: "include" });

  // If unauthorized and we have a refresh token, try refresh once
  if (first.res.status === 401 && retry && auth.refresh()) {
    try {
      const r = await _fetch("/accounts/jwt/refresh/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ refresh: auth.refresh() }),
      });
      if (r.res.ok && r.data && r.data.access) {
        auth.set(r.data.access, auth.refresh());
        return api(url, opts, false);
      }
    } catch (e) {
      // fall through
    }
  }

  return first;
}

/* ============================================================================
 * Client Cart (guest-persistent with merge-on-login)
 * ============================================================================
 * Storage: localStorage "cart_v1" -> { items: { "<id>": {qty, price, name, image} }, tip, discount, delivery }
 */

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
    // FIX: decrement by exactly one per click (previous buggy code subtracted 2)
    const s = this._state();
    const key = String(id);
    const delta = Math.max(1, Number(qty || 1));
    if (!s.items[key]) return;
    const next = Number(s.items[key].qty || 0) - delta;
    if (next > 0) {
      s.items[key].qty = next;
    } else {
      delete s.items[key];
    }
    this._save(s);
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
  mergeIntoServerIfSupported: async function () {
    // Try to merge with user's saved cart if an endpoint exists.
    // This is defensive — if 404, we silently skip.
    try {
      const snap = this.snapshot();
      const { res } = await api("/api/cart/merge/", {
        method: "POST",
        body: JSON.stringify(snap),
      });
      if (res.status === 404) return; // endpoint not present -> ignore
      if (res.ok) {
        // Server owns the truth now; pull it back to local for consistency
        const { res: r2, data } = await api("/api/cart/", { method: "GET" });
        if (r2.ok && data && data.items) {
          const state = {
            items: {},
            tip: Number(data.tip || 0),
            discount: Number(data.discount || 0),
            delivery: data.delivery || "DINE_IN",
          };
          for (const it of data.items) {
            state.items[String(it.id)] = {
              qty: Number(it.qty || 0),
              name: it.name || "",
              price: Number(it.price || 0),
              image: it.image || null,
            };
          }
          this._save(state);
        }
      }
    } catch (e) {
      // no-op
    }
  },
};

// When user logs in (see auth.set), merge guest cart -> server
window.addEventListener("auth:login", () => {
  cart.mergeIntoServerIfSupported();
});

/* ============================================================================
 * UI Bindings
 * ============================================================================
 * Add data attributes in templates:
 *   data-add="<id>"  data-name="Veg Momo" data-price="199.00" data-image="/media/…"
 *   data-sub="<id>"
 *   data-qty="<id>"  (for numeric inputs)
 *   data-tip, data-discount, data-delivery
 */

function _closest(target, selector) {
  if (!target) return null;
  if (target.matches && target.matches(selector)) return target;
  return target.closest ? target.closest(selector) : null;
}

function renderCartBadges() {
  // Update any elements showing cart count / totals.
  const snap = cart.snapshot();
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
    const addBtn = _closest(ev.target, "[data-add]");
    if (addBtn) {
      const id = addBtn.getAttribute("data-add");
      const name = addBtn.getAttribute("data-name") || "";
      const price = Number(addBtn.getAttribute("data-price") || 0);
      const image = addBtn.getAttribute("data-image") || null;
      cart.add(id, { name, price, image }, 1);
      return;
    }

    const subBtn = _closest(ev.target, "[data-sub]");
    if (subBtn) {
      const id = subBtn.getAttribute("data-sub");
      // FIX: strictly decrement by one per click
      cart.remove(id, 1);
      return;
    }

    const clearBtn = _closest(ev.target, "[data-cart-clear]");
    if (clearBtn) {
      cart.clear();
      return;
    }

    const dineBtn = _closest(ev.target, "[data-delivery]");
    if (dineBtn) {
      cart.setDelivery(dineBtn.getAttribute("data-delivery") || "DINE_IN");
      return;
    }
  });

  // Inputs for direct quantity set, tip, discount
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
  // Optional helper: if a table body with data-cart-body exists, render it.
  const tbody = document.querySelector("[data-cart-body]");
  if (!tbody) return;
  const snap = cart.snapshot();
  tbody.innerHTML = "";
  if (snap.items.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="5" class="text-center text-muted">Your cart is empty.</td></tr>';
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
      <td class="align-middle">₹ ${money(it.price)}</td>
      <td class="align-middle">
        <div class="btn-group" role="group">
          <button type="button" class="btn btn-outline-secondary" data-sub="${it.id}">−</button>
          <input type="number" class="form-control text-center" style="width:80px" min="0" step="1" value="${it.qty}" data-qty="${it.id}">
          <button type="button" class="btn btn-outline-secondary" data-add="${it.id}" data-name="${it.name}" data-price="${it.price}" ${it.image ? `data-image="${it.image}"` : ""}>＋</button>
        </div>
      </td>
      <td class="align-middle fw-semibold">₹ ${money(it.line_total)}</td>
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
 * Checkout glue (calculations happen BEFORE payment)
 * ============================================================================
 */

async function beginCheckout() {
  const snap = cart.snapshot();
  // Keep numbers as integer cents for Stripe safety
  const toCents = (n) => Math.round(Number(n || 0) * 100);

  const payload = {
    items: snap.items.map((it) => ({
      id: it.id,
      qty: it.qty,
      // If your backend needs prices, include them; otherwise omit for server authority
      price_cents: toCents(it.price),
      name: it.name,
    })),
    tip_cents: toCents(snap.tip),
    discount_cents: toCents(snap.discount),
    subtotal_cents: toCents(snap.subtotal),
    total_cents: toCents(snap.total),
    delivery: snap.delivery, // "DINE_IN", "UBER_EATS", "DOORDASH"
  };

  // Hand off to server to create a Stripe session or charge
  const { res, data } = await api("/payments/checkout/", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    alert(data && data.detail ? data.detail : "Unable to start checkout.");
    return;
  }

  if (data && data.redirect_url) {
    // Stripe Hosted Checkout or equivalent
    window.location.href = data.redirect_url;
    return;
  }

  // If server performs payment inline and returns success, clear cart here.
  if (data && data.paid === true) {
    cart.clear();
    window.location.href = "/my-orders/";
  }
}

function bindCheckoutButton() {
  document.addEventListener("click", (ev) => {
    const btn = _closest(ev.target, "[data-begin-checkout]");
    if (!btn) return;
    ev.preventDefault();
    beginCheckout();
  });
}

/* ============================================================================
 * Delivery option popups (no external API calls—just links)
 * ============================================================================
 */

function bindDeliveryPopups() {
  document.addEventListener("click", (ev) => {
    const el = _closest(ev.target, "[data-open-external-order]");
    if (!el) return;
    const url = el.getAttribute("data-url");
    if (!url) return;
    // Mark delivery mode so totals reflect any internal rules (if any).
    if (url.includes("ubereats")) cart.setDelivery("UBER_EATS");
    else if (url.includes("doordash")) cart.setDelivery("DOORDASH");
    else cart.setDelivery("DINE_IN");
    window.open(url, "_blank", "noopener,noreferrer");
  });
}

/* ============================================================================
 * Boot
 * ============================================================================
 */

function boot() {
  bindCartButtons();
  bindCartRendering();
  bindCheckoutButton();
  bindDeliveryPopups();

  // Ping session to ensure CSRF cookie exists before first POST
  api("/session/ping/", { method: "GET" });

  // Initial paint:
  renderCartBadges();
  renderCartTable();
}

if (document.readyState === "complete" || document.readyState === "interactive") {
  setTimeout(boot, 0);
} else {
  document.addEventListener("DOMContentLoaded", boot);
}

/* ============================================================================
 * Navigation Auth Links Handler
 * ============================================================================ */

document.addEventListener('DOMContentLoaded', function() {
  const navLogin = document.getElementById('nav-login');
  const navLogout = document.getElementById('nav-logout');
  const navOrders = document.getElementById('nav-orders');
  const cartCount = document.getElementById('cart-count');
  
  // Handle login button click
  if (navLogin) {
    navLogin.addEventListener('click', function(e) {
      e.preventDefault();
      if (window.__openAuthModalForPay) {
        window.__openAuthModalForPay();
      }
    });
  }

  // Handle logout button click  
  if (navLogout) {
    navLogout.addEventListener('click', async function(e) {
      e.preventDefault();
      try {
        await api('/accounts/logout/', { method: 'POST' });
        auth.clear();
        cart.clear();
        updateAuthNavigation(false);
      } catch (error) {
        console.error('Logout failed:', error);
      }
    });
  }

  // Function to update navigation based on auth status
  function updateAuthNavigation(isAuthenticated) {
    if (navLogin) navLogin.style.display = isAuthenticated ? 'none' : '';
    if (navLogout) navLogout.style.display = isAuthenticated ? '' : 'none';
    if (navOrders) navOrders.style.display = isAuthenticated ? '' : 'none';
  }

  // Check auth status on page load
  checkAuthStatus();

  async function checkAuthStatus() {
    try {
      const { res, data } = await api('/session/ping/');
      if (res.ok && data.is_auth) {
        updateAuthNavigation(true);
      } else {
        updateAuthNavigation(false);
      }
    } catch (error) {
      updateAuthNavigation(false);
    }
  }

  // Listen for auth events
  window.addEventListener('auth:login', () => {
    updateAuthNavigation(true);
  });
  
  window.addEventListener('auth:logout', () => {
    updateAuthNavigation(false);
  });

  // Initialize cart display
  bindCartRendering();
  bindCartButtons();
});
