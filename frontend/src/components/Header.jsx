import React from "react";
import { LogOut, Globe } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useI18n } from "../context/I18nContext";
import { toast } from "sonner";
import { BrandMark } from "./BrandMark";

export function Header() {
  const { user, logout } = useAuth();
  const { t, locale, toggle } = useI18n();

  const initials = (user?.name || user?.username || "A")
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  const roleLabel = t.header.role[user?.role] || user?.role || "";

  const onLogout = async () => {
    await logout();
    toast.success(t.toast.logout_ok);
  };

  return (
    <header
      className="sticky top-0 z-40 w-full border-b border-[#1f1f1f] bg-[#070707]/85 backdrop-blur-md"
      data-testid="app-header"
    >
      <div className="max-w-7xl mx-auto flex items-center justify-between px-4 sm:px-6 h-16">
        <div className="flex items-center gap-3">
          <BrandMark size={40} />
          <div className="flex flex-col leading-tight">
            <span className="font-display uppercase text-[13px] sm:text-[14px] tracking-wider text-white leading-tight">
              Armenta's Motors <span className="text-[#dc2626]">Company</span>
            </span>
            <span className="hidden sm:inline text-[10px] font-mono-tactical uppercase tracking-widest text-zinc-500">
              {t.brand.company}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          <div
            className="hidden sm:flex items-center gap-2 px-3 h-9 rounded-full border border-emerald-800/50 bg-emerald-950/40"
            data-testid="header-session-active-indicator"
          >
            <span className="pulse-dot" />
            <span className="text-[10px] tracking-widest font-mono-tactical text-emerald-300 uppercase">
              {t.header.session_active}
            </span>
          </div>

          <button
            type="button"
            onClick={toggle}
            className="armenta-btn-ghost flex items-center gap-2 !h-9 !px-3"
            data-testid="header-language-toggle"
            aria-label="Toggle language"
          >
            <Globe size={14} />
            <span className="font-mono-tactical text-[11px]">{locale.toUpperCase()}</span>
          </button>

          <div
            className="hidden md:flex items-center gap-2 px-3 h-9 rounded-md border border-[#262626] bg-[#0d0d0d]"
            data-testid="header-user-badge"
          >
            <div className="w-6 h-6 rounded-full bg-[#dc2626] text-white text-[11px] font-bold flex items-center justify-center font-display">
              {initials}
            </div>
            <div className="flex flex-col leading-tight">
              <span className="text-xs text-white font-medium">{user?.name}</span>
              <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-mono-tactical">
                {roleLabel}
              </span>
            </div>
          </div>

          <button
            type="button"
            onClick={onLogout}
            className="armenta-btn-ghost flex items-center gap-2 !h-9 !px-3"
            data-testid="header-logout-button"
          >
            <LogOut size={14} />
            <span className="hidden sm:inline">{t.header.logout}</span>
          </button>
        </div>
      </div>
    </header>
  );
}
