import React, { useEffect, useState } from "react";
import { CreditCard, Landmark, ShieldCheck, Copy, Send, Settings as SettingsIcon } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api, formatApiError } from "../lib/api";
import { useI18n } from "../context/I18nContext";
import "../transferencia.css";

function Row({ icon: Icon, label, value, hint, testId, onCopy }) {
  return (
    <div className="tr-row" data-testid={testId}>
      <div className="tr-icon"><Icon size={26} /></div>
      <div className="tr-field">
        <div className="tr-label">{label}</div>
        <button type="button" className="tr-value" onClick={onCopy} title="Copiar" data-testid={`${testId}-value`}>
          <span>{value || "—"}</span><Copy size={14} className="tr-copy" />
        </button>
        <div className="tr-hint">{hint}</div>
      </div>
    </div>
  );
}

export default function Transferencia() {
  const { t } = useI18n();
  const tr = t.transferencia;
  const navigate = useNavigate();
  const [s, setS] = useState(null);
  const [phone, setPhone] = useState("");

  useEffect(() => { api.get("/settings").then((r) => setS(r.data)).catch((e) => toast.error(formatApiError(e))); }, []);

  const copy = async (v, what) => { if (!v) return; await navigator.clipboard.writeText(v); toast.success(`${what} ${tr.copied}`); };
  const fmtCard = (v) => (v || "").replace(/\s+/g, "").replace(/(.{4})/g, "$1 ").trim();
  const message = () => {
    const lines = [`*ARMENTA'S MOTORS · ${tr.title}*`, `${tr.holder}: ${s.bank_holder}`];
    if (s.bank_name) lines.push(`${tr.bank}: ${s.bank_name}`);
    if (s.bank_card) lines.push(`${tr.card}: ${fmtCard(s.bank_card)}`);
    if (s.bank_clabe) lines.push(`CLABE: ${s.bank_clabe}`);
    lines.push("", tr.verify, "", tr.thanks_for);
    return lines.join("\n");
  };
  const sendWa = () => window.open(`https://wa.me/${phone.replace(/\D/g, "")}?text=${encodeURIComponent(message())}`, "_blank", "noopener");

  if (!s) return <div className="min-h-[60vh] flex items-center justify-center"><span className="spinner spinner-gold" /></div>;
  const configured = s.bank_card || s.bank_clabe;

  return (
    <div className="space-y-4" data-testid="transferencia-page">
      <div className="flex flex-wrap gap-2 items-center justify-between">
        <div className="flex gap-2 items-center">
          <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder={tr.phone_placeholder} className="h-11 px-3.5 rounded-lg bg-[#0d0d0d] border border-[#262626] text-sm text-white outline-none focus:border-[#dc2626] w-56" data-testid="transfer-phone" />
          <button onClick={sendWa} disabled={!configured} className="h-11 px-4 rounded-lg border border-emerald-800/60 bg-emerald-950/30 text-emerald-300 flex items-center gap-2 text-sm font-semibold disabled:opacity-40" data-testid="transfer-send-wa"><Send size={14} />WhatsApp</button>
          <button onClick={() => copy(message(), tr.title)} disabled={!configured} className="armenta-btn-ghost !h-11 !px-4 flex items-center gap-2" data-testid="transfer-copy-all"><Copy size={14} />{tr.copy_all}</button>
        </div>
        <button onClick={() => navigate("/configuracion")} className="armenta-btn-ghost !h-11 !px-4 flex items-center gap-2" data-testid="transfer-edit"><SettingsIcon size={14} />{tr.edit}</button>
      </div>

      <div className="tr-card" data-testid="transfer-card">
        <div className="tr-glow" />
        <img src="/armenta_wordmark.png" alt="ARMENTA'S MOTORS" className="tr-logo" draggable={false} />
        <div className="tr-kicker">{tr.kicker}</div>
        <h1 className="tr-title">{tr.title_big}</h1>
        <div className="tr-rule" />
        <div className="tr-thanks">{tr.thanks}</div>
        <div className="tr-holder">
          <div className="tr-holder-script">{(s.bank_holder || "").split(" ")[0]}</div>
          <div className="tr-holder-name">{(s.bank_holder || "").split(" ").slice(1).join(" ") || s.bank_holder}</div>
          <div className="tr-holder-caption">{tr.holder}{s.bank_name ? ` · ${s.bank_name}` : ""}</div>
        </div>
        <div className="tr-panel">
          <Row icon={CreditCard} label={tr.card} value={fmtCard(s.bank_card)} hint={tr.card_hint} testId="transfer-card-number" onCopy={() => copy(s.bank_card, tr.card)} />
          <div className="tr-sep" />
          <Row icon={Landmark} label="CLABE INTERBANCARIA" value={s.bank_clabe} hint={tr.clabe_hint} testId="transfer-clabe" onCopy={() => copy(s.bank_clabe, "CLABE")} />
        </div>
        <div className="tr-important">
          <div className="tr-shield"><ShieldCheck size={30} /></div>
          <div>
            <div className="tr-important-label">{tr.important}</div>
            <div className="tr-important-text">{tr.verify}</div>
          </div>
        </div>
        <div className="tr-gracias">¡Gracias!</div>
        <div className="tr-footer">{tr.thanks_for}</div>
      </div>
    </div>
  );
}
