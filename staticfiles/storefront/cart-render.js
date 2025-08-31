/* FILE: storefront/static/storefront/cart-render.js
 * Renders the cart list with +/−/remove controls and keeps the header count in sync.
 * Depends on helpers defined in app.js (cartApiGet/cartApiAdd/cartApiRemove/renderCartBadges).
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
    const modifierPrice = Number(item.modifier_price || 0).toFixed(2);
    const totalUnitPrice = Number(item.total_unit_price || item.unit_price || 0).toFixed(2);
    const line = Number(item.line_total || (qty * Number(item.total_unit_price || item.unit_price || 0))).toFixed(2);
    const image = item.image || '/static/storefront/img/placeholder.svg';
    
    // Build modifier display with collapsible extras
    let modifierDisplay = '';
    if (item.modifier_names && item.modifier_names.length > 0) {
      const modifierCount = item.modifier_names.length;
      const modifierText = modifierCount === 1 ? item.modifier_names[0] : `${modifierCount} extras`;
      modifierDisplay = `
        <div class="extras-section" style="margin-top: 4px;">
          <button class="extras-toggle" data-id="${id}" style="background: none; border: none; color: #007bff; font-size: 12px; padding: 0; cursor: pointer; text-decoration: underline;">
            + ${modifierText} (+NPR ${modifierPrice}) ▼
          </button>
          <div class="extras-details" data-id="${id}" style="display: none; color: #666; font-size: 11px; margin-top: 2px; padding-left: 8px;">
            ${item.modifier_names.map(name => `• ${name}`).join('<br>')}
          </div>
        </div>
      `;
    }

    return `
      <div class="cart-row" data-id="${id}" style="display:flex; align-items:flex-start; gap:12px; border-bottom:1px solid #eee; padding:12px 0;">
        <div class="item-image" style="width: 60px; height: 60px; flex-shrink: 0;">
          <img src="${image}" alt="${name}" style="width: 100%; height: 100%; object-fit: cover; border-radius: 8px; background: #f7f7f7;" onerror="this.src='/static/storefront/img/placeholder.svg'">
        </div>
        <div class="item-details" style="flex: 1; min-width: 0;">
          <div class="item-name" style="font-weight: 600; font-size: 14px; margin-bottom: 2px;">${name}</div>
          <div class="item-price" style="color: #666; font-size: 12px;">NPR ${unit} each${Number(modifierPrice) > 0 ? ` (NPR ${totalUnitPrice} with extras)` : ''}</div>
          ${modifierDisplay}
        </div>
        <div class="qty-controls" style="display:flex; align-items:center; gap:8px; margin-top: 4px;">
          <button class="qty-dec" data-id="${id}" aria-label="Decrease" style="width: 28px; height: 28px; border: 1px solid #ddd; background: #f8f9fa; border-radius: 4px; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 16px; color: #666;">−</button>
          <span class="qty" data-id="${id}" style="min-width: 32px; text-align: center; font-weight: 600; font-size: 14px;">${qty}</span>
          <button class="qty-inc" data-id="${id}" aria-label="Increase" style="width: 28px; height: 28px; border: 1px solid #ddd; background: #f8f9fa; border-radius: 4px; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 16px; color: #666;">+</button>
        </div>
        <div class="line-total" style="min-width: 80px; text-align: right; font-weight: 600; font-size: 14px; margin-top: 4px;">NPR ${line}</div>
        <button class="remove-item" data-id="${id}" aria-label="Remove" title="Remove item" style="width: 24px; height: 24px; border: none; background: #dc3545; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 12px; margin-top: 4px;">✕</button>
      </div>
    `;
  }

  async function renderCartList(){
    const host = $("#cart-items");
    if (!host) return;
    
    // Wait for cartApiGet to be available with more robust checking
    let attempts = 0;
    const maxAttempts = 100; // 10 seconds
    
    while (!window.cartApiGet && attempts < maxAttempts) {
      console.log(`Waiting for cartApiGet... attempt ${attempts + 1}`);
      await new Promise(resolve => setTimeout(resolve, 100));
      attempts++;
    }
    
    if (!window.cartApiGet) {
      console.error('cartApiGet not available after', maxAttempts * 100, 'ms');
      console.log('Available window properties:', Object.keys(window).filter(k => k.includes('cart')));
      host.innerHTML = `<p>Unable to load cart items. Please refresh the page.</p>`;
      return;
    }
    
    console.log('cartApiGet found, proceeding with cart rendering');
    
    const data = await window.cartApiGet();
    const items = Array.isArray(data.items) ? data.items : [];
    if (!items.length){
      host.innerHTML = `<p>Your cart is empty.</p>`;
      if (window.renderCartBadges) window.renderCartBadges(); // header count
      return;
    }
    host.innerHTML = items.map(lineHTML).join("");
    if (window.renderCartBadges) window.renderCartBadges(); // header count + pay enabled
    
    // Trigger cart change event for totals update
    if (window.dispatchEvent) {
      window.dispatchEvent(new CustomEvent('cart:change'));
    }
  }

  // Delegate clicks for +/−/remove/extras toggle strictly within the cart list container
  document.addEventListener("click", async (e)=>{
    const host = document.getElementById("cart-items");
    if (!host || !host.contains(e.target)) return;

    const dec = e.target.closest(".qty-dec");
    const inc = e.target.closest(".qty-inc");
    const rem = e.target.closest(".remove-item");
    const extrasToggle = e.target.closest(".extras-toggle");
    
    if (extrasToggle){
      const id = extrasToggle.getAttribute("data-id");
      const extrasDetails = host.querySelector(`.extras-details[data-id="${id}"]`);
      const toggleButton = extrasToggle;
      
      if (extrasDetails) {
        const isVisible = extrasDetails.style.display !== 'none';
        extrasDetails.style.display = isVisible ? 'none' : 'block';
        
        // Update arrow direction
        const buttonText = toggleButton.textContent;
        if (isVisible) {
          toggleButton.textContent = buttonText.replace('▲', '▼');
        } else {
          toggleButton.textContent = buttonText.replace('▼', '▲');
        }
      }
      return;
    }
    
    if (dec){
      const id = Number(dec.getAttribute("data-id"));
      // The cart.remove function now handles preventing quantities below 1
      await cartApiAdd(id, -1);
      await renderCartList();
      return;
    }
    if (inc){
      const id = Number(inc.getAttribute("data-id"));
      if (inc.disabled) return;
      inc.disabled = true;
      try {
        await cartApiAdd(id, 1);
        await renderCartList();
      } finally {
        inc.disabled = false;
      }
      return;
    }
    if (rem){
      const id = Number(rem.getAttribute("data-id"));
      // Use high quantity (999) to completely remove the item
      await cartApiRemove(id, 999);
      await renderCartList();
      return;
    }
  });

  // Use a more robust initialization that waits for all scripts
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', renderCartList);
  } else {
    // DOM is already loaded, wait a bit for other scripts
    setTimeout(renderCartList, 100);
  }

  // expose for extras script to re-render after modifier updates
  window.renderCartList = renderCartList;
})();
