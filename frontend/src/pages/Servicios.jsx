import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Plus, Trash2, Wrench, Receipt as ReceiptIcon, Upload, Image as ImageIcon, X, Zap, MessageSquareHeart, Mail } from "lucide-react";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import { api, formatApiError } from "../lib/api";
import { useI18n } from "../context/I18nContext";
import { fmtDate, fmtMoney } from "../lib/format";
import { Modal, Field, Input, Textarea, Select, PageHeader, StatusBadge } from "../components/ui-kit";
import { whatsappSurveyUrl } from "../lib/surveyLink";
import { SecureImg } from "../components/SecureImg";
import { ShareReceipt } from "../components/ShareReceipt";

function EmailReceiptButton({ service }) {
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);
  const email = service.client?.email;
  const send = async () => {
    if (!email) return toast.error(t.servicios.no_client_email);
    setBusy(true);
    try {
      const { data } = await api.post(`/services/${service.id}/send-receipt-email`);
      toast.success(`${t.servicios.receipt_sent} ${data.to}`);
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setBusy(false); }
  };
  return (
    <button type="button" onClick={send} disabled={busy} title={email || t.servicios.no_client_email} className={`h-12 px-4 rounded-lg border flex items-center justify-center gap-2 text-sm font-semibold ${email ? "border-sky-800/60 bg-sky-950/30 text-sky-300" : "border-[#262626] text-zinc-600"}`} data-testid="service-email-receipt">
      {busy ? <span className="spinner" /> : <Mail size={14} />}{t.servicios.email_receipt}
    </button>
  );
}

function SurveyButton({ service }) {
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);
  const send = async () => {
    setBusy(true);
    try {
      const { data: settings } = await api.get("/settings");
      if (!settings.survey_url) return toast.error(t.encuestas.missing_url);
      const url = whatsappSurveyUrl({ clientName: service.client?.nombre, clientPhone: service.client?.telefono, folio: service.folio, surveyUrl: settings.survey_url });
      try { await navigator.clipboard.writeText(settings.survey_url); } catch { /* clipboard may be blocked */ }
      toast.success(t.encuestas.link_ready);
      window.open(url, "_blank", "noopener");
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setBusy(false); }
  };
  return (
    <button type="button" onClick={send} disabled={busy} className="h-12 px-4 rounded-lg border border-emerald-800/60 bg-emerald-950/30 text-emerald-300 flex items-center justify-center gap-2 text-sm font-semibold" data-testid="service-send-survey">
      {busy ? <span className="spinner" /> : <MessageSquareHeart size={14} />}{t.servicios.send_survey}
    </button>
  );
}

const STATUS_TONE = {
  lead: "gray", diagnostic: "blue", quoted: "amber", approved: "amber",
  scheduled: "amber", in_progress: "amber", completed: "green",
  delivered: "green", cancelled: "red",
};

function ServicePhotos({ serviceId }) {
  const { t } = useI18n();
  const [items, setItems] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [aiPrompt, setAiPrompt] = useState("");
  const [aiBusy, setAiBusy] = useState(false);
  const inputRef = useRef(null);

  const load = useCallback(async () => {
    if (!serviceId) return;
    try {
      const { data } = await api.get("/files", { params: { service_id: serviceId } });
      setItems(data.items || []);
    } catch (e) { /* ignore */ }
  }, [serviceId]);
  useEffect(() => { load(); }, [load]);

  const onFiles = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setUploading(true);
    for (const file of files) {
      const fd = new FormData();
      fd.append("file", file);
      try {
        await api.post("/files/upload", fd, {
          params: { service_id: serviceId },
          headers: { "Content-Type": "multipart/form-data" },
        });
      } catch (err) { toast.error(formatApiError(err)); }
    }
    setUploading(false);
    if (inputRef.current) inputRef.current.value = "";
    load();
  };

  const generateAI = async () => {
    if (!aiPrompt.trim()) return toast.error("Escribe un prompt");
    setAiBusy(true);
    try {
      await api.post("/ai/images/generate", { prompt: aiPrompt.trim(), service_id: serviceId });
      toast.success("Imagen generada");
      setAiPrompt("");
      load();
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setAiBusy(false); }
  };

  const remove = async (id) => {
    if (!window.confirm(t.common.delete_confirm)) return;
    try { await api.delete(`/files/${id}`); load(); }
    catch (e) { toast.error(formatApiError(e)); }
  };

  return (
    <div className="pt-2 border-t border-[#1a1a1a]">
      <div className="flex items-center justify-between mb-3">
        <label className="text-[11px] uppercase tracking-widest font-mono-tactical text-zinc-500 flex items-center gap-2">
          <ImageIcon size={13} className="text-[#dc2626]" /> Evidencias · se adjuntan al PDF
        </label>
        <label className="armenta-btn-ghost !h-9 !px-3 flex items-center gap-2 cursor-pointer" data-testid="photos-upload-btn">
          <Upload size={13} />
          {uploading ? "Subiendo…" : "Subir foto"}
          <input ref={inputRef} type="file" accept="image/*,application/pdf" multiple className="hidden" onChange={onFiles} data-testid="photos-input" />
        </label>
      </div>

      {/* AI image generation */}
      <div className="flex gap-2 mb-3">
        <input
          type="text"
          className="flex-1 h-10 bg-[#0d0d0d] border border-[#262626] rounded-lg px-3 text-sm text-white outline-none focus:border-[#dc2626]"
          placeholder='Generar con IA (ej. "van Armenta llegando al domicilio al atardecer")'
          value={aiPrompt}
          onChange={(e) => setAiPrompt(e.target.value)}
          data-testid="ai-prompt-input"
        />
        <button type="button" onClick={generateAI} disabled={aiBusy}
          className="h-10 px-4 rounded-lg border border-[#dc262666] bg-[#dc262614] text-[#dc2626] hover:bg-[#dc262622] flex items-center gap-2 text-xs font-semibold uppercase tracking-widest"
          data-testid="ai-generate-btn">
          {aiBusy ? <span className="spinner spinner-gold" /> : <Zap size={13} />}
          {aiBusy ? "Generando…" : "IA"}
        </button>
      </div>

      {items.length === 0 ? (
        <div className="text-xs text-zinc-600 py-3 text-center border border-dashed border-[#262626] rounded-lg">
          Sin fotos de evidencia todavía
        </div>
      ) : (
        <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
          {items.map((f) => (
            <div key={f.id} className="relative group aspect-square rounded-lg overflow-hidden border border-[#262626] bg-[#0d0d0d]">
              {f.content_type?.startsWith("image/") ? (
                <SecureImg fileId={f.id} alt={f.original_filename} className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-xs text-zinc-500 p-2 text-center">{f.original_filename}</div>
              )}
              {f.ai_generated && (
                <span className="absolute top-1 left-1 bg-[#dc2626] text-white text-[8px] uppercase tracking-widest font-mono-tactical px-1.5 py-0.5 rounded">IA</span>
              )}
              <button type="button" onClick={() => remove(f.id)} className="absolute top-1 right-1 bg-black/70 hover:bg-red-900 text-white rounded p-1 opacity-0 group-hover:opacity-100 transition-opacity" data-testid={`photo-rm-${f.id}`}>
                <X size={12} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TuneupPresetPicker({ onApply }) {
  const [catalog, setCatalog] = useState(null);
  const [tier, setTier] = useState("estandar");
  const [cyl, setCyl] = useState(4);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/catalog/tuneups").then((r) => setCatalog(r.data)).catch(() => {});
  }, []);

  if (!catalog) return null;
  const t = catalog.tiers.find((x) => x.key === tier);

  const apply = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/catalog/tuneups/preset-items", { tier, cylinders: cyl });
      onApply(data.items);
      toast.success(`Preset ${data.tier_label} · ${data.cylinders} cil aplicado`);
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <div className="pt-2 border-t border-[#1a1a1a]">
      <div className="flex items-center gap-2 mb-3">
        <Zap size={14} className="text-[#dc2626]" />
        <span className="text-[11px] uppercase tracking-widest font-mono-tactical text-zinc-400">Preset de afinación oficial</span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-2">
        <div className="sm:col-span-2 grid grid-cols-3 gap-1">
          {catalog.tiers.map((it) => (
            <button key={it.key} type="button" onClick={() => setTier(it.key)}
              data-testid={`preset-tier-${it.key}`}
              className={`h-11 rounded-lg border text-[10px] uppercase font-mono-tactical tracking-widest transition-colors ${tier === it.key ? "text-white" : "text-zinc-500 hover:text-white"}`}
              style={{ borderColor: tier === it.key ? it.color : "#262626", background: tier === it.key ? `${it.color}22` : "#0d0d0d" }}
            >
              {it.label.replace("Calidad ", "")}
            </button>
          ))}
        </div>
        <div className="grid grid-cols-3 gap-1">
          {catalog.cylinders.map((n) => (
            <button key={n} type="button" onClick={() => setCyl(n)}
              data-testid={`preset-cyl-${n}`}
              className={`h-11 rounded-lg border text-xs font-mono-tactical ${cyl === n ? "border-[#dc2626] bg-[#dc262614] text-white" : "border-[#262626] bg-[#0d0d0d] text-zinc-500 hover:text-white"}`}
            >{n} CIL</button>
          ))}
        </div>
        <button type="button" onClick={apply} disabled={busy} data-testid="preset-apply"
          className="h-11 px-4 rounded-lg border border-[#dc262666] bg-[#dc262614] text-[#dc2626] hover:bg-[#dc262622] flex items-center justify-center gap-2 text-xs font-semibold uppercase tracking-widest">
          {busy ? <span className="spinner spinner-gold" /> : <Zap size={13} />}
          Aplicar · ${t.prices[cyl].toLocaleString()} MXN
        </button>
      </div>
      <div className="text-[10px] font-mono-tactical uppercase tracking-widest text-zinc-600 mt-2">
        Bujías {t.spark_plug.material} · Aceite {t.spark_plug.oil} · {t.includes.slice(0, 3).join(" · ")}
      </div>
    </div>
  );
}

function ItemsEditor({ items, setItems, taxRate, setTaxRate }) {
  const { t } = useI18n();
  const update = (i, k, v) => {
    const next = [...items];
    next[i] = { ...next[i], [k]: k === "description" || k === "is_labor" ? v : Number(v) || 0 };
    setItems(next);
  };
  const add = () => setItems([...items, { description: "", quantity: 1, unit_price: 0, cost: 0, is_labor: false }]);
  const rm = (i) => setItems(items.filter((_, idx) => idx !== i));

  const subtotal = items.reduce((s, it) => s + (it.quantity || 0) * (it.unit_price || 0), 0);
  const cost = items.reduce((s, it) => s + (it.quantity || 0) * (it.cost || 0), 0);
  const tax = subtotal * (taxRate || 0);
  const total = subtotal + tax;
  const profit = subtotal - cost;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-[11px] uppercase tracking-widest font-mono-tactical text-zinc-500">{t.common.description}</label>
        <button type="button" onClick={add} className="armenta-btn-ghost !h-8 !px-3 flex items-center gap-1.5" data-testid="items-add"><Plus size={12} />{t.common.add_item}</button>
      </div>
      {items.length === 0 && <div className="text-xs text-zinc-600 py-3 text-center border border-dashed border-[#262626] rounded-lg">{t.common.no_items}</div>}
      {items.map((it, i) => (
        <div key={i} className="grid grid-cols-12 gap-2 items-center" data-testid={`item-row-${i}`}>
          <input className="col-span-12 sm:col-span-5 h-10 bg-[#0d0d0d] border border-[#262626] rounded-lg px-3 text-sm text-white outline-none focus:border-[#dc2626]" placeholder={t.common.description} value={it.description} onChange={(e) => update(i, "description", e.target.value)} data-testid={`item-desc-${i}`} />
          <input className="col-span-3 sm:col-span-1 h-10 bg-[#0d0d0d] border border-[#262626] rounded-lg px-2 text-sm text-white text-right outline-none focus:border-[#dc2626]" type="number" step="0.01" placeholder="1" value={it.quantity} onChange={(e) => update(i, "quantity", e.target.value)} data-testid={`item-qty-${i}`} />
          <input className="col-span-4 sm:col-span-2 h-10 bg-[#0d0d0d] border border-[#262626] rounded-lg px-2 text-sm text-white text-right outline-none focus:border-[#dc2626]" type="number" step="0.01" placeholder="$0" value={it.unit_price} onChange={(e) => update(i, "unit_price", e.target.value)} data-testid={`item-price-${i}`} />
          <input className="col-span-4 sm:col-span-2 h-10 bg-[#0d0d0d] border border-[#262626] rounded-lg px-2 text-sm text-white text-right outline-none focus:border-[#dc2626]" type="number" step="0.01" placeholder="$costo" value={it.cost} onChange={(e) => update(i, "cost", e.target.value)} data-testid={`item-cost-${i}`} />
          <div className="col-span-11 sm:col-span-1 text-right text-xs text-white font-mono-tactical">{fmtMoney((it.quantity || 0) * (it.unit_price || 0))}</div>
          <button type="button" onClick={() => rm(i)} className="col-span-1 text-zinc-500 hover:text-red-400" data-testid={`item-rm-${i}`}><Trash2 size={14} /></button>
        </div>
      ))}
      <div className="pt-3 mt-3 border-t border-[#1a1a1a] grid grid-cols-2 gap-3 text-sm">
        <div className="text-zinc-500 font-mono-tactical uppercase tracking-widest text-[10px]">{t.common.subtotal}</div>
        <div className="text-right text-white font-mono-tactical">{fmtMoney(subtotal)}</div>
        <div className="text-zinc-500 font-mono-tactical uppercase tracking-widest text-[10px] flex items-center gap-2">
          {t.common.tax}
          <input type="number" step="0.01" value={taxRate} onChange={(e) => setTaxRate(Number(e.target.value) || 0)} className="w-16 h-7 bg-[#0d0d0d] border border-[#262626] rounded px-2 text-xs text-white text-right outline-none focus:border-[#dc2626]" data-testid="items-tax-rate" />
        </div>
        <div className="text-right text-white font-mono-tactical">{fmtMoney(tax)}</div>
        <div className="text-[#dc2626] font-mono-tactical uppercase tracking-widest text-[11px] font-bold">{t.common.total}</div>
        <div className="text-right text-white font-mono-tactical text-lg font-bold">{fmtMoney(total)}</div>
        <div className="text-zinc-600 font-mono-tactical uppercase tracking-widest text-[10px]">{t.common.profit}</div>
        <div className="text-right text-emerald-400 font-mono-tactical">{fmtMoney(profit)}</div>
      </div>
    </div>
  );
}

function ServiceForm({ initial, clients, vehicles, technicians, onClose, onSaved }) {
  const { t } = useI18n();
  const [f, setF] = useState({
    client_id: initial?.client_id || clients[0]?.id || "",
    vehicle_id: initial?.vehicle_id || "",
    technician_id: initial?.technician_id || "",
    type: initial?.type || "mantenimiento",
    symptoms: initial?.symptoms || "",
    diagnosis: initial?.diagnosis || "",
    requested_service: initial?.requested_service || "",
    address: initial?.address || "",
    scheduled_at: initial?.scheduled_at || "",
    status: initial?.status || "lead",
    recommendations: initial?.recommendations || "",
    notes: initial?.notes || "",
    client_name: initial?.client_name || "",
    client_phone: initial?.client_phone || "",
  });
  const [items, setItems] = useState(initial?.items || []);
  const [taxRate, setTaxRate] = useState(initial?.tax_rate ?? 0.16);
  const [saving, setSaving] = useState(false);
  const [surveyUrl, setSurveyUrl] = useState("");
  useEffect(() => { api.get("/settings").then((r) => setSurveyUrl(r.data.survey_url || "")).catch(() => {}); }, []);
  const editing = !!initial?.id;
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }));

  const filteredVehicles = useMemo(() => vehicles.filter((v) => v.client_id === f.client_id), [vehicles, f.client_id]);

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    const payload = { ...f, items, tax_rate: taxRate };
    if (!payload.vehicle_id) delete payload.vehicle_id;
    if (!payload.client_id) delete payload.client_id;
    if (!payload.technician_id) delete payload.technician_id;
    if (!payload.scheduled_at) delete payload.scheduled_at;
    const becomesDelivered = editing && f.status === "delivered" && initial.status !== "delivered";
    let waWindow = null;
    if (becomesDelivered && surveyUrl) {
      const client = clients.find((c) => c.id === f.client_id);
      waWindow = window.open(whatsappSurveyUrl({ clientName: client?.nombre || f.client_name, clientPhone: client?.telefono || f.client_phone, folio: initial.folio, surveyUrl }), "_blank", "noopener");
    }
    try {
      editing
        ? await api.patch(`/services/${initial.id}`, payload)
        : await api.post("/services", payload);
      toast.success(t.servicios.saved);
      if (becomesDelivered && surveyUrl) toast.success(t.servicios.survey_auto);
      onSaved();
    } catch (e2) { if (waWindow) waWindow.close(); toast.error(formatApiError(e2)); }
    finally { setSaving(false); }
  };

  const doDelete = async () => {
    if (!window.confirm(t.common.delete_confirm)) return;
    try { await api.delete(`/services/${initial.id}`); toast.success(t.servicios.deleted); onSaved(); }
    catch (e2) { toast.error(formatApiError(e2)); }
  };

  const typeOptions = Object.entries(t.servicios.form.types).map(([k, v]) => ({ value: k, label: v }));
  const statusOptions = Object.entries(t.servicios.statuses).map(([k, v]) => ({ value: k, label: v }));

  return (
    <Modal title={editing ? t.servicios.edit : t.servicios.new} onClose={onClose} testId="service-form" size="xl">
      <form onSubmit={submit} className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Field label={t.common.client}>
            <Select testId="service-client" value={f.client_id} onChange={(v) => { set("client_id")(v); set("vehicle_id")(""); }} options={[{ value: "", label: t.servicios.form.walk_in }, ...clients.map((c) => ({ value: c.id, label: c.nombre }))]} />
          </Field>
          <Field label={t.common.vehicle}>
            <Select testId="service-vehicle" value={f.vehicle_id} onChange={set("vehicle_id")} options={[{ value: "", label: "—" }, ...filteredVehicles.map((v) => ({ value: v.id, label: `${v.year || ""} ${v.make} ${v.model} · ${v.plates || ""}` }))]} />
          </Field>
          <Field label={t.common.technician}>
            <Select testId="service-tech" value={f.technician_id} onChange={set("technician_id")} options={[{ value: "", label: "—" }, ...technicians.map((tc) => ({ value: tc.id, label: tc.name }))]} />
          </Field>
        </div>
        {!f.client_id && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3" data-testid="service-walkin-fields">
            <Field label={t.servicios.form.client_name}><Input testId="service-client-name" value={f.client_name} onChange={set("client_name")} placeholder="Ej. Donato Reyes" /></Field>
            <Field label={t.common.phone}><Input testId="service-client-phone" value={f.client_phone} onChange={set("client_phone")} placeholder="656 000 0000" /></Field>
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Field label={t.servicios.form.type}><Select testId="service-type" value={f.type} onChange={set("type")} options={typeOptions} /></Field>
          <Field label={t.common.status}><Select testId="service-status" value={f.status} onChange={set("status")} options={statusOptions} /></Field>
          <Field label={t.servicios.form.scheduled_at}><Input testId="service-scheduled" type="date" value={f.scheduled_at} onChange={set("scheduled_at")} /></Field>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label={t.servicios.form.symptoms}><Textarea testId="service-symptoms" value={f.symptoms} onChange={set("symptoms")} rows={2} /></Field>
          <Field label={t.servicios.form.diagnosis}><Textarea testId="service-diagnosis" value={f.diagnosis} onChange={set("diagnosis")} rows={2} /></Field>
        </div>
        <Field label={t.servicios.form.address}><Input testId="service-address" value={f.address} onChange={set("address")} /></Field>
        <div className="pt-2 border-t border-[#1a1a1a]">
          <ItemsEditor items={items} setItems={setItems} taxRate={taxRate} setTaxRate={setTaxRate} />
        </div>
        <TuneupPresetPicker onApply={(preset) => setItems([...(items || []), ...preset])} />
        {editing && <ServicePhotos serviceId={initial.id} />}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label={t.servicios.form.recommendations}><Textarea testId="service-reco" value={f.recommendations} onChange={set("recommendations")} rows={2} /></Field>
          <Field label={t.common.description}><Textarea testId="service-notes" value={f.notes} onChange={set("notes")} rows={2} /></Field>
        </div>
        <div className="flex flex-col sm:flex-row gap-2 pt-1">
          <button type="submit" className="armenta-btn-primary flex-1 !h-12" disabled={saving} data-testid="service-submit">{saving ? t.common.saving : t.common.save}</button>
          {editing && <Link to={`/recibo/servicio/${initial.id}`} className="h-12 px-4 rounded-lg border border-[#dc262666] bg-[#dc262614] text-[#dc2626] hover:bg-[#dc262622] flex items-center justify-center gap-2 text-sm font-semibold" data-testid="service-view-receipt"><ReceiptIcon size={14} />{t.servicios.view_receipt}</Link>}
          {editing && <SurveyButton service={initial} />}
          {editing && <ShareReceipt kind="servicio" id={initial.id} folio={initial.folio} clientName={initial.client?.nombre || f.client_name} clientPhone={initial.client?.telefono || f.client_phone} />}
          {editing && <EmailReceiptButton service={initial} />}
          {editing && <button type="button" onClick={doDelete} className="h-12 px-4 rounded-lg border border-red-900/60 bg-red-950/30 text-red-300 flex items-center gap-2 text-sm"><Trash2 size={14} />{t.common.delete}</button>}
          <button type="button" onClick={onClose} className="armenta-btn-ghost !h-12 !px-4">{t.common.cancel}</button>
        </div>
      </form>
    </Modal>
  );
}

export default function Servicios() {
  const { t } = useI18n();
  const [items, setItems] = useState([]);
  const [clients, setClients] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [techs, setTechs] = useState([]);
  const [statusFilter, setStatusFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = statusFilter !== "all" ? { status: statusFilter } : {};
      const [s, c, v, tc] = await Promise.all([
        api.get("/services", { params }),
        api.get("/clients", { params: { limit: 500 } }),
        api.get("/vehicles"),
        api.get("/technicians"),
      ]);
      setItems(s.data.items || []);
      setClients(c.data.items || []);
      setVehicles(v.data.items || []);
      setTechs(tc.data.items || []);
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setLoading(false); }
  }, [statusFilter]);

  useEffect(() => { load(); }, [load]);

  const openEdit = async (s) => {
    try {
      const { data } = await api.get(`/services/${s.id}`);
      setEditing(data); setFormOpen(true);
    } catch (e) { toast.error(formatApiError(e)); }
  };

  const clientName = (s) => clients.find((c) => c.id === s.client_id)?.nombre || s.client_name || "—";
  const vehicleLabel = (id) => { const v = vehicles.find((x) => x.id === id); return v ? `${v.year || ""} ${v.make} ${v.model}`.trim() : ""; };

  const statusFilters = ["all", ...Object.keys(t.servicios.statuses)];

  return (
    <div className="space-y-5" data-testid="servicios-page">
      <PageHeader
        title={t.servicios.title}
        subtitle={t.servicios.subtitle}
        action={<button onClick={() => { setEditing(null); setFormOpen(true); }} className="armenta-btn-primary !w-auto !h-12 !px-5 flex items-center gap-2" data-testid="servicios-new"><Plus size={16} />{t.servicios.new}</button>}
      />
      <div className="card-tactical p-3 flex gap-2 overflow-x-auto">
        {statusFilters.map((s) => (
          <button key={s} onClick={() => setStatusFilter(s)} className={`h-10 px-3 rounded-lg border text-[10px] uppercase font-mono-tactical tracking-widest whitespace-nowrap ${statusFilter === s ? "border-[#dc2626] bg-[#dc262614] text-white" : "border-[#262626] bg-[#0d0d0d] text-zinc-500 hover:text-white"}`} data-testid={`servicios-filter-${s}`}>
            {s === "all" ? "Todos" : t.servicios.statuses[s]}
          </button>
        ))}
      </div>

      {loading ? <div className="card-tactical p-10 flex justify-center"><span className="spinner spinner-gold" /></div>
        : items.length === 0 ? <div className="card-tactical p-8 text-center"><Wrench size={28} className="text-[#dc2626] mx-auto mb-3" /><p className="text-sm text-zinc-400">{t.servicios.empty}</p></div>
        : <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {items.map((s) => (
              <button key={s.id} onClick={() => openEdit(s)} className="card-tactical p-4 text-left hover:border-[#dc262666]" data-testid={`service-card-${s.id}`}>
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="min-w-0">
                    <div className="font-mono-tactical text-[10px] uppercase tracking-widest text-[#dc2626]">{s.folio}</div>
                    <div className="text-white font-semibold truncate">{clientName(s)}</div>
                    <div className="text-xs text-zinc-500 truncate">{vehicleLabel(s.vehicle_id)}</div>
                  </div>
                  <StatusBadge label={t.servicios.statuses[s.status]} tone={STATUS_TONE[s.status]} />
                </div>
                <div className="mt-3 pt-3 border-t border-[#1a1a1a] flex justify-between items-end text-xs">
                  <span className="text-zinc-500">{fmtDate(s.scheduled_at) || fmtDate(s.created_at)}</span>
                  <span className="text-white font-mono-tactical font-bold">{fmtMoney(s.total)}</span>
                </div>
                {s.balance > 0 && <div className="mt-1 text-[10px] font-mono-tactical uppercase tracking-widest text-amber-400">Saldo: {fmtMoney(s.balance)}</div>}
              </button>
            ))}
          </div>
      }
      {formOpen && <ServiceForm initial={editing} clients={clients} vehicles={vehicles} technicians={techs} onClose={() => { setFormOpen(false); setEditing(null); }} onSaved={() => { setFormOpen(false); setEditing(null); load(); }} />}
    </div>
  );
}
