import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { api, formatApiError } from "../lib/api";
import { storage, STORAGE_KEYS } from "../lib/storage";

const AuthContext = createContext(null);

/**
 * AuthContext states:
 *  - status: 'initializing' | 'authenticated' | 'anonymous'
 *  - session: { token, user, session_started_at } | null
 */
export function AuthProvider({ children }) {
  const [status, setStatus] = useState("initializing");
  const [session, setSession] = useState(null);

  // Rehydrate from localStorage on mount, then verify with /auth/me.
  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      const stored = storage.get(STORAGE_KEYS.session);
      if (!stored?.token) {
        if (!cancelled) {
          setStatus("anonymous");
        }
        return;
      }
      try {
        const { data } = await api.get("/auth/me");
        if (cancelled) return;
        const refreshed = { ...stored, user: data };
        storage.set(STORAGE_KEYS.session, refreshed);
        setSession(refreshed);
        setStatus("authenticated");
      } catch (e) {
        if (cancelled) return;
        storage.remove(STORAGE_KEYS.session);
        setSession(null);
        setStatus("anonymous");
      }
    }
    bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (identifier, password) => {
    try {
      const { data } = await api.post("/auth/login", {
        identifier: identifier.trim(),
        password,
      });
      const sess = {
        token: data.token,
        user: data.user,
        session_started_at: data.session_started_at,
      };
      storage.set(STORAGE_KEYS.session, sess);
      setSession(sess);
      setStatus("authenticated");
      return { ok: true };
    } catch (e) {
      return { ok: false, error: formatApiError(e) };
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } catch (e) {
      // ignore — stateless JWT, we just drop it
    }
    storage.remove(STORAGE_KEYS.session);
    setSession(null);
    setStatus("anonymous");
  }, []);

  const value = useMemo(
    () => ({
      status,
      session,
      user: session?.user || null,
      isAuthenticated: status === "authenticated",
      isInitializing: status === "initializing",
      login,
      logout,
    }),
    [status, session, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
