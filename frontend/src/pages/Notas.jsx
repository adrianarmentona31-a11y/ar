import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Trash2, FileText, Receipt as ReceiptIcon, Mail, Send } from "lucide-react";
import { toast } from "sonner";
import { api, formatApiError } from "../lib/api";
import { useI18n } from "../context/I18nContext";
import { fmtDate, fmtMoney } from "../lib/format";
import { Modal, Field, Input, Textarea, Select, PageHeader, StatusBadge } from "../components/ui-kit";

const emptyItem = () => ({ description: "", quantity: 1, unit_price: 0, cost: 0, is_labor: false });

function NoteForm({ clients, initial, onClose, onSaved }) {
  const { t } = useI18n();
  const tr = t.notas;
  const editing = !!initial?.id;
  const [f, setF] = useState({
    client_id: initial?.client_id || "", client_name: initial?.client_name || "", client_phone: initial?.client_phone || "",
    client_email: initial?.client_email || "", vehicle_label: initial?.vehicle_label || "", notes: initial?.notes || "",
    paid_amount: initial?.paid_amount ?? 0, method: initial?.method || "cash", tax_rate: initial?.tax_rate ?? 0,
  });
  const [items, setItems] = useState(initial?.items?.length ? initial.items : [emptyItem()]);
  const [saving, setSaving] = useState(false);
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }));
  const setItem = (i, k, v) => setItems((arr) => arr.map((it, j) => (j === i ? { ...it, [k]: v } : it)));

  const subtotal = useMemo(() => items.reduce((a, it) => a + (Number(it.quantity) || 0) * (Number(it.unit_price) || 0), 0), [items]);
  const total = subtotal * (1 + (Number(f.tax_rate) || 0));

  const pickClient = (id) => {
    const c = clients.find((x) => x.id === id);
    setF((s) => ({ ...s, client_id: id, client_name: c?.nombre || s.client_name, client_phone: c?.telefono || s.client_phone, client_email: c?.email || s.client_email }));
  };

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    const payload = { ...f, tax_rate: Number(f.tax_rate) || 0, paid_amount: Number(f.paid_amount) || 0,
      items: items.filter((it) => it.description.trim()).map((it) => ({ ...it, quantity: Number(it.quantity) || 0, unit_price: Number(it.unit_price) || 0, cost: Number(it.cost) || 0 })) };
    if (!payload.client_id) delete payload.client_id;
    try {
      const res = editing ? await api.patch(`/notes/${initial.id}`, payload) : await api.post("/notes", payload);
      toast.success(tr.saved); onSaved(res.data);
    } catch (e2) { toast.error(formatApiError(e2)); }
    finally { setSaving(false); }
  };

  return (
    <Modal title={editing ? `${tr.edit} · ${initial.folio}` : tr.new} onClose={onClose} testId="note-form">
      <form onSubmit={submit} className="space-y-4">
        <Field label={t.common.client}>
          <Select testId="note-client" value={f.client_id} onChange={pickClient} options={[{ value: "", label: tr.walk_in }, ...clients.map((c) => ({ value: c.id, label: c.nombre }))]} />
        </Field>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label={tr.client_name}><Input testId="note-client-name" value={f.client_name} onChange={set("client_name")} placeholder={tr.walk_in} /></Field>
          <Field label={t.common.phone}><Input testId="note-client-phone" value={f.client_phone} onChange={set("client_phone")} /></Field>
          <Field label="Email"><Input testId="note-client-email" type="email" value={f.client_email} onChange={set("client_email")} /></Field>
          <Field label={tr.vehicle}><Input testId="note-vehicle" value={f.vehicle_label} onChange={set("vehicle_label")} placeholder="Nissan Versa 2023" /></Field>
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-mono-tactical text-[10px] uppercase tracking-widest text-zinc-500">{tr.items}</span>
            <button type="button" onClick={() => setItems((a) => [...a, emptyItem()])} className="text-xs text-[#dc2626] flex items-center gap-1" data-testid="note-add-item"><Plus size={12} />{tr.add_item}</button>
          </div>
          {items.map((it, i) => (
            <div key={i} className="grid grid-cols-[1fr_64px_96px_28px] gap-2 items-center" data-testid={`note-item-${i}`}>
              <Input testId={`note-item-desc-${i}`} value={it.description} onChange={(v) => setItem(i, "description", v)} placeholder={tr.item_placeholder} />
              <Input testId={`note-item-qty-${i}`} type="number" value={it.quantity} onChange={(v) => setItem(i, "quantity", v)} />
              <Input testId={`note-item-price-${i}`} type="number" value={it.unit_price} onChange={(v) => setItem(i, "unit_price", v)} />
              <button type="button" onClick={() => setItems((a) => a.filter((_, j) => j !== i))} className="text-zinc-600 hover:text-red-400"><Trash2 size={14} /></button>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-3 gap-3">
          <Field label="IVA"><Input testId="note-tax" type="number" value={f.tax_rate} onChange={set("tax_rate")} /></Field>
          <Field label={tr.paid_amount}><Input testId="note-paid" type="number" value={f.paid_amount} onChange={set("paid_amount")} /></Field>
          <Field label={t.cobros.form.method}>
            <Select testId="note-method" value={f.method} onChange={set("method")} options={Object.entries(t.cobros.methods).map(([k, v]) => ({ value: k, label: v }))} />
          </Field>
        </div>
        <div className="flex items-center justify-between text-sm">
          <button type="button" onClick={() => set("paid_amount")(Number(total.toFixed(2)))} className="text-xs text-[#dc2626] underline" data-testid="note-pay-full">{tr.pay_full}</button>
          <span className="font-mono-tactical text-white font-bold" data-testid="note-total">{t.common.total}: {fmtMoney(total)}</span>
        </div>
        <Field label={t.common.notes}><Textarea testId="note-notes" value={f.notes} onChange={set("notes")} rows={2} /></Field>
        <div className="flex gap-2 pt-1">
          <button type="submit" className="armenta-btn-primary flex-1 !h-12" disabled={saving} data-testid="note-submit">{saving ? t.common.saving : t.common.save}</button>
          <button type="button" onClick={onClose} className="armenta-btn-ghost !h-12 !px-4">{t.common.cancel}</button>
        </div>
      </form>
    </Modal>
  );
}

export default function Notas() {
  const { t } = useI18n();
  const tr = t.notas;
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [n, c] = await Promise.all([api.get("/notes"), api.get("/clients", { params: { limit: 500 } })]);
      setItems(n.data.items || []); setClients(c.data.items || []);
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const del = async (id) => {
    if (!window.confirm(t.common.delete_confirm)) return;
    try { await api.delete(`/notes/${id}`); toast.success(tr.deleted); load(); } catch (e) { toast.error(formatApiError(e)); }
  };
  const email = async (n) => {
    if (!n.client_email) return toast.error(t.servicios.no_client_email);
    setBusy(n.id);
    try { const { data } = await api.post(`/notes/${n.id}/send-email`); toast.success(`${t.servicios.receipt_sent} ${data.to}`); }
    catch (e) { toast.error(formatApiError(e)); } finally { setBusy(""); }
  };
  const wa = (n) => {
    const phone = (n.client_phone || "").replace(/\D/g, "");
    const text = `Hola ${n.client_name}, gracias por tu preferencia. Nota ${n.folio}: total ${fmtMoney(n.total)}, pagado ${fmtMoney(n.paid_amount)}${n.balance > 0 ? `, saldo ${fmtMoney(n.balance)}` : ""}. Armenta's Motors Company.`;
    window.open(`https://wa.me/${phone}?text=${encodeURIComponent(text)}`, "_blank", "noopener");
  };

  return (
    <div className="space-y-5" data-testid="notas-page">
      <PageHeader title={tr.title} subtitle={tr.subtitle}
        action={<button onClick={() => { setEditing(null); setFormOpen(true); }} className="armenta-btn-primary !w-auto !h-12 !px-5 flex items-center gap-2" data-testid="notas-new"><Plus size={16} />{tr.new}</button>} />
      {loading ? <div className="card-tactical p-10 flex justify-center"><span className="spinner spinner-gold" /></div>
        : items.length === 0 ? <div className="card-tactical p-8 text-center"><FileText size={28} className="text-[#dc2626] mx-auto mb-3" /><p className="text-sm text-zinc-400">{tr.empty}</p></div>
        : <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {items.map((n) => (
              <div key={n.id} className="card-tactical p-4 space-y-3" data-testid={`note-card-${n.id}`}>
                <div className="flex items-start justify-between gap-2 cursor-pointer" onClick={() => { setEditing(n); setFormOpen(true); }}>
                  <div className="min-w-0">
                    <div className="font-mono-tactical text-[10px] uppercase tracking-widest text-[#dc2626]">{n.folio} · {fmtDate(n.created_at)}</div>
                    <div className="text-white font-semibold truncate">{n.client_name}</div>
                    <div className="text-xs text-zinc-500 truncate">{n.vehicle_label || (n.items[0]?.description ?? "")}</div>
                  </div>
                  <StatusBadge label={n.status === "pagada" ? tr.paid : tr.pending} tone={n.status === "pagada" ? "green" : "amber"} />
                </div>
                <div className="flex items-baseline justify-between">
                  <span className="text-xs text-zinc-500">{n.balance > 0 ? `${t.recibo.balance}: ${fmtMoney(n.balance)}` : t.cobros.methods[n.method]}</span>
                  <span className="font-mono-tactical text-white font-bold text-lg">{fmtMoney(n.total)}</span>
                </div>
                <div className="flex gap-2 flex-wrap">
                  <button onClick={() => navigate(`/recibo/nota/${n.id}`)} className="armenta-btn-ghost !h-9 !px-3 flex items-center gap-1.5 text-xs" data-testid={`note-receipt-${n.id}`}><ReceiptIcon size={12} />{t.servicios.view_receipt}</button>
                  <button onClick={() => wa(n)} disabled={!n.client_phone} className="h-9 px-3 rounded-lg border border-emerald-800/60 bg-emerald-950/30 text-emerald-300 flex items-center gap-1.5 text-xs disabled:opacity-40" data-testid={`note-wa-${n.id}`}><Send size={12} />WhatsApp</button>
                  <button onClick={() => email(n)} disabled={busy === n.id} className={`h-9 px-3 rounded-lg border flex items-center gap-1.5 text-xs ${n.client_email ? "border-sky-800/60 bg-sky-950/30 text-sky-300" : "border-[#262626] text-zinc-600"}`} data-testid={`note-email-${n.id}`}>{busy === n.id ? <span className="spinner" /> : <Mail size={12} />}Email</button>
                  <button onClick={() => del(n.id)} className="ml-auto text-zinc-600 hover:text-red-400" data-testid={`note-rm-${n.id}`}><Trash2 size={14} /></button>
                </div>
              </div>
            ))}
          </div>}
      {formOpen && <NoteForm clients={clients} initial={editing} onClose={() => setFormOpen(false)} onSaved={(n) => { setFormOpen(false); load(); if (!editing) navigate(`/recibo/nota/${n.id}`); }} />}
    </div>
  );
}
