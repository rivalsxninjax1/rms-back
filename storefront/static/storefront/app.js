/* storefront/static/storefront/app.js
 * Session auth + Cart in server session + Auth-gated checkout
 * - Guests can add to cart (session-based)
 * - Checkout requires login (modal, then resume)
 * - Coupons optional via localStorage (UI-only)
 * - No JWT required
 */

/* ===========================
 * Utilities
 * =========================== */
function currency(amount){
  const cur = (window.DEFAULT_CURRENCY || "NPR");
  return `${cur} ${Number(amount||0).toFixed(2)}`;
}
function getCookie(name){
  const m = document.cookie.match(new RegExp("(^| )"+name+"=([^;]+)"));
  return m ? decodeURIComponent(m[2]) : "";
}

/* ===========================
 * Session auth helpers
 * =========================== */
async function whoami(){
  try{
    const r = await fetch("/accounts/auth/whoami/", { credentials:"include" });
    const j = await r.json().catch(()=>({authenticated:false}));
    return j;
  }catch{return {authenticated:false};}
}
async function isAuthenticated(){ const j = await whoami(); return !!j.authenticated; }

/* Auth modal helpers */
const modalEl = () => document.getElementById("auth-modal");
function show(step){
  ["choice","login","signup"].forEach(s=>{
    const el=document.getElementById("auth-step-"+s);
    if(el) el.classList.toggle("hidden", s!==step);
  });
}
function openAuth(step="login"){
  const m=modalEl();
  if(!m){
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    // Fallback to storefront login page (HTML), not JSON endpoint
    window.location.href = `/login/?next=${next}`;
    return;
  }
  m.classList.remove("hidden");
  show(step);
}
function closeAuth(){
  const m=modalEl();
  if(m) m.classList.add("hidden");
}

/* ===========================
 * Header auth state + nav
 * =========================== */
async function refreshHeaderAuth(){
  const linkLogin  = document.getElementById("nav-login") || document.getElementById("auth-link");
  const linkLogout = document.getElementById("nav-logout");
  const linkOrders = document.getElementById("nav-orders") || document.querySelector('a[href="/my-orders/"]');

  const authed = await isAuthenticated();
  if (linkLogin)  linkLogin.style.display  = authed ? "none" : "";
  if (linkLogout) linkLogout.style.display = authed ? "" : "none";
  if (linkOrders) linkOrders.style.display = authed ? "" : "none";

  if (linkLogin && !linkLogin._bound){
    linkLogin._bound = true;
    linkLogin.addEventListener("click", (e)=>{ e.preventDefault(); openAuth("login"); });
  }

  if (linkLogout && !linkLogout._bound){
    linkLogout._bound = true;
    linkLogout.addEventListener("click", async (e)=>{
      e.preventDefault();
      try { 
        await fetch("/accounts/logout/", {
          method:"POST",
          headers: { "X-CSRFToken": getCookie("csrftoken") },
          credentials:"include"
        });
      } catch {}
      try { await cartApiReset(); } catch {}
      try { clearAppliedCoupon(); } catch {}
      try { window.location.href = "/"; } catch { location.reload(); }
    });
  }

  if (linkOrders && !linkOrders._bound2){
    linkOrders._bound2 = true;
    linkOrders.addEventListener("click", async (e)=>{
      if(!(await isAuthenticated())){
        e.preventDefault();
        openAuth("login");
      }
    });
  }
}

/* ===========================
 * Server Cart API (session)
 * =========================== */
async function cartApiGet(){
  const r = await fetch("/api/orders/cart/", { credentials: "include" });
  if (!r.ok) return { items: [], subtotal: "0.00", currency: "NPR", meta: {} };
  return await r.json();
}
async function cartApiAdd(id, qty){
  await fetch("/api/orders/cart/items/", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") },
    credentials: "include",
    body: JSON.stringify({ id, quantity: qty })
  });
}
async function cartApiRemove(id){
  await fetch("/api/orders/cart/items/remove/", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") },
    credentials: "include",
    body: JSON.stringify({ id })
  });
}
async function cartApiSet(items){
  await fetch("/api/orders/cart/", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") },
    credentials: "include",
    body: JSON.stringify({ items })
  });
}
async function cartApiReset(){
  await fetch("/api/orders/cart/reset_session/", {
    method: "POST",
    headers: { "X-CSRFToken": getCookie("csrftoken") },
    credentials: "include"
  });
}
async function cartApiMergeAfterLogin(){
  await fetch("/api/orders/cart/merge/", {
    method: "POST",
    headers: { "X-CSRFToken": getCookie("csrftoken") },
    credentials: "include"
  });
}

/* coupon helpers (UI only) */
function clearAppliedCoupon(){
  try{ localStorage.removeItem("applied_coupon"); }catch{}
}

/* ===========================
 * Render cart badge + small helpers
 * =========================== */
async function renderCart(){
  try{
    const data = await cartApiGet();
    const items = Array.isArray(data.items) ? data.items : [];
    const count = items.reduce((a,i)=> a + Number(i.quantity||0), 0);
    const el=document.getElementById("cart-count");
    if(el) el.textContent = String(count || 0);
    const payBtn=document.querySelector("#pay-btn, [data-checkout]");
    if (payBtn){
      payBtn.disabled = !items.length;
      payBtn.title = items.length ? "" : "Add at least one item to cart.";
    }
  }catch{}
}

/* ===========================
 * Auth modal bindings
 * =========================== */
function bindAuthModal(){
  const m = modalEl();
  if(!m) return;

  const btnChoiceLogin = document.getElementById("btn-open-login");
  const btnChoiceSignup = document.getElementById("btn-open-signup");
  const btnClose = document.getElementById("auth-close");
  const aToSignup = document.getElementById("link-to-signup");
  const aToLogin = document.getElementById("link-to-login");

  if(btnClose && !btnClose._bound){
    btnClose._bound = true;
    btnClose.addEventListener("click", ()=> closeAuth());
  }

  if(btnChoiceLogin && !btnChoiceLogin._bound){
    btnChoiceLogin._bound = true;
    btnChoiceLogin.addEventListener("click", ()=> show("login"));
  }
  if(btnChoiceSignup && !btnChoiceSignup._bound){
    btnChoiceSignup._bound = true;
    btnChoiceSignup.addEventListener("click", ()=> show("signup"));
  }
  if(aToSignup && !aToSignup._bound){
    aToSignup._bound = true;
    aToSignup.addEventListener("click", (e)=>{ e.preventDefault(); show("signup"); });
  }
  if(aToLogin && !aToLogin._bound){
    aToLogin._bound = true;
    aToLogin.addEventListener("click", (e)=>{ e.preventDefault(); show("login"); });
  }

  const formLogin = document.getElementById("modal-login-form");
  if(formLogin && !formLogin._bound){
    formLogin._bound = true;
    formLogin.addEventListener("submit", async (e)=>{
      e.preventDefault();
      const fd = new FormData(formLogin);
      const payload = {
        username: (fd.get("username")||"").trim(),
        password: fd.get("password"),
      };
      const res = await fetch("/accounts/login/", {
        method:"POST",
        headers:{"Content-Type":"application/json","X-CSRFToken": getCookie("csrftoken")},
        credentials:"include",
        body: JSON.stringify(payload)
      });
      const data=await res.json().catch(()=>({}));
      const st=document.getElementById("modal-login-status");
      if(res.ok && data && data.ok){
        try { await cartApiMergeAfterLogin(); } catch {}
        st.textContent=""; closeAuth();
        try { await refreshHeaderAuth(); await renderCart(); } catch {}
        try{
          const p = new URLSearchParams(window.location.search).get("next");
          if (p) window.location.href = p; else window.location.reload();
        }catch{
          window.location.reload();
        }
      } else {
        st.textContent=(data && (data.detail||JSON.stringify(data))) || "Login failed.";
      }
    });
  }

  const formSignup = document.getElementById("modal-signup-form");
  if(formSignup && !formSignup._bound){
    formSignup._bound = true;
    formSignup.addEventListener("submit", async (e)=>{
      e.preventDefault();
      const fd = new FormData(formSignup);
      const payload = {
        username:(fd.get("username")||"").trim(),
        email:(fd.get("email")||"").trim().toLowerCase(),
        first_name:fd.get("first_name") || "",
        last_name:fd.get("last_name") || "",
        password:fd.get("password"),
      };
      const res = await fetch("/accounts/register/", {
        method:"POST",
        headers:{"Content-Type":"application/json","X-CSRFToken": getCookie("csrftoken")},
        credentials:"include",
        body: JSON.stringify(payload)
      });
      const data=await res.json().catch(()=>({}));
      const st=document.getElementById("modal-signup-status");
      if(res.ok && data && data.ok){
        try { await cartApiMergeAfterLogin(); } catch {}
        st.textContent=""; closeAuth();
        try { await refreshHeaderAuth(); await renderCart(); } catch {}
        try{
          const href = new URLSearchParams(window.location.search).get("next");
          if (href) window.location.href = href; else window.location.reload();
        }catch{
          if (href) window.location.href = href; else window.location.reload();
        }
      } else {
        st.textContent=(data && (data.detail||JSON.stringify(data))) || "Signup failed.";
      }
    });
  }
}

/* ===========================
 * Events: Add-to-cart ONLY (qty handled in cart-render.js)
 * =========================== */
document.addEventListener("click", async (e) => {
  // 1) Add-to-cart via class
  const btn = e.target.closest(".add-to-cart");
  if (btn){
    const id = Number(btn.getAttribute("data-id"));
    if (id > 0){
      await cartApiAdd(id, 1);
      await renderCart();
    }
    return;
  }

  // 2) Fallback for item detail page (id may be #btn-add-item)
  const btn2 = e.target.closest("#btn-add-item");
  if (btn2){
    const id = Number(btn2.getAttribute("data-id"));
    const qty = Number(btn2.getAttribute("data-qty") || 1);
    if (id > 0){
      await cartApiAdd(id, Math.max(1, qty));
      await renderCart();
    }
    return;
  }
});

/* ===========================
 * Boot
 * =========================== */
function highlightActiveNav(){
  try{
    const here = window.location.pathname.replace(/\/$/, "");
    document.querySelectorAll("header.bar nav a[href]").forEach(a=>{
      const href = a.getAttribute("href").replace(/\/$/, "");
      if (href && (here===href || (href!=="/" && here.startsWith(href)))) {
        a.style.textDecoration = "underline";
      }
    });
  }catch{}
}

document.addEventListener("DOMContentLoaded", async ()=>{
  bindAuthModal();
  highlightActiveNav();
  await refreshHeaderAuth();
  await renderCart(); // server session is the single source of truth
});
