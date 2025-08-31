/* FILE: storefront/static/storefront/cart-pay.js
 * Pay flow with "service_type" selection and optional coupon.
 * - Uses server session cart
 * - Requires login (now opens the login/signup modal if not authenticated)
 * - Builds the Order on the server and returns a Stripe checkout_url
 */

// Make cartApiGet globally available for cart-render.js
console.log('cart-pay.js is executing');
window.cartApiGet = async function cartApiGet(){
  const r = await fetch("/api/orders/cart-simple/", { 
    credentials: "include"
  });
  if (!r.ok) return { items: [] };
  return await r.json();
}
console.log('cartApiGet defined:', typeof window.cartApiGet);

// Check for cart expiration message
window.checkCartExpiration = async function checkCartExpiration() {
  try {
    const r = await fetch("/api/orders/cart-expired/", { 
      credentials: "include"
    });
    if (r.ok) {
      const data = await r.json();
      if (data.expired) {
        // Show expiration message
        const message = "Your cart has expired after 25 minutes of inactivity.";
        if (typeof showNotification === 'function') {
          showNotification(message, 'warning');
        } else {
          alert(message);
        }
        // Refresh cart display
        if (typeof window.renderCartList === 'function') {
          window.renderCartList();
        }
      }
    }
  } catch (e) {
    console.log('Cart expiration check failed:', e);
  }
};

// Check for expiration on page load
document.addEventListener('DOMContentLoaded', function() {
  window.checkCartExpiration();
});

(function () {
  const $ = (sel, el=document) => el.querySelector(sel);

  // CSRF helpers
  function getCookie(name){
    const m = document.cookie.match(new RegExp("(^| )"+name+"=([^;]+)"));
    return m ? decodeURIComponent(m[2]) : "";
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

  // Merge session cart into user cart after login
  async function mergeSessionCart() {
    try {
      const r = await fetch("/api/orders/cart/merge/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken")
        },
        credentials: "include"
      });
      if (r.ok) {
        console.log('Cart merged successfully');
        // Refresh cart display
        if (typeof window.renderCartList === 'function') {
          window.renderCartList();
        }
      }
    } catch (e) {
      console.log('Cart merge failed:', e);
    }
  }

  // Set up continuation after auth
  window.__continueCheckoutAfterAuth = async function() {
    try {
      // First merge the session cart
      await mergeSessionCart();
      
      // Then proceed with checkout
      const payload = window.__pendingCheckoutPayload || {};
      const result = await checkoutCreate(payload);
      
      if (result.checkout_url) {
        window.location.href = result.checkout_url;
      } else {
        console.error('No checkout URL received');
      }
    } catch (e) {
      console.error('Checkout continuation failed:', e);
      alert('Checkout failed: ' + e.message);
    } finally {
      // Clean up
      delete window.__pendingCheckoutPayload;
    }
  };

  function readMethod(){
    const el = document.querySelector('input[name="order_method_inline"]:checked');
    return el ? String(el.value || "").toUpperCase() : "";
  }

  function readSelectedTable(){
    const sel = document.getElementById("tableSelect");
    if (!sel) return { table_id: null, table_number: null };
    const table_id = sel.value ? Number(sel.value) : null;
    const table_number = sel.selectedOptions && sel.selectedOptions[0]
      ? Number(sel.selectedOptions[0].textContent.match(/Table (\d+)/)?.[1])
      : null;
    return { table_id, table_number };
  }

  async function onPay(){
    // Must be logged in -> if not, open modal
    if (!(await isAuthenticated())){
      // Store the checkout payload for after login
      const method = readMethod();
      if (!method){
        alert("Please choose an order method.");
        return;
      }
      
      let table_id = null;
      let table_number = null;
      if (method === "DINE_IN"){
        const sel = document.getElementById("tableSelect");
        if (!sel || !sel.value){
          alert("Please choose your table.");
          return;
        }
        const t = readSelectedTable();
        table_id = t.table_id;
        table_number = t.table_number;
      }
      
      const coupon_code = ($("#coupon-code") && $("#coupon-code").value || "").trim();
      
      window.__pendingCheckoutPayload = {
        service_type: method === "UBEREATS" ? "UBER_EATS" : method,
        table_id: table_id || undefined,
        table_number: table_number || undefined,
        coupon_code: coupon_code || undefined
      };
      
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
      const sel = document.getElementById("tableSelect");
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

    // Listen for successful login to continue checkout
    document.addEventListener('authSuccess', function() {
      if (window.__continueCheckoutAfterAuth) {
        setTimeout(() => {
          window.__continueCheckoutAfterAuth();
        }, 100); // Small delay to ensure auth state is updated
      }
    });
  });
})();

// Export functions for use by other scripts
window.cartPayFunctions = {
  mergeSessionCart: async function() {
    // This will be defined inside the IIFE, so we need to expose it
    if (window.__continueCheckoutAfterAuth) {
      // The merge function is already available through the continuation
      return;
    }
  }
};
