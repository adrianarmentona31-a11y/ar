import React, { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Printer, ArrowLeft, Download } from "lucide-react";
import { toast } from "sonner";
import { api, formatApiError } from "../lib/api";
import { useI18n } from "../context/I18nContext";
import { fmtMoney, fmtDate } from "../lib/format";
import { BrandMark } from "../components/BrandMark";
import { ArmentaWordmark } from "../components/ArmentaWordmark";

/**
 * Receipt / sales preview. Works for both quotes and services.
 * Route: /recibo/:kind/:id  (kind = "cotizacion" | "servicio")
 * Uses window.print — hides nav/print-only formatting via .print-hidden / .print-only classes.
 */
export default function Recibo() {
  const { t, locale } = useI18n();
  const { kind, id } = useParams();
  const navigate = useNavigate();
  const [doc, setDoc] = useState(null);
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const downloadPdf = async () => {
    setDownloading(true);
    try {
      const res = await api.get(`/receipts/${kind}/${id}/pdf`, {
        responseType: "blob",
      });
      const blob = new Blob([res.data], { type: "application/pdf" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      const suggested = res.headers?.["x-filename"] || `${doc?.folio || "recibo"}.pdf`;
      link.download = suggested;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => window.URL.revokeObjectURL(url), 250);
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setDownloading(false);
    }
  };

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const endpoint = kind === "cotizacion" ? `/quotes/${id}` : `/services/${id}`;
        const [{ data: d }, { data: s }] = await Promise.all([
          api.get(endpoint),
          api.get("/settings").catch(() => ({ data: {} })),
        ]);
        setDoc(d);
        setSettings(s);
      } catch (e) {
        setNotFound(true);
        toast.error(formatApiError(e));
      } finally {
        setLoading(false);
      }
    })();
  }, [kind, id]);

  const currency = settings?.currency || "MXN";
  const money = (v) => fmtMoney(v, currency, locale === "es" ? "es-MX" : "en-US");
  const isQuote = kind === "cotizacion";

  const statusLabel = useMemo(() => {
    if (!doc) return "";
    if (isQuote) return t.cotizaciones.statuses[doc.status] || doc.status;
    return t.servicios.statuses[doc.status] || doc.status;
  }, [doc, isQuote, t]);

  if (loading) return <div className="min-h-[60vh] flex items-center justify-center"><span className="spinner spinner-gold" /></div>;
  if (notFound || !doc) {
    return (
      <div className="card-tactical p-8 max-w-lg mx-auto text-center">
        <p className="text-sm text-zinc-400 mb-4">{t.recibo.not_found}</p>
        <button onClick={() => navigate(-1)} className="armenta-btn-ghost !h-11 !px-4 mx-auto flex items-center gap-2"><ArrowLeft size={14} />{t.recibo.back}</button>
      </div>
    );
  }

  const client = doc.client || {};
  const vehicle = doc.vehicle;
  const technician = doc.technician;

  return (
    <div className="max-w-4xl mx-auto space-y-4" data-testid="recibo-page">
      {/* Toolbar (screen only) */}
      <div className="flex items-center justify-between print-hidden gap-2 flex-wrap">
        <button onClick={() => navigate(-1)} className="armenta-btn-ghost !h-11 !px-4 flex items-center gap-2" data-testid="recibo-back"><ArrowLeft size={14} />{t.recibo.back}</button>
        <div className="flex items-center gap-2">
          <button onClick={() => window.print()} className="armenta-btn-ghost !h-11 !px-4 flex items-center gap-2" data-testid="recibo-print"><Printer size={14} />{t.recibo.print}</button>
          <button onClick={downloadPdf} disabled={downloading} className="armenta-btn-primary !w-auto !h-11 !px-5 flex items-center gap-2" data-testid="recibo-download-pdf">
            {downloading ? <span className="spinner" /> : <Download size={14} />}
            {downloading ? t.recibo.generating_pdf : t.recibo.download_pdf}
          </button>
        </div>
      </div>

      {/* Paper */}
      <div id="receipt-paper" className="receipt-paper" data-testid="recibo-paper">
        {/* Header */}
        <div className="receipt-header">
          <div className="flex items-center gap-5">
            <BrandMark size={72} />
            <div>
              <ArmentaWordmark width={220} />
              <div className="receipt-meta">
                {settings?.company_address && <div>{settings.company_address}</div>}
                {settings?.company_phone && <div>Tel. {settings.company_phone}</div>}
                {settings?.company_email && <div>{settings.company_email}</div>}
                {settings?.company_rfc && <div>RFC: {settings.company_rfc}</div>}
              </div>
            </div>
          </div>
          <div className="receipt-folio">
            <div className="receipt-folio-label">{isQuote ? "COTIZACIÓN" : "ORDEN DE SERVICIO"}</div>
            <div className="receipt-folio-value">{doc.folio}</div>
            <div className="receipt-status">{statusLabel}</div>
          </div>
        </div>

        <div className="receipt-divider" />

        {/* Meta grid */}
        <div className="receipt-grid">
          <div>
            <div className="receipt-label">{t.recibo.issued_to}</div>
            <div className="receipt-value">{client.nombre || "—"}</div>
            {client.telefono && <div className="receipt-sub">{client.telefono}</div>}
            {client.email && <div className="receipt-sub">{client.email}</div>}
            {client.direccion && <div className="receipt-sub">{client.direccion}</div>}
          </div>
          {vehicle && (
            <div>
              <div className="receipt-label">{t.recibo.vehicle}</div>
              <div className="receipt-value">{[vehicle.year, vehicle.make, vehicle.model].filter(Boolean).join(" ")}</div>
              {vehicle.vin && <div className="receipt-sub">VIN: {vehicle.vin}</div>}
              {vehicle.plates && <div className="receipt-sub">Placas: {vehicle.plates}</div>}
              {vehicle.mileage != null && <div className="receipt-sub">KM: {Number(vehicle.mileage).toLocaleString()}</div>}
              {vehicle.engine && <div className="receipt-sub">Motor: {vehicle.engine}</div>}
            </div>
          )}
          <div>
            <div className="receipt-label">{t.recibo.date}</div>
            <div className="receipt-value">{fmtDate(doc.created_at, locale === "es" ? "es-MX" : "en-US")}</div>
            {isQuote && doc.expires_at && (
              <>
                <div className="receipt-label mt-3">{t.recibo.valid_until}</div>
                <div className="receipt-sub">{fmtDate(doc.expires_at)}</div>
              </>
            )}
            {technician && (
              <>
                <div className="receipt-label mt-3">{t.recibo.technician}</div>
                <div className="receipt-sub">{technician.name}</div>
              </>
            )}
          </div>
        </div>

        {/* Items table */}
        <table className="receipt-table">
          <thead>
            <tr>
              <th className="left">{t.recibo.concept}</th>
              <th className="right">{t.recibo.qty}</th>
              <th className="right">{t.recibo.unit}</th>
              <th className="right">{t.recibo.amount}</th>
            </tr>
          </thead>
          <tbody>
            {(doc.items || []).length === 0 ? (
              <tr><td colSpan={4} className="empty">Sin conceptos</td></tr>
            ) : (
              (doc.items || []).map((it, i) => (
                <tr key={i}>
                  <td className="left">
                    <div className="item-desc">{it.description}</div>
                    {it.is_labor && <div className="item-tag">Mano de obra</div>}
                  </td>
                  <td className="right">{it.quantity}</td>
                  <td className="right">{money(it.unit_price)}</td>
                  <td className="right amount">{money((it.quantity || 0) * (it.unit_price || 0))}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        {/* Totals */}
        <div className="receipt-totals">
          <div className="totals-row">
            <span>{t.recibo.subtotal}</span>
            <span>{money(doc.subtotal)}</span>
          </div>
          <div className="totals-row">
            <span>{t.recibo.tax} ({Math.round((doc.tax_rate || 0) * 100)}%)</span>
            <span>{money(doc.tax)}</span>
          </div>
          <div className="totals-row grand">
            <span>{t.recibo.total}</span>
            <span>{money(doc.total)}</span>
          </div>
          {!isQuote && (
            <>
              <div className="totals-row">
                <span>{t.recibo.paid}</span>
                <span>{money(doc.paid || 0)}</span>
              </div>
              <div className={`totals-row balance ${doc.balance > 0 ? "outstanding" : "settled"}`}>
                <span>{t.recibo.balance}</span>
                <span>{money(doc.balance || 0)}</span>
              </div>
            </>
          )}
        </div>

        {/* Notes */}
        {(doc.notes || (isQuote === false && doc.recommendations)) && (
          <div className="receipt-notes">
            {doc.notes && (
              <>
                <div className="receipt-label">{t.recibo.notes}</div>
                <p className="receipt-body">{doc.notes}</p>
              </>
            )}
            {!isQuote && doc.recommendations && (
              <>
                <div className="receipt-label mt-3">Recomendaciones</div>
                <p className="receipt-body">{doc.recommendations}</p>
              </>
            )}
          </div>
        )}

        {/* Signature block */}
        <div className="receipt-signatures">
          <div className="sig">
            <div className="sig-line" />
            <div className="sig-caption">{t.recibo.auth}</div>
          </div>
          <div className="sig">
            <div className="sig-line" />
            <div className="sig-caption">Cliente / {client.nombre || ""}</div>
          </div>
        </div>

        <div className="receipt-footer">
          {settings?.footer_note || t.recibo.thanks}
        </div>
      </div>
    </div>
  );
}
