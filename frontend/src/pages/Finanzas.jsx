import React, { useEffect, useState } from "react";
import { TrendingUp, DollarSign, Wallet, PieChart } from "lucide-react";
import { toast } from "sonner";
import { api, formatApiError } from "../lib/api";
import { useI18n } from "../context/I18nContext";
import { fmtMoney } from "../lib/format";
import { PageHeader } from "../components/ui-kit";

function StatCard({ icon: Icon, label, value, sub, tone = "gold" }) {
  const toneMap = {
    gold: "text-[#dc2626] border-[#dc262640] bg-[#dc262614]",
    green: "text-emerald-300 border-emerald-800/50 bg-emerald-950/30",
    amber: "text-amber-300 border-amber-800/50 bg-amber-950/30",
    blue: "text-blue-300 border-blue-800/50 bg-blue-950/30",
  };
  return (
    <div className="card-tactical p-5">
      <div className={`inline-flex items-center gap-2 px-2.5 py-1 rounded border text-[9px] uppercase font-mono-tactical tracking-widest ${toneMap[tone]}`}>
        <Icon size={12} />{label}
      </div>
      <div className="mt-3 font-mono-tactical text-2xl sm:text-3xl font-bold text-white">{value}</div>
      {sub && <div className="text-xs text-zinc-500 mt-1">{sub}</div>}
    </div>
  );
}

export default function Finanzas() {
  const { t } = useI18n();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try { const { data } = await api.get("/finance/summary"); setData(data); }
      catch (e) { toast.error(formatApiError(e)); }
      finally { setLoading(false); }
    })();
  }, []);

  return (
    <div className="space-y-5" data-testid="finanzas-page">
      <PageHeader title={t.finanzas.title} subtitle={t.finanzas.subtitle} />
      {loading ? <div className="card-tactical p-10 flex justify-center"><span className="spinner spinner-gold" /></div>
        : !data ? <div className="card-tactical p-8 text-center text-sm text-zinc-500">Sin datos</div>
        : <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <StatCard icon={TrendingUp} label={t.finanzas.revenue} value={fmtMoney(data.revenue)} sub="Servicios terminados/entregados" />
            <StatCard icon={DollarSign} label={t.finanzas.profit} value={fmtMoney(data.profit)} sub={`${t.finanzas.margin}: ${data.margin_pct}%`} tone="green" />
            <StatCard icon={Wallet} label={t.finanzas.collected} value={fmtMoney(data.collected)} tone="blue" />
            <StatCard icon={PieChart} label={t.finanzas.receivable} value={fmtMoney(data.receivable)} tone="amber" />
          </div>
          <div className="card-tactical p-5">
            <h2 className="font-display uppercase tracking-wider text-lg text-white mb-4">{t.finanzas.by_status}</h2>
            <div className="space-y-2">
              {Object.entries(data.services_by_status || {}).length === 0 ? (
                <p className="text-sm text-zinc-500">Sin servicios registrados.</p>
              ) : (
                Object.entries(data.services_by_status).map(([st, count]) => {
                  const label = t.servicios.statuses[st] || st;
                  const max = Math.max(...Object.values(data.services_by_status));
                  const pct = max > 0 ? (count / max) * 100 : 0;
                  return (
                    <div key={st}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-zinc-400 font-mono-tactical uppercase tracking-widest text-[10px]">{label}</span>
                        <span className="text-white font-mono-tactical">{count}</span>
                      </div>
                      <div className="w-full h-2 bg-[#0d0d0d] rounded-full overflow-hidden">
                        <div className="h-full bg-[#dc2626]" style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </>
      }
    </div>
  );
}
