import React, { useState } from "react";
import { Navigate } from "react-router-dom";
import { Eye, EyeOff, User, Lock, Globe, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../context/AuthContext";
import { useI18n } from "../context/I18nContext";
import { ArmentaWordmark } from "../components/ArmentaWordmark";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
function startGoogleSignIn() {
  const redirectUrl = window.location.origin + "/control";
  window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
}

export default function Login() {
  const { login, isAuthenticated, isInitializing } = useAuth();
  const { t, locale, toggle } = useI18n();

  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  if (isInitializing) {
    return (
      <div className="min-h-screen bg-obsidian-mesh flex items-center justify-center">
        <div className="spinner spinner-gold" />
      </div>
    );
  }
  if (isAuthenticated) {
    return <Navigate to="/control" replace />;
  }

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (!identifier.trim() || !password) {
      setError(t.login.errors.empty);
      return;
    }
    setSubmitting(true);
    const res = await login(identifier, password);
    setSubmitting(false);
    if (!res.ok) {
      setError(res.error || t.login.errors.invalid);
      return;
    }
    toast.success(t.toast.login_ok);
  };

  return (
    <div className="min-h-screen bg-obsidian-mesh flex flex-col">
      <div className="flex-1 flex items-center justify-center px-4 py-8 relative">
        <button
          type="button"
          onClick={toggle}
          className="absolute top-4 right-4 armenta-btn-ghost flex items-center gap-2 !h-9 !px-3"
          data-testid="login-language-toggle"
          aria-label="Toggle language"
        >
          <Globe size={14} />
          <span className="font-mono-tactical text-[11px]">{locale.toUpperCase()}</span>
        </button>

        <div className="w-full max-w-md">
          <div className="flex flex-col items-center mb-8">
            <ArmentaWordmark width={380} className="mb-1 -mt-4" />
            <div className="brand-ribbon" data-testid="login-ribbon">Servicio a domicilio</div>
            <p className="text-xs text-zinc-500 mt-3 font-mono-tactical tracking-[0.28em] uppercase">
              {t.brand.tagline}
            </p>
          </div>

          <div className="card-tactical p-6 sm:p-7" data-testid="login-card">
            <div className="mb-5">
              <h2 className="text-lg font-semibold text-white">{t.login.title}</h2>
              <p className="text-sm text-zinc-500 mt-1">{t.login.subtitle}</p>
            </div>

            <form
              onSubmit={onSubmit}
              className="space-y-4"
              data-testid="login-form"
              noValidate
            >
              <div>
                <label className="block text-[11px] uppercase tracking-widest font-mono-tactical text-zinc-500 mb-1.5">
                  {t.login.username}
                </label>
                <div className="relative">
                  <User
                    size={16}
                    className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-500"
                  />
                  <input
                    type="text"
                    inputMode="text"
                    autoComplete="username"
                    className="armenta-input"
                    placeholder={t.login.username_placeholder}
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                    disabled={submitting}
                    data-testid="login-username-input"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] uppercase tracking-widest font-mono-tactical text-zinc-500 mb-1.5">
                  {t.login.password}
                </label>
                <div className="relative">
                  <Lock
                    size={16}
                    className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-500"
                  />
                  <input
                    type={showPwd ? "text" : "password"}
                    autoComplete="current-password"
                    className="armenta-input"
                    placeholder={t.login.password_placeholder}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={submitting}
                    data-testid="login-password-input"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPwd((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-white transition-colors p-1"
                    aria-label={showPwd ? t.login.hide : t.login.show}
                    data-testid="login-toggle-password-visibility"
                  >
                    {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              {error && (
                <div
                  className="rounded-lg border border-red-800/70 bg-red-950/40 px-3.5 py-2.5 text-sm text-red-200"
                  role="alert"
                  data-testid="login-error-alert"
                >
                  {error}
                </div>
              )}

              <button
                type="submit"
                className="armenta-btn-primary flex items-center justify-center gap-2"
                disabled={submitting}
                data-testid="login-submit-button"
              >
                {submitting ? (
                  <>
                    <span className="spinner" data-testid="login-loading-spinner" />
                    <span>{t.login.submitting}</span>
                  </>
                ) : (
                  <span>{t.login.submit}</span>
                )}
              </button>

              {/* Google Sign-In (Emergent managed) */}
              <div className="relative py-1">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-[#1f1f1f]" />
                </div>
                <div className="relative flex justify-center text-[10px] uppercase tracking-widest font-mono-tactical text-zinc-600">
                  <span className="bg-[#101010] px-3">{t.login.or}</span>
                </div>
              </div>

              <button
                type="button"
                onClick={startGoogleSignIn}
                disabled={submitting}
                className="w-full h-12 rounded-lg border border-[#262626] bg-[#0d0d0d] hover:bg-[#141414] hover:border-[#3a3a3a] text-white flex items-center justify-center gap-3 transition-colors font-medium text-sm"
                data-testid="login-google-button"
              >
                <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
                  <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.3l6.7-6.7C35.6 2.4 30.2 0 24 0 14.7 0 6.7 5.3 2.8 13l7.9 6.1C12.6 12.9 17.8 9.5 24 9.5z" />
                  <path fill="#4285F4" d="M46.5 24.6c0-1.6-.1-3.1-.4-4.6H24v9.3h12.7c-.6 3-2.3 5.6-4.8 7.3l7.4 5.8c4.4-4 6.9-9.9 6.9-17.8z" />
                  <path fill="#FBBC05" d="M10.7 28.6c-.5-1.5-.8-3-.8-4.6s.3-3.1.8-4.6l-7.9-6.1C1.1 16.8 0 20.3 0 24s1.1 7.2 2.8 10.7l7.9-6.1z" />
                  <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.4-5.8c-2.1 1.4-4.8 2.2-8.5 2.2-6.2 0-11.4-3.4-13.3-8.6l-7.9 6.1C6.7 42.7 14.7 48 24 48z" />
                </svg>
                {t.login.google}
              </button>
            </form>

            <div className="mt-6 pt-4 border-t border-[#1a1a1a] flex items-center gap-2 text-[11px] font-mono-tactical uppercase tracking-widest text-zinc-500">
              <ShieldCheck size={13} className="text-[#dc2626]" />
              <span>{t.login.footer}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
