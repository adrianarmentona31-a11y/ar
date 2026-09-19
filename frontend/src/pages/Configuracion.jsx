import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { Save } from "lucide-react";
import { api, formatApiError } from "../lib/api";
import { useI18n } from "../context/I18nContext";
import { PageHeader, Field, Input, Textarea } from "../components/ui-kit";
import { TeamPanel } from "../components/TeamPanel";
import { useAuth } from "../context/AuthContext";

export default function Configuracion() {
  const { t } = useI18n();
  const { user } = useAuth();
  const [f, setF] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try { const { data } = await api.get("/settings"); setF(data); }
      catch (e) { toast.error(formatApiError(e)); }
    })();
  }, []);
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }));

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const { data } = await api.patch("/settings", {
        ...f,
        tax_rate: Number(f.tax_rate) || 0,
        payment_terms_days: Number(f.payment_terms_days) || 0,
      });
      setF(data);
      toast.success(t.common.settings_saved);
    } catch (e2) { toast.error(formatApiError(e2)); }
    finally { setSaving(false); }
  };

  if (!f) return <div className="card-tactical p-10 flex justify-center"><span className="spinner spinner-gold" /></div>;

  return (
    <div className="space-y-5" data-testid="config-page">
      <PageHeader title={t.configuracion.title} subtitle={t.configuracion.subtitle} />
      <form onSubmit={save} className="card-tactical p-5 space-y-4 max-w-3xl">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label={t.configuracion.company_name} required><Input testId="cfg-name" value={f.company_name} onChange={set("company_name")} /></Field>
          <Field label={t.configuracion.company_rfc}><Input testId="cfg-rfc" value={f.company_rfc} onChange={set("company_rfc")} /></Field>
          <Field label={t.configuracion.company_phone}><Input testId="cfg-phone" value={f.company_phone} onChange={set("company_phone")} /></Field>
          <Field label={t.configuracion.company_email}><Input testId="cfg-email" type="email" value={f.company_email} onChange={set("company_email")} /></Field>
        </div>
        <Field label={t.configuracion.company_address}><Input testId="cfg-address" value={f.company_address} onChange={set("company_address")} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t.configuracion.tax_rate}><Input testId="cfg-tax" type="number" value={f.tax_rate} onChange={set("tax_rate")} /></Field>
          <Field label={t.configuracion.currency}><Input testId="cfg-currency" value={f.currency} onChange={set("currency")} /></Field>
        </div>
        <Field label={t.configuracion.footer_note}><Textarea testId="cfg-footer" value={f.footer_note} onChange={set("footer_note")} rows={3} /></Field>
        <Field label={t.configuracion.survey_url}><Input testId="cfg-survey-url" value={f.survey_url} onChange={set("survey_url")} placeholder="https://docs.google.com/forms/..." /></Field>
        <div className="pt-2 font-mono-tactical text-[10px] uppercase tracking-widest text-[#dc2626]">{t.transferencia.title}</div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label={t.transferencia.holder}><Input testId="cfg-bank-holder" value={f.bank_holder} onChange={set("bank_holder")} /></Field>
          <Field label={t.transferencia.bank}><Input testId="cfg-bank-name" value={f.bank_name} onChange={set("bank_name")} placeholder="BBVA, Banorte…" /></Field>
          <Field label={t.transferencia.card}><Input testId="cfg-bank-card" value={f.bank_card} onChange={set("bank_card")} placeholder="16 dígitos" /></Field>
          <Field label="CLABE"><Input testId="cfg-bank-clabe" value={f.bank_clabe} onChange={set("bank_clabe")} placeholder="18 dígitos" /></Field>
        </div>
        <button type="submit" className="armenta-btn-primary !w-auto !h-12 !px-6 flex items-center gap-2" disabled={saving} data-testid="cfg-save">
          <Save size={14} />{saving ? t.common.saving : t.configuracion.save}
        </button>
      </form>
      {user?.role === "admin" && <TeamPanel />}
    </div>
  );
}
