/* storefront/static/storefront/cart-session-guard.js
 * Defensive: ensure cart survives navigation and reflect count in header.
 */
(function () {
  // $ utility is now available from utils.js
  async function fetchCart() {
    const r = await fetch("/api/cart/", { credentials: "include" });
    const d = await r.json().catch(() => ({ items: [] }));
    if (!d.items) d.items = [];
    return d.items;
  }
  function updateBadge(items) {
    try {
      const count = (items || []).reduce((n, it) => n + (parseInt(it.quantity||0)||0), 0);
      const badge = $("#cart-count");
      if (badge) badge.textContent = String(count);
    } catch (e) {}
  }
  document.addEventListener("DOMContentLoaded", async () => {
    try { updateBadge(await fetchCart()); } catch (e) {}
  });
})();
