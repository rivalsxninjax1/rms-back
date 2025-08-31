/* FILE: storefront/static/storefront/cart-extras.js
 * order_extras UI as <select multiple> per modifier group, persisted to server.
 * Depends on helpers defined in app.js and cart-render.js.
 */
(function () {
  if (window.__CART_EXTRAS_BOUND__) return;
  window.__CART_EXTRAS_BOUND__ = true;

  const $ = (sel, el=document) => el.querySelector(sel);
  const $$ = (sel, el=document) => Array.from(el.querySelectorAll(sel));

  async function fetchCart() {
    try {
      const r = await fetch("/api/orders/cart/", { credentials: "include" });
      if (!r.ok) throw new Error("cart fetch failed");
      return await r.json();
    } catch (e) {
      // Fallback to local snapshot
      const snap = (window.cart && window.cart.snapshot) ? window.cart.snapshot() : { items: [] };
      return {
        items: (snap.items || []).map(it => ({ id: it.id, name: it.name, quantity: it.qty, unit_price: String(it.price || 0) })),
        subtotal: String(snap.subtotal || 0),
      };
    }
  }

  async function fetchModifierGroups() {
    try {
      const r = await fetch("/api/orders/cart/modifiers/", { credentials: "include" });
      if (!r.ok) return { modifier_groups: [] };
      return await r.json();
    } catch (e) {
      console.warn("modifier fetch failed", e);
      return { modifier_groups: [] };
    }
  }

  function renderExtrasUI(cartData, groups) {
    const host = $("#extras-section");
    const container = $("#extras-container");
    if (!host || !container) return;

    const items = cartData.items || [];
    // Hide section if no items or no groups
    if (!items.length || !(groups.modifier_groups || []).length) {
      host.style.display = "none";
      container.innerHTML = "";
      return;
    }

    // Build quick lookup for groups per menu_item_id
    const groupsByMenu = new Map();
    for (const g of (groups.modifier_groups || [])) {
      if (!groupsByMenu.has(g.menu_item_id)) groupsByMenu.set(g.menu_item_id, []);
      groupsByMenu.get(g.menu_item_id).push(g);
    }

    // Build HTML
    let html = "";
    for (const it of items) {
      const menuId = Number(it.id);
      const gList = groupsByMenu.get(menuId) || [];
      if (!gList.length) continue;

      html += '<div class="extras-block" style="border-top:1px dashed #eee; padding-top:12px; margin-top:12px;">';
      html += `<div style="font-weight:600; margin-bottom:8px;">Extras for ${it.name || ("Item "+menuId)}</div>`;

      for (const g of gList) {
        html += `<label style="display:block; font-weight:600; margin:8px 0 6px;">${g.name} ${g.is_required ? '(required)' : ''}</label>`;
        const multiple = (g.max_select || 0) !== 1;
        const size = Math.min(6, Math.max(2, (g.modifiers || []).length));
        html += `<select class="extras-select" data-item-id="${menuId}" data-group-id="${g.id}" ${multiple ? 'multiple' : ''} size="${size}" style="width:100%; padding:6px;">`;
        for (const m of (g.modifiers || [])) {
          const price = Number(m.price || 0).toFixed(2);
          const name = m.name + (price > 0 ? ` (+NPR ${price})` : "");
          html += `<option value="${m.id}" data-price="${price}">${name}</option>`;
        }
        html += `</select>`;
        if (g.min_select || g.max_select) {
          html += `<div class="muted" style="font-size:12px; color:#666; margin-top:4px;">Select ${g.min_select || 0}${g.max_select ? '–'+g.max_select : '+'}</div>`;
        }
      }

      html += "</div>";
    }

    container.innerHTML = html;

    // Preselect currently-chosen modifiers by matching names (server returns modifier_names)
    const nameToId = new Map();
    for (const g of (groups.modifier_groups || [])) {
      for (const m of (g.modifiers || [])) nameToId.set(m.name, m.id);
    }
    const itemsById = new Map((cartData.items || []).map(x => [Number(x.id), x]));
    $$(".extras-select", container).forEach(sel => {
      const itemId = Number(sel.getAttribute("data-item-id"));
      const item = itemsById.get(itemId) || {};
      const names = item.modifier_names || [];
      const ids = names.map(n => nameToId.get(n)).filter(Boolean);
      for (const opt of sel.options) {
        if (ids.includes(Number(opt.value))) opt.selected = true;
      }
    });

    host.style.display = "";
  }

  async function updateItemModifiers(itemId) {
    // Collect all selected modifiers across groups for this item
    const container = $("#extras-container");
    const selects = $$(".extras-select", container).filter(s => Number(s.getAttribute("data-item-id")) === Number(itemId));
    const ids = [];
    for (const sel of selects) {
      for (const opt of sel.selectedOptions) {
        ids.push(Number(opt.value));
      }
    }
    // Build payload with modifiers; quantity delta 0 to preserve qty
    const payload = { id: Number(itemId), quantity: 0, modifiers: ids.map(i => ({ id: i })) };
    await api("/api/orders/cart/items", { method: "POST", body: JSON.stringify(payload) });
    // Re-render cart list to reflect new prices
    if (typeof window.renderCartList === "function") await window.renderCartList();
  }

  // Wire events
  document.addEventListener("change", async (e) => {
    const sel = e.target.closest(".extras-select");
    if (!sel) return;
    const itemId = sel.getAttribute("data-item-id");
    await updateItemModifiers(itemId);
  });

  // Initial render & on cart change
  async function refresh() {
    const [cartData, groups] = await Promise.all([fetchCart(), fetchModifierGroups()]);
    renderExtrasUI(cartData, groups);
  }
  window.addEventListener("cart:change", refresh);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", refresh);
  } else {
    setTimeout(refresh, 100);
  }
})();
