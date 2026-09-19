// Thin storage layer. In Fase 1 backed by localStorage but the interface is
// intentionally decoupled so it can be swapped for a secure API-backed store
// later (e.g., httpOnly cookies + refresh tokens) without touching UI.

const NAMESPACE = "armenta_os_";

export const storage = {
  get(key) {
    try {
      const raw = window.localStorage.getItem(NAMESPACE + key);
      if (raw == null) return null;
      return JSON.parse(raw);
    } catch (e) {
      console.warn("[storage.get] failed for", key, e);
      return null;
    }
  },
  set(key, value) {
    try {
      window.localStorage.setItem(NAMESPACE + key, JSON.stringify(value));
      return true;
    } catch (e) {
      console.warn("[storage.set] failed for", key, e);
      return false;
    }
  },
  remove(key) {
    try {
      window.localStorage.removeItem(NAMESPACE + key);
      return true;
    } catch (e) {
      return false;
    }
  },
};

export const STORAGE_KEYS = {
  session: "session_v1",
  locale: "locale_v1",
};
