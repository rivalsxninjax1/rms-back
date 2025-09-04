// storefront/static/storefront/utils.js
// Shared utility functions for all storefront JavaScript modules

(function() {
  'use strict';
  
  // Prevent multiple initialization
  if (window.__STOREFRONT_UTILS_LOADED__) return;
  window.__STOREFRONT_UTILS_LOADED__ = true;
  
  // DOM utilities
  window.$ = window.$ || ((sel, el = document) => el.querySelector(sel));
  window.$$ = window.$$ || ((sel, el = document) => Array.from(el.querySelectorAll(sel)));
  
  // Cookie utility
  window.getCookie = window.getCookie || function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return '';
  };

  // Robust CSRF token getter: prefer hidden input (works with HttpOnly cookies)
  window.csrfToken = window.csrfToken || function csrfToken() {
    try {
      const inp = document.querySelector('input[name="csrfmiddlewaretoken"]');
      if (inp && inp.value) return inp.value;
    } catch(_) { /* ignore */ }
    const c = window.getCookie('csrftoken');
    return c || '';
  };
  
  // Money formatting utility
  window.money = window.money || function money(n) {
    const num = Number(n || 0);
    return num.toFixed(2);
  };
  
  // JSON fetch utility with CSRF
  window.jsonFetch = window.jsonFetch || function jsonFetch(url, opts = {}) {
    const defaults = {
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': window.csrfToken(),
      },
      credentials: 'include',
    };
    return fetch(url, { ...defaults, ...opts });
  };
})();
