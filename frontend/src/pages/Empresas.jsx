import React, { useCallback, useEffect, useState } from "react";
import { Plus, Building2, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, formatApiError } from "../lib/api";
import { useI18n } from "../context/I18nContext";
import { Modal, Field, Input, Textarea, PageHeader } from "../components/ui-kit";

function CompanyForm({ initial, onClose, onSaved }) {
  const { t } = useI18n();
  const [f, setF] = useState({
    name: initial?.name || "", rfc: initial?.rfc || "",
    contact: initial?.contact || "", phone: initial?.phone || "",
    email: initial?.email || "", address: initial?.address || "",
    payment_terms_days: initial?.payment_terms_days || 0,
    credit_limit: initial?.credit_limit || 0,
    notes: initial?.notes || "",
  });
  const [saving, setSaving] = useState(false);
  const editing = !!initial?.id;
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    if (!f.name.trim()) return toast.error(t.common.required);
    setSaving(true);
    try {
      editing
        ? await api.patch(`/companies/${initial.id}`, f)
        : await api.post("/companies", f);
      toast.success(t.empresas.saved);
      onSaved();
    } catch (e2) { toast.error(formatApiError(e2)); }
    finally { setSaving(false); }
  };

  const doDelete = async () => {
    if (!window.confirm(t.common.delete_confirm)) return;
    try { await api.delete(`/companies/${initial.id}`); toast.success(t.empresas.deleted); onSaved(); }
    catch (e2) { toast.error(formatApiError(e2)); }
  };

  return (
    <Modal title={editing ? t.empresas.edit : t.empresas.new} onClose={onClose} testId="company-form" size="lg">
      <form onSubmit={submit} className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label={t.empresas.form.name} required><Input testId="company-name" value={f.name} onChange={set("name")} /></Field>
          <Field label={t.empresas.form.rfc}><Input testId="company-rfc" value={f.rfc} onChange={set("rfc")} /></Field>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Field label={t.empresas.form.contact}><Input testId="company-contact" value={f.contact} onChange={set("contact")} /></Field>
          <Field label={t.empresas.form.phone}><Input testId="company-phone" value={f.phone} onChange={set("phone")} /></Field>
          <Field label={t.empresas.form.email}><Input testId="company-email" type="email" value={f.email} onChange={set("email")} /></Field>
        </div>
        <Field label={t.empresas.form.address}><Input testId="company-address" value={f.address} onChange={set("address")} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t.empresas.form.terms}><Input testId="company-terms" type="number" value={f.payment_terms_days} onChange={set("payment_terms_days")} /></Field>
          <Field label={t.empresas.form.credit}><Input testId="company-credit" type="number" value={f.credit_limit} onChange={set("credit_limit")} /></Field>
        </div>
        <Field label={t.empresas.form.notes}><Textarea testId="company-notes" value={f.notes} onChange={set("notes")} /></Field>
        <div className="flex flex-col sm:flex-row gap-2 pt-1">
          <button type="submit" className="armenta-btn-primary flex-1 !h-12" disabled={saving} data-testid="company-submit">{saving ? t.common.saving : t.common.save}</button>
          {editing && <button type="button" onClick={doDelete} className="h-12 px-4 rounded-lg border border-red-900/60 bg-red-950/30 text-red-300 flex items-center gap-2 text-sm"><Trash2 size={14} />{t.common.delete}</button>}
          <button type="button" onClick={onClose} className="armenta-btn-ghost !h-12 !px-4">{t.common.cancel}</button>
        </div>
      </form>
    </Modal>
  );
}

export default function Empresas() {
  const { t } = useI18n();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try { const { data } = await api.get("/companies"); setItems(data.items || []); }
    catch (e) { toast.error(formatApiError(e)); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-5" data-testid="empresas-page">
      <PageHeader
        title={t.empresas.title}
        subtitle={t.empresas.subtitle}
        action={<button onClick={() => { setEditing(null); setFormOpen(true); }} className="armenta-btn-primary !w-auto !h-12 !px-5 flex items-center gap-2" data-testid="empresas-new"><Plus size={16} />{t.empresas.new}</button>}
      />
      {loading ? <div className="card-tactical p-10 flex justify-center"><span className="spinner spinner-gold" /></div>
        : items.length === 0 ? <div className="card-tactical p-8 text-center"><Building2 size={28} className="text-[#dc2626] mx-auto mb-3" /><p className="text-sm text-zinc-400">{t.empresas.empty}</p></div>
        : <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {items.map((c) => (
              <button key={c.id} onClick={() => { setEditing(c); setFormOpen(true); }} className="card-tactical p-4 text-left hover:border-[#dc262666]" data-testid={`company-card-${c.id}`}>
                <div className="flex items-start justify-between">
                  <div className="min-w-0">
                    <div className="text-white font-semibold truncate">{c.name}</div>
                    <div className="text-xs text-zinc-500 font-mono-tactical uppercase tracking-widest mt-1">{c.rfc || "—"}</div>
                  </div>
                  <Building2 size={16} className="text-[#dc2626]" />
                </div>
                <div className="mt-3 pt-3 border-t border-[#1a1a1a] text-xs text-zinc-400 space-y-1">
                  {c.contact && <div>{c.contact}</div>}
                  {c.phone && <div>{c.phone}</div>}
                  {c.email && <div className="truncate">{c.email}</div>}
                </div>
              </button>
            ))}
          </div>
      }
      {formOpen && <CompanyForm initial={editing} onClose={() => { setFormOpen(false); setEditing(null); }} onSaved={() => { setFormOpen(false); setEditing(null); load(); }} />}
    </div>
  );
}
