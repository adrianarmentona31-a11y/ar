import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Plus, FileText, Receipt as ReceiptIcon, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import { api, formatApiError } from "../lib/api";
import { useI18n } from "../context/I18nContext";
import { fmtDate, fmtMoney } from "../lib/format";
import { Modal, Field, Input, Textarea, Select, PageHeader, StatusBadge } from "../components/ui-kit";

const STATUS_TONE = {
  draft: "gray", sent: "blue", approved: "green",
  rejected: "red", expired: "amber",
};

function ItemsInline({ items, setItems, taxRate, setTaxRate }) {
  const { t } = useI18n();
  const update = (i, k, v) => {
    const next = [...items];
    next[i] = { ...next[i], [k]: k === "description" ? v : Number(v) || 0 };
    setItems(next);
  };
  const subtotal = items.reduce((s, it) => s + (it.quantity || 0) * (it.unit_price || 0), 0);
  const tax = subtotal * (taxRate || 0);
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-[11px] uppercase tracking-widest font-mono-tactical text-zinc-500">{t.common.description}</label>
        <button type="button" onClick={() => setItems([...items, { description: "", quantity: 1, unit_price: 0, cost: 0 }])} className="armenta-btn-ghost !h-8 !px-3 flex items-center gap-1.5" data-testid="quote-items-add"><Plus size={12} />{t.common.add_item}</button>
      </div>
      {items.map((it, i) => (
        <div key={i} className="grid grid-cols-12 gap-2 items-center">
          <input className="col-span-12 sm:col-span-6 h-10 bg-[#0d0d0d] border border-[#262626] rounded-lg px-3 text-sm text-white outline-none focus:border-[#dc2626]" placeholder={t.common.description} value={it.description} onChange={(e) => update(i, "description", e.target.value)} data-testid={`qitem-desc-${i}`} />
          <input className="col-span-3 sm:col-span-2 h-10 bg-[#0d0d0d] border border-[#262626] rounded-lg px-2 text-sm text-white text-right outline-none focus:border-[#dc2626]" type="number" value={it.quantity} onChange={(e) => update(i, "quantity", e.target.value)} data-testid={`qitem-qty-${i}`} />
          <input className="col-span-5 sm:col-span-2 h-10 bg-[#0d0d0d] border border-[#262626] rounded-lg px-2 text-sm text-white text-right outline-none focus:border-[#dc2626]" type="number" value={it.unit_price} onChange={(e) => update(i, "unit_price", e.target.value)} data-testid={`qitem-price-${i}`} />
          <div className="col-span-3 sm:col-span-1 text-right text-xs text-white font-mono-tactical">{fmtMoney((it.quantity || 0) * (it.unit_price || 0))}</div>
          <button type="button" onClick={() => setItems(items.filter((_, idx) => idx !== i))} className="col-span-1 text-zinc-500 hover:text-red-400"><Trash2 size={14} /></button>
        </div>
      ))}
      <div className="pt-3 mt-2 border-t border-[#1a1a1a] flex justify-end gap-6 text-sm">
        <div className="text-right">
          <div className="text-[10px] uppercase font-mono-tactical text-zinc-500">{t.common.subtotal}</div>
          <div className="text-white font-mono-tactical">{fmtMoney(subtotal)}</div>
        </div>
        <div className="text-right">
          <div className="text-[10px] uppercase font-mono-tactical text-zinc-500 flex items-center gap-1 justify-end">
            {t.common.tax}
            <input type="number" step="0.01" value={taxRate} onChange={(e) => setTaxRate(Number(e.target.value) || 0)} className="w-14 h-6 bg-[#0d0d0d] border border-[#262626] rounded px-2 text-[11px] text-white text-right outline-none" data-testid="quote-tax-rate" />
          </div>
          <div className="text-white font-mono-tactical">{fmtMoney(tax)}</div>
        </div>
        <div className="text-right">
          <div className="text-[10px] uppercase font-mono-tactical text-[#dc2626] font-bold">{t.common.total}</div>
          <div className="text-white font-mono-tactical text-lg font-bold">{fmtMoney(subtotal + tax)}</div>
        </div>
      </div>
    </div>
  );
}

function QuoteForm({ initial, clients, vehicles, onClose, onSaved }) {
  const { t } = useI18n();
  const [f, setF] = useState({
    client_id: initial?.client_id || clients[0]?.id || "",
    vehicle_id: initial?.vehicle_id || "",
    status: initial?.status || "draft",
    valid_days: initial?.valid_days ?? 15,
    notes: initial?.notes || "",
  });
  const [items, setItems] = useState(initial?.items || []);
  const [taxRate, setTaxRate] = useState(initial?.tax_rate ?? 0.16);
  const [saving, setSaving] = useState(false);
  const editing = !!initial?.id;
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }));
  const filteredVehicles = useMemo(() => vehicles.filter((v) => v.client_id === f.client_id), [vehicles, f.client_id]);

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    const payload = { ...f, items, tax_rate: taxRate };
    if (!payload.vehicle_id) delete payload.vehicle_id;
    if (!payload.client_id) delete payload.client_id;
    try {
      editing ? await api.patch(`/quotes/${initial.id}`, payload) : await api.post("/quotes", payload);
      toast.success(t.cotizaciones.saved); onSaved();
    } catch (e2) { toast.error(formatApiError(e2)); }
    finally { setSaving(false); }
  };

  const doDelete = async () => {
    if (!window.confirm(t.common.delete_confirm)) return;
    try { await api.delete(`/quotes/${initial.id}`); toast.success(t.cotizaciones.deleted); onSaved(); }
    catch (e2) { toast.error(formatApiError(e2)); }
  };

  const statusOptions = Object.entries(t.cotizaciones.statuses).map(([k, v]) => ({ value: k, label: v }));

  return (
    <Modal title={editing ? t.cotizaciones.edit : t.cotizaciones.new} onClose={onClose} testId="quote-form" size="xl">
      <form onSubmit={submit} className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          <Field label={t.common.client} required>
            <Select testId="quote-client" value={f.client_id} onChange={(v) => { set("client_id")(v); set("vehicle_id")(""); }} options={[{ value: "", label: "—" }, ...clients.map((c) => ({ value: c.id, label: c.nombre }))]} />
          </Field>
          <Field label={t.common.vehicle}>
            <Select testId="quote-vehicle" value={f.vehicle_id} onChange={set("vehicle_id")} options={[{ value: "", label: "—" }, ...filteredVehicles.map((v) => ({ value: v.id, label: `${v.year || ""} ${v.make} ${v.model}` }))]} />
          </Field>
          <Field label={t.common.status}><Select testId="quote-status" value={f.status} onChange={set("status")} options={statusOptions} /></Field>
          <Field label={t.cotizaciones.valid_days}><Input testId="quote-valid" type="number" value={f.valid_days} onChange={set("valid_days")} /></Field>
        </div>
        <div className="pt-2 border-t border-[#1a1a1a]">
          <ItemsInline items={items} setItems={setItems} taxRate={taxRate} setTaxRate={setTaxRate} />
        </div>
        <Field label={t.common.description}><Textarea testId="quote-notes" value={f.notes} onChange={set("notes")} rows={2} /></Field>
        <div className="flex flex-col sm:flex-row gap-2 pt-1">
          <button type="submit" className="armenta-btn-primary flex-1 !h-12" disabled={saving} data-testid="quote-submit">{saving ? t.common.saving : t.common.save}</button>
          {editing && <Link to={`/recibo/cotizacion/${initial.id}`} className="h-12 px-4 rounded-lg border border-[#dc262666] bg-[#dc262614] text-[#dc2626] hover:bg-[#dc262622] flex items-center justify-center gap-2 text-sm font-semibold" data-testid="quote-view-receipt"><ReceiptIcon size={14} />{t.cotizaciones.view_receipt}</Link>}
          {editing && <button type="button" onClick={doDelete} className="h-12 px-4 rounded-lg border border-red-900/60 bg-red-950/30 text-red-300 flex items-center gap-2 text-sm"><Trash2 size={14} />{t.common.delete}</button>}
          <button type="button" onClick={onClose} className="armenta-btn-ghost !h-12 !px-4">{t.common.cancel}</button>
        </div>
      </form>
    </Modal>
  );
}

export default function Cotizaciones() {
  const { t } = useI18n();
  const [items, setItems] = useState([]);
  const [clients, setClients] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [q, c, v] = await Promise.all([
        api.get("/quotes"),
        api.get("/clients", { params: { limit: 500 } }),
        api.get("/vehicles"),
      ]);
      setItems(q.data.items || []);
      setClients(c.data.items || []);
      setVehicles(v.data.items || []);
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openEdit = async (q) => {
    try { const { data } = await api.get(`/quotes/${q.id}`); setEditing(data); setFormOpen(true); }
    catch (e) { toast.error(formatApiError(e)); }
  };
  const clientName = (id) => clients.find((c) => c.id === id)?.nombre || "—";

  return (
    <div className="space-y-5" data-testid="cotizaciones-page">
      <PageHeader
        title={t.cotizaciones.title}
        subtitle={t.cotizaciones.subtitle}
        action={<button onClick={() => { setEditing(null); setFormOpen(true); }} className="armenta-btn-primary !w-auto !h-12 !px-5 flex items-center gap-2" data-testid="cotizaciones-new"><Plus size={16} />{t.cotizaciones.new}</button>}
      />
      {loading ? <div className="card-tactical p-10 flex justify-center"><span className="spinner spinner-gold" /></div>
        : items.length === 0 ? <div className="card-tactical p-8 text-center"><FileText size={28} className="text-[#dc2626] mx-auto mb-3" /><p className="text-sm text-zinc-400">{t.cotizaciones.empty}</p></div>
        : <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {items.map((q) => (
              <button key={q.id} onClick={() => openEdit(q)} className="card-tactical p-4 text-left hover:border-[#dc262666]" data-testid={`quote-card-${q.id}`}>
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="min-w-0">
                    <div className="font-mono-tactical text-[10px] uppercase tracking-widest text-[#dc2626]">{q.folio}</div>
                    <div className="text-white font-semibold truncate">{clientName(q.client_id)}</div>
                  </div>
                  <StatusBadge label={t.cotizaciones.statuses[q.status]} tone={STATUS_TONE[q.status]} />
                </div>
                <div className="mt-3 pt-3 border-t border-[#1a1a1a] flex justify-between items-end text-xs">
                  <span className="text-zinc-500">{fmtDate(q.created_at)}</span>
                  <span className="text-white font-mono-tactical font-bold">{fmtMoney(q.total)}</span>
                </div>
              </button>
            ))}
          </div>
      }
      {formOpen && <QuoteForm initial={editing} clients={clients} vehicles={vehicles} onClose={() => { setFormOpen(false); setEditing(null); }} onSaved={() => { setFormOpen(false); setEditing(null); load(); }} />}
    </div>
  );
}
