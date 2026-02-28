import axios, { AxiosError } from "axios";

// In dev, Vite proxies /api → localhost:8000.
// In production, FastAPI serves both API and frontend on the same origin.
const BASE_URL = import.meta.env.VITE_API_URL ?? "";

export const api = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
  timeout: 15_000,
});

// Attach the JWT on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Global 401 handler — clear token and redirect to login
api.interceptors.response.use(
  (r) => r,
  (err: AxiosError) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("access_token");
      // Only redirect if we're not already on the auth page
      if (!window.location.pathname.startsWith("/auth")) {
        window.location.href = "/auth";
      }
    }
    return Promise.reject(err);
  }
);

/** Extract a human-readable error message from an Axios error. */
export function apiErrorMessage(err: unknown): string {
  if (err instanceof AxiosError) {
    const data = err.response?.data;
    if (typeof data?.detail === "string") return data.detail;
    if (typeof data?.message === "string") return data.message;
    if (err.message) return err.message;
  }
  return "An unexpected error occurred.";
}

/** Build a WebSocket URL, swapping the HTTP scheme and appending the JWT. */
export function wsUrl(path: string): string {
  const token = localStorage.getItem("access_token") ?? "";
  const base = import.meta.env.VITE_API_URL ?? window.location.origin;
  const ws = base.replace(/^http/, "ws");
  const sep = path.includes("?") ? "&" : "?";
  return `${ws}/api/v1${path}${sep}token=${encodeURIComponent(token)}`;
}
