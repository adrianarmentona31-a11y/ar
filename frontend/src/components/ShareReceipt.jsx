import React, { useState } from "react";
import { Share2, Send, MessageCircle, Copy } from "lucide-react";
import { toast } from "sonner";
import { api, formatApiError } from "../lib/api";
import { useI18n } from "../context/I18nContext";

export function ShareReceipt({ kind, id, folio, clientName, clientPhone, compact = false }) {
  const { t } = useI18n();
  const tr = t.share;
  const [open, setOpen] = useState(false);
  const [link, setLink] = useState(null);
  const [busy, setBusy] = useState(false);

  const getLink = async () => {
    if (link) return link;
    const { data } = await api.get(`/receipts/${kind}/${id}/share-link`);
    const url = `${window.location.origin}${data.path}`;
    setLink(url);
    return url;
  };
  const message = (url) => `${tr.msg_prefix}${clientName ? ` ${clientName.split(" ")[0]}` : ""}, ${tr.msg_body} ${folio}: ${url}\n\n${tr.msg_sign}`;

  const start = async () => {
    setBusy(true);
    try {
      const url = await getLink();
      if (navigator.share && /Android|iPhone|iPad/i.test(navigator.userAgent)) {
        try { await navigator.share({ title: `${folio} · Armenta's Motors`, text: message(url) }); return; } catch (e) { if (e?.name === "AbortError") return; }
      }
      setOpen((o) => !o);
    } catch (e) { toast.error(formatApiError(e)); } finally { setBusy(false); }
  };
  const wa = () => window.open(`https://wa.me/${(clientPhone || "").replace(/\D/g, "")}?text=${encodeURIComponent(message(link))}`, "_blank", "noopener");
  const messenger = () => {
    const isMobile = /Android|iPhone|iPad/i.test(navigator.userAgent);
    window.open(isMobile ? `fb-messenger://share/?link=${encodeURIComponent(link)}` : `https://www.facebook.com/dialog/send?link=${encodeURIComponent(link)}&redirect_uri=${encodeURIComponent(window.location.origin)}&app_id=0`, "_blank", "noopener");
    navigator.clipboard?.writeText(message(link)).then(() => toast.success(tr.copied_msg)).catch(() => {});
  };
  const copy = async () => { await navigator.clipboard.writeText(link); toast.success(tr.copied); };

  const btnCls = compact ? "h-9 px-3 rounded-lg border border-[#262626] text-zinc-300 hover:text-white flex items-center gap-1.5 text-xs" : "armenta-btn-ghost !h-11 !px-4 flex items-center gap-2";
  return (
    <div className="relative" data-testid={`share-${kind}-${id}`}>
      <button type="button" onClick={start} disabled={busy} className={btnCls} data-testid="share-btn">
        {busy ? <span className="spinner" /> : <Share2 size={14} />}{tr.share}
      </button>
      {open && link && (
        <div className="absolute right-0 z-30 mt-2 w-64 card-tactical p-2 space-y-1 shadow-2xl" data-testid="share-menu">
          <button type="button" onClick={wa} className="w-full h-10 px-3 rounded-lg text-left text-sm text-emerald-300 hover:bg-emerald-950/40 flex items-center gap-2" data-testid="share-whatsapp"><Send size={14} />WhatsApp</button>
          <button type="button" onClick={messenger} className="w-full h-10 px-3 rounded-lg text-left text-sm text-sky-300 hover:bg-sky-950/40 flex items-center gap-2" data-testid="share-messenger"><MessageCircle size={14} />Messenger</button>
          <button type="button" onClick={copy} className="w-full h-10 px-3 rounded-lg text-left text-sm text-zinc-300 hover:bg-[#151515] flex items-center gap-2" data-testid="share-copy"><Copy size={14} />{tr.copy_link}</button>
          <div className="px-3 pb-1 text-[10px] text-zinc-600">{tr.valid_30}</div>
        </div>
      )}
    </div>
  );
}
