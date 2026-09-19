import React, { useEffect, useState } from "react";
import {
  Wrench,
  FileText,
  DollarSign,
  ShieldCheck,
  PlusCircle,
  Car,
  Clock,
} from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../context/AuthContext";
import { useI18n } from "../context/I18nContext";
import { api } from "../lib/api";

function KpiCard({ testId, icon: Icon, title, value, subtitle, badge, tone = "gold" }) {
  const toneStyle =
    tone === "green"
      ? "text-emerald-400 border-emerald-800/50 bg-emerald-950/30"
      : tone === "amber"
        ? "text-amber-300 border-amber-800/50 bg-amber-950/30"
        : "text-[#dc2626] border-[#dc262640] bg-[#dc262614]";

  return (
    <div className="card-tactical p-4 sm:p-5" data-testid={testId}>
      <div className="flex items-start justify-between mb-3">
        <div className="w-10 h-10 rounded-lg bg-[#0d0d0d] border border-[#262626] flex items-center justify-center">
          <Icon size={18} className="text-[#dc2626]" />
        </div>
        <span
          className={`text-[9px] font-mono-tactical uppercase tracking-widest px-2 py-1 rounded border ${toneStyle}`}
        >
          {badge}
        </span>
      </div>
      <div className="font-mono-tactical text-2xl sm:text-3xl font-bold text-white tracking-tight">
        {value}
      </div>
      <div className="mt-1 text-sm font-medium text-white">{title}</div>
      <div className="text-xs text-zinc-500 mt-0.5">{subtitle}</div>
    </div>
  );
}

function QuickAction({ testId, icon: Icon, label, soonLabel, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testId}
      className="card-tactical p-4 flex items-center gap-3 text-left w-full hover:border-[#dc262666]"
    >
      <div className="w-10 h-10 rounded-lg bg-[#0d0d0d] border border-[#262626] flex items-center justify-center">
        <Icon size={18} className="text-[#dc2626]" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-white truncate">{label}</div>
        <div className="text-[10px] uppercase tracking-widest font-mono-tactical text-zinc-500">
          {soonLabel}
        </div>
      </div>
      <PlusCircle size={16} className="text-zinc-600" />
    </button>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api
      .get("/dashboard/summary")
      .then((r) => {
        if (!cancelled) setSummary(r.data);
      })
      .catch(() => {
        if (!cancelled) setSummary(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const notifySoon = () => toast(t.toast.soon);

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      {/* Title */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="font-mono-tactical text-[11px] uppercase tracking-widest text-zinc-500 mb-1">
            {t.dashboard.subtitle}
          </div>
          <h1 className="font-display uppercase text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
            {t.dashboard.title}
          </h1>
          <p className="text-sm text-zinc-400 mt-2" data-testid="dashboard-welcome">
            {user?.name
              ? t.dashboard.welcome(user.name)
              : t.dashboard.welcome_generic}
          </p>
        </div>

        <div className="flex items-center gap-2 px-3 h-9 rounded-full border border-emerald-800/50 bg-emerald-950/40">
          <span className="pulse-dot" />
          <span className="text-[10px] tracking-widest font-mono-tactical text-emerald-300 uppercase">
            {t.header.session_active}
          </span>
        </div>
      </div>

      {/* KPI grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <KpiCard
          testId="kpi-card-servicios-hoy"
          icon={Wrench}
          title={t.dashboard.kpi.services_today}
          subtitle={t.dashboard.kpi.services_today_sub}
          value={summary?.services_today ?? 0}
          badge="HOY"
        />
        <KpiCard
          testId="kpi-card-cotizaciones"
          icon={FileText}
          title={t.dashboard.kpi.quotes}
          subtitle={t.dashboard.kpi.quotes_sub}
          value={summary?.quotes_pending ?? 0}
          badge="PENDIENTE"
          tone="amber"
        />
        <KpiCard
          testId="kpi-card-por-cobrar"
          icon={DollarSign}
          title={t.dashboard.kpi.receivable}
          subtitle={t.dashboard.kpi.receivable_sub}
          value={`$${(summary?.receivable_total_mxn ?? 0).toLocaleString("es-MX")} MXN`}
          badge="FINANZAS"
        />
        <KpiCard
          testId="kpi-card-estado-sistema"
          icon={ShieldCheck}
          title={t.dashboard.kpi.status}
          subtitle={t.dashboard.kpi.status_sub}
          value={t.dashboard.kpi.status_value}
          badge="ONLINE"
          tone="green"
        />
      </div>

      {/* Body */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <section className="lg:col-span-2 card-tactical p-5" data-testid="quick-actions-panel">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-display uppercase text-lg tracking-wider text-white">
              {t.dashboard.quick_actions.title}
            </h2>
            <span className="text-[10px] uppercase font-mono-tactical tracking-widest text-zinc-500">
              {t.dashboard.quick_actions.soon}
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <QuickAction
              testId="action-btn-nuevo-servicio"
              icon={Wrench}
              label={t.dashboard.quick_actions.new_service}
              soonLabel={t.dashboard.quick_actions.soon}
              onClick={notifySoon}
            />
            <QuickAction
              testId="action-btn-nuevo-vehiculo"
              icon={Car}
              label={t.dashboard.quick_actions.new_vehicle}
              soonLabel={t.dashboard.quick_actions.soon}
              onClick={notifySoon}
            />
            <QuickAction
              testId="action-btn-nueva-cotizacion"
              icon={FileText}
              label={t.dashboard.quick_actions.new_quote}
              soonLabel={t.dashboard.quick_actions.soon}
              onClick={notifySoon}
            />
          </div>
        </section>

        <section className="card-tactical p-5" data-testid="recent-activity-panel">
          <div className="flex items-center gap-2 mb-3">
            <Clock size={16} className="text-[#dc2626]" />
            <h2 className="font-display uppercase text-lg tracking-wider text-white">
              {t.dashboard.activity.title}
            </h2>
          </div>
          <p className="text-sm text-zinc-500 leading-relaxed">
            {t.dashboard.activity.empty}
          </p>
        </section>
      </div>
    </div>
  );
}
