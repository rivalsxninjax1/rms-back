/* FILE: storefront/static/storefront/cart-pay.js
 * Pay flow with "service_type" selection and optional coupon.
 * - Uses server session cart
 * - Requires login (now opens the login/signup modal if not authenticated)
 * - Builds the Order on the server and returns a Stripe checkout_url
 */
(function () {
  const $ = (sel, el=document) => el.querySelector(sel);

  // CSRF helpers
  function getCookie(name){
    const m = document.cookie.match(new RegExp("(^| )"+name+"=([^;]+)"));
    return m ? decodeURIComponent(m[2]) : "";
  }

  async function cartApiGet(){
    const r = await fetch("/api/orders/cart/", { credentials: "include" });
    if (!r.ok) return { items: [] };
    return await r.json();
  }

  async function isAuthenticated(){
    try{
      const r = await fetch("/accounts/auth/whoami/", { credentials:"include" });
      const j = await r.json().catch(()=>({authenticated:false}));
      return !!j.authenticated;
    }catch{return false;}
  }

  // openAuth(step) is defined in app.js; this safely no-ops to /login/?next= if modal is missing
  function requireAuthOrModal(){
    if (typeof openAuth === "function"){
      openAuth("login");
    } else {
      const next = encodeURIComponent(window.location.pathname + window.location.search);
      window.location.href = `/login/?next=${next}`;
    }
  }

  async function checkoutCreate(payload){
    const r = await fetch("/api/orders/orders/", {
      method: "POST",
      headers: {
        "Content-Type":"application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      credentials: "include",
      body: JSON.stringify(payload)
    });
    const j = await r.json().catch(()=> ({}));
    if (!r.ok) {
      // If backend says auth required, show the modal instead of alert
      if (r.status === 401) {
        requireAuthOrModal();
        throw new Error("Please log in to continue.");
      }
      const msg = j && (j.detail || JSON.stringify(j)) || "Checkout failed";
      throw new Error(msg);
    }
    return j;
  }

  function readMethod(){
    const el = document.querySelector('input[name="order_method_inline"]:checked');
    return el ? String(el.value || "").toUpperCase() : "";
  }

  function readSelectedTable(){
    const sel = document.getElementById("table-select");
    if (!sel) return { table_id: null, table_number: null };
    const table_id = sel.value ? Number(sel.value) : null;
    const table_number = sel.selectedOptions && sel.selectedOptions[0]
      ? Number(sel.selectedOptions[0].getAttribute("data-number"))
      : null;
    return { table_id, table_number };
  }

  async function onPay(){
    // Must be logged in -> if not, open modal
    if (!(await isAuthenticated())){
      requireAuthOrModal();
      return;
    }

    // Require at least one item
    const data = await cartApiGet();
    if (!data.items || !data.items.length){
      alert("Your cart is empty.");
      return;
    }

    // Require method
    let method = readMethod();
    if (!method){
      alert("Please choose an order method.");
      return;
    }
    if (method === "UBEREATS") method = "UBER_EATS"; // normalize

    // Dine-in requires a selected table from RMS Admin
    let table_id = null;
    let table_number = null;
    if (method === "DINE_IN"){
      const sel = document.getElementById("table-select");
      if (!sel || !sel.value){
        alert("Please choose your table.");
        return;
      }
      const t = readSelectedTable();
      table_id = t.table_id;
      table_number = t.table_number;
    }

    // Coupon (optional)
    const coupon_code = ($("#coupon-code") && $("#coupon-code").value || "").trim();

    const payload = {
      service_type: method,                 // "DINE_IN" | "UBER_EATS" | "DOORDASH"
      table_id: table_id || undefined,      // prefers precise RMS Table id
      table_number: table_number || undefined, // also send number (for fallback)
      coupon_code: coupon_code || undefined
    };

    try{
      const res = await checkoutCreate(payload);
      if (res && res.checkout_url){
        window.location.href = res.checkout_url;
      } else {
        alert("Could not start checkout.");
      }
    }catch(err){
      if (err && /log in/i.test(err.message)) return; // modal already opened
      alert(err.message || "Checkout failed.");
    }
  }

  document.addEventListener("DOMContentLoaded", ()=>{
    const btn = document.getElementById("pay-btn");
    if (btn && !btn._bound){
      btn._bound = true;
      btn.addEventListener("click", (e)=>{ e.preventDefault(); onPay(); });
    }

    const apply = document.getElementById("apply-coupon");
    if (apply && !apply._bound){
      apply._bound = true;
      apply.addEventListener("click", ()=>{
        const msg = document.getElementById("coupon-msg");
        if (msg) {
          msg.textContent = "Coupon will be applied at checkout.";
          setTimeout(()=> msg.textContent = "", 3000);
        }
      });
    }
  });
})();
