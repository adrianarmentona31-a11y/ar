import React, { useCallback, useEffect, useState } from "react";
import { Star, MessageSquareHeart, Copy, Trash2, Send } from "lucide-react";
import { toast } from "sonner";
import { api, formatApiError } from "../lib/api";
import { useI18n } from "../context/I18nContext";
import { fmtDate } from "../lib/format";
import { PageHeader, StatusBadge } from "../components/ui-kit";
import { whatsappSurveyUrl } from "../lib/surveyLink";

function Kpi({ label, value, sub, testId }) {
  return (
    <div className="card-tactical p-4" data-testid={testId}>
      <div className="font-mono-tactical text-[10px] uppercase tracking-widest text-zinc-500">{label}</div>
      <div className="text-2xl font-bold text-white font-mono-tactical mt-1">{value}</div>
      {sub && <div className="text-[10px] text-zinc-600 mt-0.5">{sub}</div>}
    </div>
  );
}

function StarRow({ n }) {
  return <span className="inline-flex gap-0.5">{[1, 2, 3, 4, 5].map((i) => <Star key={i} size={13} className={i <= n ? "text-[#dc2626] fill-[#dc2626]" : "text-zinc-700"} />)}</span>;
}

export default function Encuestas() {
  const { t } = useI18n();
  const [items, setItems] = useState([]);
  const [stats, setStats] = useState(null);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const tr = t.encuestas;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/surveys", { params: filter === "all" ? {} : { status: filter } });
      setItems(data.items || []); setStats(data.stats);
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setLoading(false); }
  }, [filter]);
  useEffect(() => { load(); }, [load]);

  const url = (s) => `${window.location.origin}/encuesta/${s.token}`;
  const copy = async (s) => { await navigator.clipboard.writeText(url(s)); toast.success(tr.copied); };
  const remove = async (s) => {
    if (!window.confirm(t.common.delete_confirm)) return;
    try { await api.delete(`/surveys/${s.id}`); toast.success(tr.deleted); load(); } catch (e) { toast.error(formatApiError(e)); }
  };

  return (
    <div className="space-y-5" data-testid="encuestas-page">
      <PageHeader title={tr.title} subtitle={tr.subtitle} />
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Kpi testId="kpi-sent" label={tr.sent} value={stats.sent} sub={`${stats.answered} ${tr.answered_lower}`} />
          <Kpi testId="kpi-rate" label={tr.response_rate} value={`${stats.response_rate}%`} />
          <Kpi testId="kpi-rating" label={tr.avg_rating} value={stats.avg_rating ?? "—"} sub="/ 5" />
          <Kpi testId="kpi-nps" label="NPS" value={stats.nps ?? "—"} sub={`${stats.promoters} ${tr.promoters} · ${stats.detractors} ${tr.detractors}`} />
        </div>
      )}
      <div className="card-tactical p-3 flex gap-2 overflow-x-auto">
        {["all", "pending", "answered"].map((s) => (
          <button key={s} onClick={() => setFilter(s)} data-testid={`encuestas-filter-${s}`}
            className={`h-10 px-3 rounded-lg border text-[10px] uppercase font-mono-tactical tracking-widest whitespace-nowrap ${filter === s ? "border-[#dc2626] bg-[#dc262614] text-white" : "border-[#262626] bg-[#0d0d0d] text-zinc-500 hover:text-white"}`}>
            {tr.filters[s]}
          </button>
        ))}
      </div>
      {loading ? <div className="card-tactical p-10 flex justify-center"><span className="spinner spinner-gold" /></div>
        : items.length === 0 ? <div className="card-tactical p-8 text-center"><MessageSquareHeart size={28} className="text-[#dc2626] mx-auto mb-3" /><p className="text-sm text-zinc-400">{tr.empty}</p></div>
        : <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {items.map((s) => (
              <div key={s.id} className="card-tactical p-4 space-y-3" data-testid={`survey-card-${s.id}`}>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="font-mono-tactical text-[10px] uppercase tracking-widest text-[#dc2626]">{s.folio}</div>
                    <div className="text-white font-semibold truncate">{s.client_name || "—"}</div>
                    <div className="text-xs text-zinc-500 truncate">{s.vehicle}</div>
                  </div>
                  <StatusBadge label={tr.filters[s.status]} tone={s.status === "answered" ? "green" : "amber"} />
                </div>
                {s.status === "answered" ? (
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between"><StarRow n={s.rating} /><span className="font-mono-tactical text-xs text-zinc-400">NPS {s.nps}/10</span></div>
                    {s.aspects?.length > 0 && <div className="flex flex-wrap gap-1">{s.aspects.map((a) => <span key={a} className="text-[9px] uppercase tracking-widest font-mono-tactical px-2 py-0.5 rounded-full border border-[#262626] text-zinc-400">{a}</span>)}</div>}
                    {s.comments && <p className="text-sm text-zinc-300 italic" data-testid={`survey-comment-${s.id}`}>“{s.comments}”</p>}
                    <div className="text-[10px] text-zinc-600">{fmtDate(s.answered_at)}</div>
                  </div>
                ) : (
                  <div className="flex gap-2">
                    <button onClick={() => copy(s)} className="armenta-btn-ghost !h-9 !px-3 flex items-center gap-1.5 text-xs" data-testid={`survey-copy-${s.id}`}><Copy size={12} />{tr.copy}</button>
                    <a href={whatsappSurveyUrl(s, url(s))} target="_blank" rel="noreferrer" className="h-9 px-3 rounded-lg border border-emerald-800/60 bg-emerald-950/30 text-emerald-300 flex items-center gap-1.5 text-xs" data-testid={`survey-wa-${s.id}`}><Send size={12} />WhatsApp</a>
                    <button onClick={() => remove(s)} className="ml-auto text-zinc-600 hover:text-red-400" data-testid={`survey-rm-${s.id}`}><Trash2 size={14} /></button>
                  </div>
                )}
              </div>
            ))}
          </div>}
    </div>
  );
}
