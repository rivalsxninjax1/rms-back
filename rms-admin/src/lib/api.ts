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

api.interceptors.request.use((cfg) => {
  const method = (cfg.method || "").toLowerCase();
  if (["post","put","patch","delete"].includes(method)) {
    const token = getCookie("csrftoken");
    if (token) {
      cfg.headers.set("X-CSRFToken", token);
    }
  }
  return cfg;
});

export default api;
