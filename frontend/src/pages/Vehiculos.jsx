import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Plus, Car, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, formatApiError } from "../lib/api";
import { useI18n } from "../context/I18nContext";
import { fmtDate } from "../lib/format";
import { Modal, Field, Input, Textarea, Select, PageHeader } from "../components/ui-kit";

function VehicleForm({ initial, clients, onClose, onSaved }) {
  const { t } = useI18n();
  const [f, setF] = useState({
    client_id: initial?.client_id || clients[0]?.id || "",
    year: initial?.year || "",
    make: initial?.make || "",
    model: initial?.model || "",
    engine: initial?.engine || "",
    vin: initial?.vin || "",
    plates: initial?.plates || "",
    mileage: initial?.mileage || 0,
    color: initial?.color || "",
    drive: initial?.drive || "",
    notes: initial?.notes || "",
    next_service_km: initial?.next_service_km || "",
    next_service_date: initial?.next_service_date || "",
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const editing = !!initial?.id;
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    if (!f.client_id || !f.make || !f.model) {
      setErr(t.common.required);
      return;
    }
    setSaving(true);
    const payload = { ...f };
    if (payload.year === "") delete payload.year;
    if (payload.mileage === "") payload.mileage = 0;
    if (payload.next_service_km === "") delete payload.next_service_km;
    if (payload.next_service_date === "") delete payload.next_service_date;
    try {
      const res = editing
        ? await api.patch(`/vehicles/${initial.id}`, payload)
        : await api.post("/vehicles", payload);
      toast.success(t.vehiculos.saved);
      onSaved(res.data);
    } catch (e2) {
      setErr(formatApiError(e2));
    } finally {
      setSaving(false);
    }
  };

  const doDelete = async () => {
    if (!editing) return;
    if (!window.confirm(t.common.delete_confirm)) return;
    try {
      await api.delete(`/vehicles/${initial.id}`);
      toast.success(t.vehiculos.deleted);
      onSaved(null);
    } catch (e2) {
      toast.error(formatApiError(e2));
    }
  };

  return (
    <Modal title={editing ? t.vehiculos.edit : t.vehiculos.new} onClose={onClose} testId="vehicle-form" size="lg">
      <form onSubmit={submit} className="space-y-4" data-testid="vehicle-form-body">
        <Field label={t.vehiculos.form.client} required>
          <Select
            testId="vehicle-form-client"
            value={f.client_id}
            onChange={set("client_id")}
            options={[{ value: "", label: t.vehiculos.form.select_client }, ...clients.map((c) => ({ value: c.id, label: c.nombre }))]}
          />
        </Field>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Field label={t.vehiculos.form.year}><Input testId="vehicle-form-year" type="number" value={f.year} onChange={set("year")} /></Field>
          <Field label={t.vehiculos.form.make} required><Input testId="vehicle-form-make" value={f.make} onChange={set("make")} /></Field>
          <Field label={t.vehiculos.form.model} required><Input testId="vehicle-form-model" value={f.model} onChange={set("model")} /></Field>
          <Field label={t.vehiculos.form.color}><Input testId="vehicle-form-color" value={f.color} onChange={set("color")} /></Field>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Field label={t.vehiculos.form.engine}><Input testId="vehicle-form-engine" value={f.engine} onChange={set("engine")} /></Field>
          <Field label={t.vehiculos.form.vin}><Input testId="vehicle-form-vin" value={f.vin} onChange={set("vin")} /></Field>
          <Field label={t.vehiculos.form.plates}><Input testId="vehicle-form-plates" value={f.plates} onChange={set("plates")} /></Field>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Field label={t.vehiculos.form.mileage}><Input testId="vehicle-form-mileage" type="number" value={f.mileage} onChange={set("mileage")} /></Field>
          <Field label={t.vehiculos.form.next_km}><Input testId="vehicle-form-next-km" type="number" value={f.next_service_km} onChange={set("next_service_km")} /></Field>
          <Field label={t.vehiculos.form.next_date}><Input testId="vehicle-form-next-date" type="date" value={f.next_service_date} onChange={set("next_service_date")} /></Field>
        </div>
        <Field label={t.vehiculos.form.notes}><Textarea testId="vehicle-form-notes" value={f.notes} onChange={set("notes")} /></Field>
        {err && <div className="rounded-lg border border-red-800/70 bg-red-950/40 px-3.5 py-2.5 text-sm text-red-200">{err}</div>}
        <div className="flex flex-col sm:flex-row gap-2 sm:gap-3 pt-1">
          <button type="submit" className="armenta-btn-primary flex-1 !h-12" disabled={saving} data-testid="vehicle-form-submit">
            {saving ? t.common.saving : t.common.save}
          </button>
          {editing && (
            <button type="button" onClick={doDelete} className="h-12 px-4 rounded-lg border border-red-900/60 bg-red-950/30 text-red-300 hover:bg-red-900/40 flex items-center justify-center gap-2 text-sm" data-testid="vehicle-form-delete">
              <Trash2 size={14} /> {t.common.delete}
            </button>
          )}
          <button type="button" onClick={onClose} className="armenta-btn-ghost !h-12 !px-4">{t.common.cancel}</button>
        </div>
      </form>
    </Modal>
  );
}

export default function Vehiculos() {
  const { t } = useI18n();
  const [items, setItems] = useState([]);
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [v, c] = await Promise.all([
        api.get("/vehicles", { params: q ? { q } : {} }),
        api.get("/clients", { params: { limit: 500 } }),
      ]);
      setItems(v.data.items || []);
      setClients(c.data.items || []);
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setLoading(false);
    }
  }, [q]);

  useEffect(() => { const id = setTimeout(load, 220); return () => clearTimeout(id); }, [load]);

  return (
    <div className="space-y-5" data-testid="vehiculos-page">
      <PageHeader
        title={t.vehiculos.title}
        subtitle={t.vehiculos.subtitle}
        action={
          <button type="button" onClick={() => { setEditing(null); setFormOpen(true); }} className="armenta-btn-primary !w-auto !h-12 !px-5 flex items-center gap-2" data-testid="vehiculos-new" disabled={clients.length === 0}>
            <Plus size={16} /> {t.vehiculos.new}
          </button>
        }
      />
      <div className="card-tactical p-3">
        <input className="w-full h-11 bg-[#0d0d0d] border border-[#262626] rounded-lg px-3.5 text-sm text-white outline-none focus:border-[#dc2626]" placeholder={t.common.search} value={q} onChange={(e) => setQ(e.target.value)} data-testid="vehiculos-search" />
      </div>

      {loading ? (
        <div className="card-tactical p-10 flex justify-center"><span className="spinner spinner-gold" /></div>
      ) : items.length === 0 ? (
        <div className="card-tactical p-8 text-center" data-testid="vehiculos-empty">
          <Car size={28} className="text-[#dc2626] mx-auto mb-3" />
          <p className="text-sm text-zinc-400">{t.vehiculos.empty}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3" data-testid="vehiculos-list">
          {items.map((v) => (
            <button key={v.id} onClick={() => { setEditing(v); setFormOpen(true); }} className="card-tactical p-4 text-left hover:border-[#dc262666]" data-testid={`vehicle-card-${v.id}`}>
              <div className="flex items-start justify-between mb-2">
                <div className="min-w-0">
                  <div className="text-white font-semibold truncate">{v.year || ""} {v.make} {v.model}</div>
                  <div className="text-xs text-zinc-500 truncate">{v.client_name || ""}</div>
                </div>
                <Car size={16} className="text-[#dc2626] shrink-0" />
              </div>
              <div className="grid grid-cols-2 gap-2 text-[11px] font-mono-tactical uppercase tracking-widest text-zinc-500 mt-3 pt-3 border-t border-[#1a1a1a]">
                <div><span className="text-zinc-600">VIN</span><div className="text-zinc-300 normal-case tracking-normal font-sans truncate">{v.vin || "—"}</div></div>
                <div><span className="text-zinc-600">PLACAS</span><div className="text-zinc-300 normal-case tracking-normal font-sans truncate">{v.plates || "—"}</div></div>
                <div><span className="text-zinc-600">KM</span><div className="text-zinc-300 normal-case tracking-normal font-sans truncate">{v.mileage?.toLocaleString?.() || 0}</div></div>
                <div><span className="text-zinc-600">MOTOR</span><div className="text-zinc-300 normal-case tracking-normal font-sans truncate">{v.engine || "—"}</div></div>
              </div>
              {v.next_service_date && (
                <div className="mt-3 pt-3 border-t border-[#1a1a1a] text-[10px] font-mono-tactical uppercase tracking-widest text-amber-400">
                  Próx. servicio: {fmtDate(v.next_service_date)}
                </div>
              )}
            </button>
          ))}
        </div>
      )}

      {formOpen && (
        <VehicleForm
          initial={editing}
          clients={clients}
          onClose={() => { setFormOpen(false); setEditing(null); }}
          onSaved={() => { setFormOpen(false); setEditing(null); load(); }}
        />
      )}
    </div>
  );
}
