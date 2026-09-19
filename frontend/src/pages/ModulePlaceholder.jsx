import React from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Construction } from "lucide-react";
import { useI18n } from "../context/I18nContext";

export default function ModulePlaceholder({ moduleKeyOverride }) {
  const moduleKey = moduleKeyOverride;
  const { t } = useI18n();
  const navigate = useNavigate();
  const label = (moduleKey && t.nav[moduleKey]) || moduleKey || "";

  return (
    <div className="space-y-6" data-testid="module-placeholder-page">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="font-mono-tactical text-[11px] uppercase tracking-widest text-zinc-500 mb-1">
            ARMENTA OS
          </div>
          <h1 className="font-display uppercase text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
            {label}
          </h1>
        </div>
        <span
          className="inline-flex items-center gap-2 px-3 h-9 rounded-full border border-[#dc262666] bg-[#dc262614] text-[10px] font-mono-tactical uppercase tracking-widest text-[#dc2626]"
          data-testid="module-proximamente-banner"
        >
          <Construction size={12} />
          {t.placeholder.badge}
        </span>
      </div>

      <div className="card-tactical p-6 max-w-2xl">
        <p className="text-sm text-zinc-400 leading-relaxed">
          {t.placeholder.description}
        </p>
        <button
          type="button"
          onClick={() => navigate("/control")}
          className="armenta-btn-ghost flex items-center gap-2 mt-5"
          data-testid="module-back-to-control"
        >
          <ArrowLeft size={14} />
          {t.placeholder.back}
        </button>
      </div>
    </div>
  );
}
