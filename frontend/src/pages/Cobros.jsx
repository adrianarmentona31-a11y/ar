import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Wallet, Trash2, Download, Mail, Send, Landmark } from "lucide-react";
import { toast } from "sonner";
import { api, formatApiError } from "../lib/api";
import { useI18n } from "../context/I18nContext";
import { fmtDate, fmtMoney } from "../lib/format";
import { Modal, Field, Input, Textarea, Select, PageHeader, StatusBadge } from "../components/ui-kit";
import { ShareReceipt } from "../components/ShareReceipt";

function PaymentActions({ p, client, service, t }) {
  const [busy, setBusy] = useState("");
  const pdf = async () => {
    setBusy("pdf");
    try {
      const res = await api.get(`/receipts/pago/${p.id}/pdf`, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
      const a = document.createElement("a"); a.href = url; a.download = `${p.folio}.pdf`; document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => window.URL.revokeObjectURL(url), 250);
    } catch (e) { toast.error(formatApiError(e)); } finally { setBusy(""); }
  };
  const email = async () => {
    if (!client?.email) return toast.error(t.servicios.no_client_email);
    setBusy("email");
    try { const { data } = await api.post(`/payments/${p.id}/send-email`); toast.success(`${t.cobros.receipt_sent} ${data.to}`); }
    catch (e) { toast.error(formatApiError(e)); } finally { setBusy(""); }
  };
  const wa = () => {
    const phone = (client?.telefono || "").replace(/\D/g, "");
    const name = (client?.nombre || "").split(" ")[0];
    const text = `Hola${name ? ` ${name}` : ""}, confirmamos tu pago ${p.folio} por ${fmtMoney(p.amount)} (${t.cobros.methods[p.method] || p.method})${service ? ` aplicado a la orden ${service.folio}. Saldo pendiente: ${fmtMoney(service.balance)}` : ""}. Gracias por tu confianza — Armenta's Motors Company.`;
    window.open(`https://wa.me/${phone}?text=${encodeURIComponent(text)}`, "_blank", "noopener");
  };
  return (
    <div className="flex items-center justify-end gap-1.5">
      <ShareReceipt kind="pago" id={p.id} folio={p.folio} clientName={client?.nombre} clientPhone={client?.telefono} compact />
      <button onClick={pdf} disabled={!!busy} title="PDF" className="h-8 w-8 rounded-md border border-[#262626] text-zinc-400 hover:text-white flex items-center justify-center" data-testid={`payment-pdf-${p.id}`}>{busy === "pdf" ? <span className="spinner" /> : <Download size={13} />}</button>
      <button onClick={wa} disabled={!client?.telefono} title="WhatsApp" className="h-8 w-8 rounded-md border border-emerald-800/60 text-emerald-300 flex items-center justify-center disabled:opacity-30" data-testid={`payment-wa-${p.id}`}><Send size={13} /></button>
      <button onClick={email} disabled={!!busy} title={client?.email || t.servicios.no_client_email} className={`h-8 w-8 rounded-md border flex items-center justify-center ${client?.email ? "border-sky-800/60 text-sky-300" : "border-[#262626] text-zinc-600"}`} data-testid={`payment-email-${p.id}`}>{busy === "email" ? <span className="spinner" /> : <Mail size={13} />}</button>
    </div>
  );
}

function PaymentForm({ clients, services, onClose, onSaved }) {
  const { t } = useI18n();
  const [f, setF] = useState({
    service_id: "", client_id: clients[0]?.id || "",
    amount: 0, method: "cash", reference: "", notes: "",
  });
  const [saving, setSaving] = useState(false);
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    if (!f.amount || f.amount <= 0) return toast.error(t.cobros.invalid_amount);
    setSaving(true);
    const payload = { ...f };
    if (!payload.service_id) delete payload.service_id;
    if (!payload.client_id) delete payload.client_id;
    try {
      await api.post("/payments", payload);
      toast.success(t.cobros.saved); onSaved();
    } catch (e2) { toast.error(formatApiError(e2)); }
    finally { setSaving(false); }
  };

  return (
    <Modal title={t.cobros.new} onClose={onClose} testId="payment-form">
      <form onSubmit={submit} className="space-y-4">
        <Field label={t.cobros.form.service}>
          <Select testId="payment-service" value={f.service_id} onChange={(v) => {
            set("service_id")(v);
            const s = services.find((x) => x.id === v);
            if (s?.client_id) set("client_id")(s.client_id);
          }} options={[{ value: "", label: "—" }, ...services.map((s) => ({ value: s.id, label: `${s.folio} · ${fmtMoney(s.balance)} pendiente` }))]} />
        </Field>
        <Field label={t.cobros.form.client}>
          <Select testId="payment-client" value={f.client_id} onChange={set("client_id")} options={[{ value: "", label: "—" }, ...clients.map((c) => ({ value: c.id, label: c.nombre }))]} />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t.cobros.form.amount} required><Input testId="payment-amount" type="number" value={f.amount} onChange={set("amount")} /></Field>
          <Field label={t.cobros.form.method}>
            <Select testId="payment-method" value={f.method} onChange={set("method")} options={Object.entries(t.cobros.methods).map(([k, v]) => ({ value: k, label: v }))} />
          </Field>
        </div>
        <Field label={t.cobros.form.reference}><Input testId="payment-reference" value={f.reference} onChange={set("reference")} /></Field>
        <Field label={t.cobros.form.notes}><Textarea testId="payment-notes" value={f.notes} onChange={set("notes")} /></Field>
        <div className="flex gap-2 pt-1">
          <button type="submit" className="armenta-btn-primary flex-1 !h-12" disabled={saving} data-testid="payment-submit">{saving ? t.common.saving : t.common.save}</button>
          <button type="button" onClick={onClose} className="armenta-btn-ghost !h-12 !px-4">{t.common.cancel}</button>
        </div>
      </form>
    </Modal>
  );
}

export default function Cobros() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [clients, setClients] = useState([]);
  const [services, setServices] = useState([]);
  const [allServices, setAllServices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [formOpen, setFormOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [p, c, s] = await Promise.all([
        api.get("/payments"),
        api.get("/clients", { params: { limit: 500 } }),
        api.get("/services"),
      ]);
      setItems(p.data.items || []);
      setClients(c.data.items || []);
      setAllServices(s.data.items || []);
      setServices((s.data.items || []).filter((x) => x.balance > 0));
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const del = async (id) => {
    if (!window.confirm(t.common.delete_confirm)) return;
    try { await api.delete(`/payments/${id}`); toast.success(t.cobros.deleted); load(); }
    catch (e) { toast.error(formatApiError(e)); }
  };

  const clientName = (id) => clients.find((c) => c.id === id)?.nombre || "—";

  return (
    <div className="space-y-5" data-testid="cobros-page">
      <PageHeader
        title={t.cobros.title}
        subtitle={t.cobros.subtitle}
        action={<div className="flex gap-2"><button onClick={() => navigate("/transferencia")} className="armenta-btn-ghost !h-12 !px-4 flex items-center gap-2" data-testid="cobros-transfer"><Landmark size={16} />{t.transferencia.title}</button><button onClick={() => setFormOpen(true)} className="armenta-btn-primary !w-auto !h-12 !px-5 flex items-center gap-2" data-testid="cobros-new"><Plus size={16} />{t.cobros.new}</button></div>}
      />
      {loading ? <div className="card-tactical p-10 flex justify-center"><span className="spinner spinner-gold" /></div>
        : items.length === 0 ? <div className="card-tactical p-8 text-center"><Wallet size={28} className="text-[#dc2626] mx-auto mb-3" /><p className="text-sm text-zinc-400">{t.cobros.empty}</p></div>
        : <div className="card-tactical overflow-hidden">
            <table className="w-full text-sm" data-testid="cobros-table">
              <thead className="bg-[#0a0a0a] border-b border-[#1a1a1a]">
                <tr className="text-[10px] uppercase font-mono-tactical tracking-widest text-zinc-500">
                  <th className="px-4 py-3 text-left">{t.common.folio}</th>
                  <th className="px-4 py-3 text-left">{t.common.date}</th>
                  <th className="px-4 py-3 text-left">{t.common.client}</th>
                  <th className="px-4 py-3 text-left">Método</th>
                  <th className="px-4 py-3 text-right">{t.common.amount}</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {items.map((p) => (
                  <tr key={p.id} className="border-b border-[#131313] hover:bg-[#0d0d0d]" data-testid={`payment-row-${p.id}`}>
                    <td className="px-4 py-3 font-mono-tactical text-[#dc2626] text-xs">{p.folio}</td>
                    <td className="px-4 py-3 text-zinc-400 text-xs">{fmtDate(p.date)}</td>
                    <td className="px-4 py-3 text-white">{clientName(p.client_id)}</td>
                    <td className="px-4 py-3"><StatusBadge label={t.cobros.methods[p.method] || p.method} /></td>
                    <td className="px-4 py-3 text-right text-white font-mono-tactical font-bold">{fmtMoney(p.amount)}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <PaymentActions p={p} t={t} client={clients.find((c) => c.id === (p.client_id || allServices.find((s) => s.id === p.service_id)?.client_id))} service={allServices.find((s) => s.id === p.service_id)} />
                        <button onClick={() => del(p.id)} className="text-zinc-500 hover:text-red-400" data-testid={`payment-rm-${p.id}`}><Trash2 size={14} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
      }
      {formOpen && <PaymentForm clients={clients} services={services} onClose={() => setFormOpen(false)} onSaved={() => { setFormOpen(false); load(); }} />}
    </div>
  );
}
