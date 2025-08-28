/* storefront/static/storefront/auth-modal.js - Fixed Session Auth */
(function () {
  const $ = (sel, el=document) => el.querySelector(sel);
  const modal = $("#auth-modal");
  const stepChoice = $("#auth-step-choice");
  const stepLogin = $("#auth-step-login");
  const stepSignup = $("#auth-step-signup");
  const btnOpenLogin = $("#btn-open-login");
  const btnOpenSignup = $("#btn-open-signup");
  const linkToLogin = $("#link-to-login");
  const linkToSignup = $("#link-to-signup");
  const btnClose = $("#auth-close");
  const loginForm = $("#modal-login-form");
  const signupForm = $("#modal-signup-form");
  const loginStatus = $("#modal-login-status");
  const signupStatus = $("#modal-signup-status");

  function show(which){ 
    stepChoice.classList.toggle("hidden", which!=="choice"); 
    stepLogin.classList.toggle("hidden", which!=="login"); 
    stepSignup.classList.toggle("hidden", which!=="signup"); 
  }
  
  function openModal(which="choice"){ 
    modal.classList.remove("hidden"); 
    show(which); 
  }
  
  function closeModal(){ 
    modal.classList.add("hidden"); 
    // Clear any status messages
    if (loginStatus) loginStatus.textContent = "";
    if (signupStatus) signupStatus.textContent = "";
  }

  // Event listeners
  btnOpenLogin?.addEventListener("click", () => show("login"));
  btnOpenSignup?.addEventListener("click", () => show("signup"));
  linkToLogin?.addEventListener("click", (e) => { e.preventDefault(); show("login"); });
  linkToSignup?.addEventListener("click", (e) => { e.preventDefault(); show("signup"); });
  btnClose?.addEventListener("click", closeModal);

  function setBusy(el, busy){ 
    if(!el) return; 
    el.disabled = !!busy; 
    el.classList.toggle("is-busy", !!busy); 
  }

  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return "";
  }

  // Session-based login (no JWT)
  async function sessionLogin(username, password){
    const csrftoken = getCookie('csrftoken');
    const res = await fetch("/accounts/login/", { 
      method: "POST", 
      headers: { 
        "Content-Type": "application/json",
        "X-CSRFToken": csrftoken
      }, 
      credentials: "include", 
      body: JSON.stringify({ username, password }) 
    });
    
    const data = await res.json().catch(()=>({}));
    if(!res.ok) throw new Error(data.detail || "Login failed");
    
    return data;
  }

  // Session-based registration
  async function sessionRegister(userData){
    const csrftoken = getCookie('csrftoken');
    const res = await fetch("/accounts/register/", { 
      method: "POST", 
      headers: { 
        "Content-Type": "application/json",
        "X-CSRFToken": csrftoken
      }, 
      credentials: "include", 
      body: JSON.stringify(userData) 
    });
    
    const data = await res.json().catch(()=>({}));
    if(!res.ok) throw new Error(data.detail || data.username || data.email || "Registration failed");
    
    return data;
  }

  // Update navigation after successful auth
  function updateNavAfterAuth() {
    const navLogin = document.getElementById('nav-login');
    const navLogout = document.getElementById('nav-logout');
    const navOrders = document.getElementById('nav-orders');
    
    if (navLogin) navLogin.style.display = 'none';
    if (navLogout) navLogout.style.display = '';
    if (navOrders) navOrders.style.display = '';
    
    // Fire auth event for other parts of the app
    window.dispatchEvent(new CustomEvent('auth:login'));
  }

  // Login form handler
  loginForm?.addEventListener("submit", async (e) => {
    e.preventDefault(); 
    loginStatus.textContent = "Logging in…";
    setBusy(loginForm.querySelector("button[type=submit]"), true);
    
    const f = new FormData(loginForm);
    try { 
      await sessionLogin(f.get("username"), f.get("password")); 
      loginStatus.textContent = "Success!"; 
      updateNavAfterAuth();
      closeModal();
      
      // Continue with checkout if needed
      if (typeof window.__continueCheckoutAfterAuth === "function") {
        await window.__continueCheckoutAfterAuth();
      }
    } catch (err) { 
      loginStatus.textContent = (err && err.message) || "Login failed."; 
    } finally { 
      setBusy(loginForm.querySelector("button[type=submit]"), false); 
    }
  });

  // Signup form handler
  signupForm?.addEventListener("submit", async (e) => {
    e.preventDefault(); 
    signupStatus.textContent = "Creating account…";
    setBusy(signupForm.querySelector("button[type=submit]"), true);
    
    const f = new FormData(signupForm);
    const payload = { 
      username: f.get("username"), 
      email: f.get("email"), 
      first_name: f.get("first_name") || "", 
      last_name: f.get("last_name") || "", 
      password: f.get("password") 
    };
    
    try {
      await sessionRegister(payload);
      // Auto-login after successful registration
      await sessionLogin(payload.username, payload.password);
      signupStatus.textContent = "Account created!"; 
      updateNavAfterAuth();
      closeModal();
      
      // Continue with checkout if needed
      if (typeof window.__continueCheckoutAfterAuth === "function") {
        await window.__continueCheckoutAfterAuth();
      }
    } catch (err) { 
      signupStatus.textContent = (err && err.message) || "Registration failed."; 
    } finally { 
      setBusy(signupForm.querySelector("button[type=submit]"), false); 
    }
  });

  // Close modal on Escape key
  document.addEventListener("keydown", (e) => { 
    if(e.key === "Escape") closeModal(); 
  });
  
  // Make openModal available globally
  window.__openAuthModalForPay = () => openModal("choice");
  window.__openAuthModal = openModal;
})();
