/* FILE: storefront/static/storefront/cart-render.js
 * Renders the cart list with +/−/remove controls and keeps the header count in sync.
 * Depends on helpers defined in app.js (cartApiGet/cartApiAdd/cartApiRemove/renderCart).
 */
(function () {
  if (window.__CART_RENDER_BOUND__) return;
  window.__CART_RENDER_BOUND__ = true;

  const $ = (sel, el=document) => el.querySelector(sel);

  function lineHTML(item){
    const id = Number(item.id);
    const qty = Number(item.quantity || 0);
    const name = item.name || `Item ${id}`;
    const unit = Number(item.unit_price || 0).toFixed(2);
    const line = Number(item.line_total || (qty * Number(item.unit_price||0))).toFixed(2);

    return `
      <div class="cart-row" data-id="${id}" style="display:flex; align-items:center; justify-content:space-between; gap:12px; border-bottom:1px solid #eee; padding:10px 0;">
        <div style="flex:1;">
          <div style="font-weight:600;">${name}</div>
          <div class="muted">NPR ${unit} each</div>
        </div>
        <div class="qty-controls" style="display:flex; align-items:center; gap:6px;">
          <button class="qty-dec" data-id="${id}" aria-label="Decrease">−</button>
          <span class="qty" data-id="${id}" style="min-width:28px; text-align:center;">${qty}</span>
          <button class="qty-inc" data-id="${id}" aria-label="Increase">+</button>
        </div>
        <div class="line-total" style="min-width:120px; text-align:right;">NPR ${line}</div>
        <button class="remove-item" data-id="${id}" aria-label="Remove" title="Remove" style="margin-left:4px;">✕</button>
      </div>
    `;
  }

  async function renderCartList(){
    const host = $("#cart-items");
    if (!host) return;
    const data = await cartApiGet();
    const items = Array.isArray(data.items) ? data.items : [];
    if (!items.length){
      host.innerHTML = `<p>Your cart is empty.</p>`;
      await renderCart(); // header count
      return;
    }
    host.innerHTML = items.map(lineHTML).join("");
    await renderCart(); // header count + pay enabled
  }

  // Delegate clicks for +/−/remove strictly within the cart list container
  document.addEventListener("click", async (e)=>{
    const host = document.getElementById("cart-items");
    if (!host || !host.contains(e.target)) return;

    const dec = e.target.closest(".qty-dec");
    const inc = e.target.closest(".qty-inc");
    const rem = e.target.closest(".remove-item");
    if (dec){
      const id = Number(dec.getAttribute("data-id"));
      const data = await cartApiGet();
      const cur = (data.items||[]).find(i => Number(i.id) === id);
      const newQty = Math.max(0, Number((cur && cur.quantity) || 1) - 1);
      if (newQty === 0) {
        await cartApiRemove(id);
      } else {
        await cartApiAdd(id, -1);
      }
      await renderCartList();
      return;
    }
    if (inc){
      const id = Number(inc.getAttribute("data-id"));
      await cartApiAdd(id, 1);
      await renderCartList();
      return;
    }
    if (rem){
      const id = Number(rem.getAttribute("data-id"));
      await cartApiRemove(id);
      await renderCartList();
      return;
    }
  });

  document.addEventListener("DOMContentLoaded", renderCartList);
})();
