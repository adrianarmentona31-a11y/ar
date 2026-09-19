import React, { useCallback, useEffect, useState } from "react";
import { Plus, HardHat, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, formatApiError } from "../lib/api";
import { useI18n } from "../context/I18nContext";
import { Modal, Field, Input, Select, PageHeader, StatusBadge } from "../components/ui-kit";

function TechForm({ initial, onClose, onSaved }) {
  const { t } = useI18n();
  const [f, setF] = useState({
    name: initial?.name || "", phone: initial?.phone || "",
    role: initial?.role || "technician",
    commission_type: initial?.commission_type || "percentage",
    commission_value: initial?.commission_value ?? 0,
    active: initial?.active ?? true,
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
        ? await api.patch(`/technicians/${initial.id}`, f)
        : await api.post("/technicians", f);
      toast.success(t.tecnicos.saved); onSaved();
    } catch (e2) { toast.error(formatApiError(e2)); }
    finally { setSaving(false); }
  };

  const doDelete = async () => {
    if (!window.confirm(t.common.delete_confirm)) return;
    try { await api.delete(`/technicians/${initial.id}`); toast.success(t.tecnicos.deleted); onSaved(); }
    catch (e2) { toast.error(formatApiError(e2)); }
  };

  return (
    <Modal title={editing ? t.tecnicos.edit : t.tecnicos.new} onClose={onClose} testId="tech-form">
      <form onSubmit={submit} className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label={t.tecnicos.form.name} required><Input testId="tech-name" value={f.name} onChange={set("name")} /></Field>
          <Field label={t.tecnicos.form.phone}><Input testId="tech-phone" value={f.phone} onChange={set("phone")} /></Field>
        </div>
        <Field label={t.tecnicos.form.role}><Input testId="tech-role" value={f.role} onChange={set("role")} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t.tecnicos.form.commission_type}>
            <Select testId="tech-ctype" value={f.commission_type} onChange={set("commission_type")} options={[
              { value: "percentage", label: t.tecnicos.form.percentage },
              { value: "fixed", label: t.tecnicos.form.fixed },
              { value: "none", label: t.tecnicos.form.none },
            ]} />
          </Field>
          <Field label={t.tecnicos.form.commission_value}><Input testId="tech-cval" type="number" value={f.commission_value} onChange={set("commission_value")} /></Field>
        </div>
        <label className="flex items-center gap-2 text-sm text-zinc-300">
          <input type="checkbox" checked={f.active} onChange={(e) => set("active")(e.target.checked)} data-testid="tech-active" />
          {t.tecnicos.form.active}
        </label>
        <div className="flex gap-2 pt-1">
          <button type="submit" className="armenta-btn-primary flex-1 !h-12" disabled={saving} data-testid="tech-submit">{saving ? t.common.saving : t.common.save}</button>
          {editing && <button type="button" onClick={doDelete} className="h-12 px-4 rounded-lg border border-red-900/60 bg-red-950/30 text-red-300 flex items-center gap-2 text-sm"><Trash2 size={14} />{t.common.delete}</button>}
          <button type="button" onClick={onClose} className="armenta-btn-ghost !h-12 !px-4">{t.common.cancel}</button>
        </div>
      </form>
    </Modal>
  );
}

export default function Tecnicos() {
  const { t } = useI18n();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try { const { data } = await api.get("/technicians"); setItems(data.items || []); }
    catch (e) { toast.error(formatApiError(e)); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-5" data-testid="tecnicos-page">
      <PageHeader
        title={t.tecnicos.title}
        subtitle={t.tecnicos.subtitle}
        action={<button onClick={() => { setEditing(null); setFormOpen(true); }} className="armenta-btn-primary !w-auto !h-12 !px-5 flex items-center gap-2" data-testid="tecnicos-new"><Plus size={16} />{t.tecnicos.new}</button>}
      />
      {loading ? <div className="card-tactical p-10 flex justify-center"><span className="spinner spinner-gold" /></div>
        : items.length === 0 ? <div className="card-tactical p-8 text-center"><HardHat size={28} className="text-[#dc2626] mx-auto mb-3" /><p className="text-sm text-zinc-400">{t.tecnicos.empty}</p></div>
        : <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {items.map((tc) => (
              <button key={tc.id} onClick={() => { setEditing(tc); setFormOpen(true); }} className="card-tactical p-4 text-left hover:border-[#dc262666]" data-testid={`tech-card-${tc.id}`}>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-white font-semibold truncate">{tc.name}</div>
                    <div className="text-xs text-zinc-500 mt-0.5">{tc.role}</div>
                  </div>
                  <StatusBadge label={tc.active ? "ACTIVO" : "INACTIVO"} tone={tc.active ? "green" : "gray"} />
                </div>
                <div className="mt-3 pt-3 border-t border-[#1a1a1a] text-xs text-zinc-400 flex justify-between">
                  <span>{tc.phone || "—"}</span>
                  <span className="font-mono-tactical">{tc.commission_type === "percentage" ? `${tc.commission_value}%` : tc.commission_type === "fixed" ? `$${tc.commission_value}` : "—"}</span>
                </div>
              </button>
            ))}
          </div>
      }
      {formOpen && <TechForm initial={editing} onClose={() => { setFormOpen(false); setEditing(null); }} onSaved={() => { setFormOpen(false); setEditing(null); load(); }} />}
    </div>
  );
}
