import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Star, CheckCircle2 } from "lucide-react";
import axios from "axios";
import { BrandMark } from "../components/BrandMark";
import { ArmentaWordmark } from "../components/ArmentaWordmark";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/public/surveys`;
const ASPECT_LABEL = { puntualidad: "Puntualidad", calidad: "Calidad del trabajo", precio: "Precio justo", comunicacion: "Comunicación", limpieza: "Limpieza y orden" };

function Stars({ value, onChange }) {
  const [hover, setHover] = useState(0);
  return (
    <div className="flex gap-2 justify-center" data-testid="survey-stars">
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" onClick={() => onChange(n)} onMouseEnter={() => setHover(n)} onMouseLeave={() => setHover(0)}
          className="p-1 transition-transform hover:scale-110" data-testid={`survey-star-${n}`} aria-label={`${n} estrellas`}>
          <Star size={40} className={(hover || value) >= n ? "text-[#dc2626] fill-[#dc2626]" : "text-zinc-700"} />
        </button>
      ))}
    </div>
  );
}

function NpsScale({ value, onChange }) {
  return (
    <div className="grid grid-cols-11 gap-1" data-testid="survey-nps">
      {Array.from({ length: 11 }, (_, i) => (
        <button key={i} type="button" onClick={() => onChange(i)} data-testid={`survey-nps-${i}`}
          className={`h-10 rounded-md border text-sm font-mono-tactical transition-colors ${value === i ? "border-[#dc2626] bg-[#dc2626] text-white" : "border-[#262626] bg-[#0d0d0d] text-zinc-400 hover:text-white"}`}>
          {i}
        </button>
      ))}
    </div>
  );
}

export default function EncuestaPublica() {
  const { token } = useParams();
  const [info, setInfo] = useState(null);
  const [error, setError] = useState("");
  const [rating, setRating] = useState(0);
  const [nps, setNps] = useState(null);
  const [aspects, setAspects] = useState([]);
  const [comments, setComments] = useState("");
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    axios.get(`${API}/${token}`).then((r) => setInfo(r.data)).catch((e) => setError(e?.response?.data?.detail || "Encuesta no disponible."));
  }, [token]);

  const toggleAspect = (a) => setAspects((s) => (s.includes(a) ? s.filter((x) => x !== a) : [...s, a]));

  const submit = async () => {
    if (!rating) return setError("Selecciona una calificación con estrellas.");
    if (nps === null) return setError("Indica del 0 al 10 qué tanto nos recomendarías.");
    setError(""); setSending(true);
    try {
      await axios.post(`${API}/${token}/respond`, { rating, nps, aspects, comments });
      setDone(true);
    } catch (e) { setError(e?.response?.data?.detail || "No se pudo enviar. Intenta de nuevo."); }
    finally { setSending(false); }
  };

  const answered = done || info?.status === "answered";

  return (
    <div className="min-h-screen bg-[#050505] text-white flex flex-col items-center px-4 py-8" data-testid="survey-public-page">
      <div className="flex items-center gap-4 mb-8">
        <BrandMark size={56} />
        <ArmentaWordmark width={180} />
      </div>
      <div className="w-full max-w-lg card-tactical p-6 sm:p-8 space-y-6">
        {!info && !error && <div className="flex justify-center py-10"><span className="spinner spinner-gold" /></div>}
        {error && !info && <p className="text-sm text-red-400 text-center" data-testid="survey-error">{error}</p>}
        {info && answered && (
          <div className="text-center py-6 space-y-3" data-testid="survey-thanks">
            <CheckCircle2 size={48} className="text-[#dc2626] mx-auto" />
            <h1 className="font-display uppercase text-2xl tracking-wider">¡Gracias{info.client_first_name ? `, ${info.client_first_name}` : ""}!</h1>
            <p className="text-sm text-zinc-400">Tu opinión nos ayuda a mejorar cada servicio de {info.company_name}.</p>
          </div>
        )}
        {info && !answered && (
          <>
            <div className="text-center">
              <div className="font-mono-tactical text-[10px] uppercase tracking-widest text-zinc-500">Encuesta de satisfacción · {info.folio}</div>
              <h1 className="font-display uppercase text-2xl sm:text-3xl tracking-wider mt-2">¿Cómo fue tu servicio{info.client_first_name ? `, ${info.client_first_name}` : ""}?</h1>
              {(info.vehicle || info.technician) && (
                <p className="text-xs text-zinc-500 mt-2">{[info.vehicle, info.technician && `Técnico: ${info.technician}`].filter(Boolean).join(" · ")}</p>
              )}
            </div>
            <div className="space-y-2">
              <p className="text-sm text-zinc-300 text-center">Calificación general</p>
              <Stars value={rating} onChange={setRating} />
            </div>
            <div className="space-y-2">
              <p className="text-sm text-zinc-300">¿Qué tanto nos recomendarías a un amigo o familiar?</p>
              <NpsScale value={nps} onChange={setNps} />
              <div className="flex justify-between text-[10px] font-mono-tactical uppercase tracking-widest text-zinc-600"><span>Nada probable</span><span>Muy probable</span></div>
            </div>
            <div className="space-y-2">
              <p className="text-sm text-zinc-300">¿Qué destacarías?</p>
              <div className="flex flex-wrap gap-2">
                {info.aspects.map((a) => (
                  <button key={a} type="button" onClick={() => toggleAspect(a)} data-testid={`survey-aspect-${a}`}
                    className={`h-9 px-3 rounded-full border text-xs transition-colors ${aspects.includes(a) ? "border-[#dc2626] bg-[#dc262622] text-white" : "border-[#262626] text-zinc-400 hover:text-white"}`}>
                    {ASPECT_LABEL[a] || a}
                  </button>
                ))}
              </div>
            </div>
            <textarea rows={3} value={comments} onChange={(e) => setComments(e.target.value)} placeholder="Comentarios (opcional)"
              className="w-full bg-[#0d0d0d] border border-[#262626] rounded-lg px-3.5 py-2.5 text-sm text-white outline-none focus:border-[#dc2626]" data-testid="survey-comments" />
            {error && <p className="text-sm text-red-400" data-testid="survey-error">{error}</p>}
            <button type="button" onClick={submit} disabled={sending} className="armenta-btn-primary !h-12 w-full" data-testid="survey-submit">
              {sending ? "Enviando…" : "Enviar opinión"}
            </button>
          </>
        )}
      </div>
      <p className="text-[10px] font-mono-tactical uppercase tracking-widest text-zinc-600 mt-6">{info?.company_name || "Armenta's Motors Company"}</p>
    </div>
  );
}
