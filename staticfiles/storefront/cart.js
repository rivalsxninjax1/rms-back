// FILE: rms-back/payments/static/js/cart.js
(function () {
  function getCookie(name) {
    const v = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return v ? v.pop() : "";
  }
  const csrftoken = getCookie("csrftoken");

  function getLS() {
    try { return JSON.parse(localStorage.getItem("cart") || "[]"); }
    catch(_) { return []; }
  }
  function setLS(items) {
    localStorage.setItem("cart", JSON.stringify(items));
  }

  async function syncWithServer(items) {
    try {
      const res = await fetch("/api/cart/sync/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrftoken },
        body: JSON.stringify({ items })
      });
      return await res.json();
    } catch (e) {
      console.error("Cart sync failed", e);
      return { items };
    }
  }

  function normalizeItem(it) {
    const id = parseInt(it.menu_item || it.id || it.menu || it.menu_id || it.product || it.product_id, 10);
    const qty = parseInt(it.quantity || it.qty || it.q || 1, 10);
    if (!id || id <= 0 || !qty || qty <= 0) return null;
    return { id: id, quantity: qty };
  }

  function upsertCartLS(menuId, qtyDelta) {
    const idNum = parseInt(menuId, 10);
    const items = getLS()
      .map(normalizeItem)
      .filter(Boolean);

    const idx = items.findIndex(it => it.id === idNum);
    if (idx === -1) items.push({ id: idNum, quantity: Math.max(1, qtyDelta) });
    else items[idx].quantity = Math.max(1, (parseInt(items[idx].quantity, 10) || 1) + qtyDelta);

    setLS(items);
    return items;
  }

  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-add-to-cart]");
    if (!btn) return;

    e.preventDefault();
    const menuId = btn.getAttribute("data-menu-id") || btn.getAttribute("data-id");
    if (!menuId) { console.warn("Missing data-menu-id"); return; }

    const qtyInput = document.querySelector("[data-qty-input]");
    const qty = qtyInput ? (parseInt(qtyInput.value, 10) || 1) : 1;

    const merged = upsertCartLS(menuId, qty);
    await syncWithServer(merged);

    btn.disabled = true;
    const prev = btn.innerText;
    btn.innerText = "Added ✓";
    setTimeout(() => { btn.disabled = false; btn.innerText = prev || "Add to cart"; }, 1200);
  });

  // On page load (including after login), sync LS -> session
  (async function bootstrapSync() {
    const items = getLS().map(normalizeItem).filter(Boolean);
    if (items.length) await syncWithServer(items);

    // Load tables into "Choose Table" dropdown
    try {
      const res = await fetch("/api/tables/");
      const data = await res.json();
      const select = document.getElementById("tableSelect");
      if (select && data.tables) {
        select.innerHTML = "";
        
        // Group tables by location for better organization
        const tablesByLocation = {};
        data.tables.forEach(t => {
          const locationName = t.location_name || `Location ${t.location_id}`;
          if (!tablesByLocation[locationName]) {
            tablesByLocation[locationName] = [];
          }
          tablesByLocation[locationName].push(t);
        });
        
        // Create options, grouped by location if multiple locations exist
        const locationCount = Object.keys(tablesByLocation).length;
        
        Object.entries(tablesByLocation).forEach(([locationName, tables]) => {
          // Add location group header if multiple locations
          if (locationCount > 1) {
            const optgroup = document.createElement("optgroup");
            optgroup.label = locationName;
            
            tables.forEach(t => {
              const opt = document.createElement("option");
              opt.value = t.id;
              
              // Create descriptive text with source info
              let description = `Table ${t.table_number} (Capacity: ${t.capacity})`;
              
              // Add source-specific information
              if (t.source === 'core' && t.table_type) {
                description += ` - ${t.table_type.charAt(0).toUpperCase() + t.table_type.slice(1)}`;
              } else if (t.source === 'inventory' && t.condition) {
                description += ` - ${t.condition.charAt(0).toUpperCase() + t.condition.slice(1)} condition`;
              }
              
              opt.textContent = description;
              opt.setAttribute('data-source', t.source);
              opt.setAttribute('data-source-id', t.source_id);
              optgroup.appendChild(opt);
            });
            
            select.appendChild(optgroup);
          } else {
            // Single location - no grouping needed
            tables.forEach(t => {
              const opt = document.createElement("option");
              opt.value = t.id;
              
              let description = `Table ${t.table_number} (Capacity: ${t.capacity})`;
              
              // Add source-specific information
              if (t.source === 'core' && t.table_type) {
                description += ` - ${t.table_type.charAt(0).toUpperCase() + t.table_type.slice(1)}`;
              } else if (t.source === 'inventory' && t.condition) {
                description += ` - ${t.condition.charAt(0).toUpperCase() + t.condition.slice(1)} condition`;
              }
              
              opt.textContent = description;
              opt.setAttribute('data-source', t.source);
              opt.setAttribute('data-source-id', t.source_id);
              select.appendChild(opt);
            });
          }
        });
        
        // Log sync info for debugging
        if (data.total_sources) {
          console.log(`Tables loaded from ${data.total_sources} synchronized sources`);
        }
      }
    } catch (err) {
      console.error("Failed to load tables", err);
    }
  })();
})();
