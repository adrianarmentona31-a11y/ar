import axios from "axios";
import { storage, STORAGE_KEYS } from "./storage";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
  withCredentials: true, // include cookies for Emergent Google session
});

// Attach bearer token when we have a session (custom JWT flow).
// Cookie-based Google session works automatically via withCredentials.
api.interceptors.request.use((config) => {
  const session = storage.get(STORAGE_KEYS.session);
  if (session?.token) {
    config.headers.Authorization = `Bearer ${session.token}`;
  }
  return config;
});

// Normalize error payloads from FastAPI (detail can be str | array of msg objs)
export function formatApiError(err) {
  const detail = err?.response?.data?.detail;
  if (detail == null) return err?.message || "Ocurrió un error inesperado.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
      .filter(Boolean)
      .join(" ");
  }
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}
