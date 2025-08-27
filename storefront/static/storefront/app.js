/* storefront/static/storefront/app.js
 * Session-based cart + tip persistence + dine-in hold
 */

function currency(amount){
  const cur = (window.DEFAULT_CURRENCY || "NPR");
  return `${cur} ${Number(amount||0).toFixed(2)}`;
}
function getCookie(name){
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
  if (match) return match[2];
  return "";
}

async function api(url, {method="GET", json=null}={}){
  const headers = {"Content-Type":"application/json"};
  const opts = {method, headers, credentials:"include"};
  if (json) opts.body = JSON.stringify(json);
  const res = await fetch(url, opts);
  let data=null;
  try{ data = await res.json(); }catch{}
  return {res, data};
}

/* ====== Cart store in session (server owns it) ====== */
async function fetchCart(){
  // Assuming you already have a backend endpoint (if not, this function can be wired later)
  // For now, read items stamped by server in the page or fallback to localStorage mock:
  let items = JSON.parse(localStorage.getItem("cart_items") || "[]");
  // shape: [{id,name,unit_price,quantity}]
  return items;
}

function renderCart(items){
  const root = document.getElementById("cart-items");
  if(!root) return;
  root.innerHTML = "";
  if(!items.length){
    root.innerHTML = '<p>Your cart is empty.</p>';
    document.getElementById("pay-btn").disabled = true;
    return;
  }
  for (const it of items){
    const div = document.createElement("div");
    div.className = "cart-item";
    div.style.margin = "8px 0";
    div.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
          <div style="font-weight:600">${it.name || "Item"}</div>
          <div>Qty: ${it.quantity||1} × ${currency(it.unit_price||0)}</div>
        </div>
        <div style="font-weight:600">${currency((it.quantity||1) * (it.unit_price||0))}</div>
      </div>`;
    root.appendChild(div);
  }
  document.getElementById("pay-btn").disabled = false;
}

function calcSubtotal(items){
  let s = 0;
  for(const it of items){
    const qty = Number(it.quantity||1);
    const unit = Number(it.unit_price||0);
    s += qty*unit;
  }
  return s;
}

async function refreshTotals(){
  const items = await fetchCart();
  const sub = calcSubtotal(items);
  const tip = Number(localStorage.getItem("cart_tip_amount") || "0");
  const disc = Number(localStorage.getItem("cart_discount_amount") || "0"); // optional preview only
  const total = Math.max(0, sub + tip - disc);

  document.getElementById("subtotal").textContent = currency(sub);
  document.getElementById("tip-amount").textContent = currency(tip);
  const row = document.getElementById("discount-row");
  if (disc>0){ row.style.display=""; document.getElementById("discount-amount").textContent = currency(disc); }
  else { row.style.display="none"; }
  document.getElementById("grand-total").textContent = currency(total);
}

async function saveTip(amount){
  amount = Math.max(0, Number(amount||0));
  localStorage.setItem("cart_tip_amount", String(amount));

  // also persist server-side (session)
  await api("/storefront/api/cart/tip/", {method:"POST", json:{tip_amount: amount}});
  const msg = document.getElementById("tip-msg");
  if (msg){ msg.textContent = "Saved."; setTimeout(()=>msg.textContent="", 1200); }
  await refreshTotals();
}

async function maybeCreateHold(){
  const method = document.querySelector('input[name="order_method_inline"]:checked');
  if (!method || method.value !== "DINE_IN") return;
  const tableId = document.getElementById("table-select")?.value;
  if (!tableId) return;
  await api("/reservations_portal/api/holds/create/", {method:"POST", json:{table_id: Number(tableId)}});
}

async function onPay(){
  await maybeCreateHold();
  // redirect to your existing "create checkout session" URL for the current order
  // If you show order id on page, use that; here we assume the backend knows which open order belongs to this session.
  window.location.href = (window.CHECKOUT_URL || "/payments/create-checkout-session/1/"); // replace with actual order id in template context
}

document.addEventListener("DOMContentLoaded", async ()=>{
  const items = await fetchCart();
  renderCart(items);
  await refreshTotals();

  const btn = document.getElementById("save-tip-btn");
  const input = document.getElementById("tip-input");
  if (btn && input){
    // restore persisted tip
    const existing = Number(localStorage.getItem("cart_tip_amount") || "0");
    input.value = existing.toFixed(2);
    btn.addEventListener("click", ()=>saveTip(input.value));
  }

  const pay = document.getElementById("pay-btn");
  if (pay){ pay.addEventListener("click", onPay); }
});
