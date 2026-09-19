import React, { useCallback, useEffect, useState } from "react";
import { UserPlus, Trash2, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { api, formatApiError } from "../lib/api";
import { useI18n } from "../context/I18nContext";
import { useAuth } from "../context/AuthContext";
import { Field, Input, Select, StatusBadge } from "./ui-kit";

const ROLES = ["admin", "manager", "technician", "assistant", "viewer"];

export function TeamPanel() {
  const { t } = useI18n();
  const { user } = useAuth();
  const tr = t.equipo;
  const [items, setItems] = useState([]);
  const [f, setF] = useState({ email: "", name: "", role: "technician" });
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try { const { data } = await api.get("/team"); setItems(data.items || []); } catch (e) { toast.error(formatApiError(e)); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const invite = async (e) => {
    e.preventDefault();
    if (!f.email.trim()) return toast.error(t.common.required);
    setSaving(true);
    try { await api.post("/team", f); toast.success(tr.invited); setF({ email: "", name: "", role: "technician" }); load(); }
    catch (e2) { toast.error(formatApiError(e2)); } finally { setSaving(false); }
  };
  const patch = async (u, body) => {
    try { await api.patch(`/team/${u.id}`, body); load(); } catch (e) { toast.error(formatApiError(e)); }
  };
  const remove = async (u) => {
    if (!window.confirm(t.common.delete_confirm)) return;
    try { await api.delete(`/team/${u.id}`); toast.success(tr.removed); load(); } catch (e) { toast.error(formatApiError(e)); }
  };

  return (
    <div className="card-tactical p-5 space-y-4 max-w-3xl" data-testid="team-panel">
      <div className="flex items-center gap-2">
        <ShieldCheck size={16} className="text-[#dc2626]" />
        <div>
          <div className="text-white font-semibold">{tr.title}</div>
          <div className="text-xs text-zinc-500">{tr.subtitle}</div>
        </div>
      </div>
      <form onSubmit={invite} className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_150px_auto] gap-2 items-end">
        <Field label="Email (Google)"><Input testId="team-email" type="email" value={f.email} onChange={(v) => setF((s) => ({ ...s, email: v }))} placeholder="empleado@gmail.com" /></Field>
        <Field label={tr.name}><Input testId="team-name" value={f.name} onChange={(v) => setF((s) => ({ ...s, name: v }))} /></Field>
        <Field label={tr.role}><Select testId="team-role" value={f.role} onChange={(v) => setF((s) => ({ ...s, role: v }))} options={ROLES.map((r) => ({ value: r, label: tr.roles[r] }))} /></Field>
        <button type="submit" disabled={saving} className="armenta-btn-primary !w-auto !h-11 !px-4 flex items-center gap-2" data-testid="team-invite"><UserPlus size={14} />{tr.invite}</button>
      </form>
      <div className="divide-y divide-[#1a1a1a]">
        {items.map((u) => (
          <div key={u.id} className="py-3 flex flex-wrap items-center gap-3" data-testid={`team-row-${u.id}`}>
            <div className="min-w-0 flex-1">
              <div className="text-white text-sm truncate">{u.name} {u.id === user?.id && <span className="text-[10px] text-zinc-500">({tr.you})</span>}</div>
              <div className="text-xs text-zinc-500 truncate">{u.email}</div>
            </div>
            <StatusBadge label={u.google_linked ? "Google" : tr.pending_login} tone={u.google_linked ? "green" : "amber"} />
            <select value={u.role} disabled={u.id === user?.id} onChange={(e) => patch(u, { role: e.target.value })} className="h-9 px-2 rounded-md bg-[#0d0d0d] border border-[#262626] text-xs text-white" data-testid={`team-role-${u.id}`}>
              {ROLES.map((r) => <option key={r} value={r}>{tr.roles[r]}</option>)}
            </select>
            <button type="button" disabled={u.id === user?.id} onClick={() => patch(u, { active: !u.active })} className={`h-9 px-3 rounded-md border text-xs ${u.active ? "border-emerald-800/60 text-emerald-300" : "border-[#262626] text-zinc-500"}`} data-testid={`team-active-${u.id}`}>{u.active ? tr.active : tr.inactive}</button>
            <button type="button" disabled={u.id === user?.id} onClick={() => remove(u)} className="text-zinc-600 hover:text-red-400 disabled:opacity-30" data-testid={`team-rm-${u.id}`}><Trash2 size={14} /></button>
          </div>
        ))}
      </div>
    </div>
  );
}
