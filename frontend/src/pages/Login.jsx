import React, { useState } from "react";
import { Navigate } from "react-router-dom";
import { Eye, EyeOff, User, Lock, Globe, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../context/AuthContext";
import { useI18n } from "../context/I18nContext";
import { BrandMark, BrandWordmark } from "../components/BrandMark";

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
            <BrandMark size={72} glow className="mb-4" />
            <span className="font-mono-tactical text-[10px] uppercase tracking-[0.28em] text-zinc-500">
              {t.brand.company}
            </span>
            <h1 className="text-3xl sm:text-4xl mt-1">
              <BrandWordmark className="text-white" />
            </h1>
            <p className="text-xs text-zinc-500 mt-2 font-mono-tactical tracking-wider uppercase">
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
