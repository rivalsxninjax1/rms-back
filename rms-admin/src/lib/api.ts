import axios from "axios";

function getCookie(name: string) {
  const m = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
  return m ? m.pop() : "";
}

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
  withCredentials: true,
  xsrfCookieName: "csrftoken",
  xsrfHeaderName: "X-CSRFToken",
});

// Attach CSRF for unsafe methods (if readable) and Bearer token if present
api.interceptors.request.use((cfg) => {
  const method = (cfg.method || "").toLowerCase();
  if (["post","put","patch","delete"].includes(method)) {
    const token = getCookie("csrftoken");
    if (token) {
      cfg.headers.set("X-CSRFToken", token);
    }
  }

  // Attach Authorization from stored access token
  try {
    const access = localStorage.getItem("accessToken");
    if (access && !cfg.headers.get("Authorization")) {
      cfg.headers.set("Authorization", `Bearer ${access}`);
    }
  } catch {}
  return cfg;
});

// On 401, try one-time refresh using stored refresh token
let isRefreshing = false;
let pendingQueue: Array<{ resolve: (v?: any) => void; reject: (e?: any) => void }> = [];

function processQueue(error: any, token: string | null) {
  pendingQueue.forEach((p) => {
    if (error) p.reject(error);
    else p.resolve(token);
  });
  pendingQueue = [];
}

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error?.config;
    const status = error?.response?.status;
    if (status !== 401 || !original || original.__retry) {
      return Promise.reject(error);
    }

    if (isRefreshing) {
      // Queue requests while a refresh is in-flight
      return new Promise((resolve, reject) => {
        pendingQueue.push({ resolve, reject });
      })
        .then((token) => {
          if (token) {
            original.headers = original.headers || {};
            original.headers["Authorization"] = `Bearer ${token}`;
          }
          original.__retry = true;
          return api.request(original);
        })
        .catch((err) => Promise.reject(err));
    }

    isRefreshing = true;
    try {
      const refresh = localStorage.getItem("refreshToken");
      if (!refresh) throw error;

      // Use a bare axios instance to avoid interceptor recursion
      const { data } = await axios.post(
        (import.meta.env.VITE_API_URL || "") + "/accounts/api/token/refresh/",
        { refresh },
        { withCredentials: true }
      );
      const newAccess = data?.access;
      if (!newAccess) throw error;

      // Persist and update default header
      try { localStorage.setItem("accessToken", newAccess); } catch {}
      api.defaults.headers.common["Authorization"] = `Bearer ${newAccess}`;

      processQueue(null, newAccess);

      // Retry the original request
      original.headers = original.headers || {};
      original.headers["Authorization"] = `Bearer ${newAccess}`;
      original.__retry = true;
      return api.request(original);
    } catch (e) {
      processQueue(e as any, null);
      // Clear tokens on hard failure
      try {
        localStorage.removeItem("accessToken");
        localStorage.removeItem("refreshToken");
      } catch {}
      return Promise.reject(e);
    } finally {
      isRefreshing = false;
    }
  }
);

export default api;
