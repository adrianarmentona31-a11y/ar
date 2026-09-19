import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Plus,
  Search,
  Users,
  Building2,
  Warehouse,
  Phone,
  Mail,
  MapPin,
  X,
  Trash2,
  Pencil,
} from "lucide-react";
import { toast } from "sonner";
import { api, formatApiError } from "../lib/api";
import { useI18n } from "../context/I18nContext";
import { useAuth } from "../context/AuthContext";

const TYPES = ["particular", "empresa", "lote"];

const TYPE_ICONS = {
  particular: Users,
  empresa: Building2,
  lote: Warehouse,
};

function TypePill({ tipo, size = "md" }) {
  const { t } = useI18n();
  const Icon = TYPE_ICONS[tipo] || Users;
  const color =
    tipo === "empresa"
      ? "border-blue-800/50 bg-blue-950/40 text-blue-300"
      : tipo === "lote"
        ? "border-amber-800/50 bg-amber-950/40 text-amber-300"
        : "border-emerald-800/50 bg-emerald-950/40 text-emerald-300";
  const pad = size === "sm" ? "px-2 py-0.5 text-[9px]" : "px-2.5 py-1 text-[10px]";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-mono-tactical uppercase tracking-widest ${pad} ${color}`}
    >
      <Icon size={11} />
      {t.clientes.types[tipo] || tipo}
    </span>
  );
}

function ClientForm({ initial, onClose, onSaved, onDelete }) {
  const { t } = useI18n();
  const editing = !!initial?.id;
  const [tipo, setTipo] = useState(initial?.tipo || "particular");
  const [nombre, setNombre] = useState(initial?.nombre || "");
  const [telefono, setTelefono] = useState(initial?.telefono || "");
  const [email, setEmail] = useState(initial?.email || "");
  const [direccion, setDireccion] = useState(initial?.direccion || "");
  const [notas, setNotas] = useState(initial?.notas || "");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [err, setErr] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setSaving(true);
    const payload = { tipo, nombre, telefono, email, direccion, notas };
    try {
      const res = editing
        ? await api.patch(`/clients/${initial.id}`, payload)
        : await api.post("/clients", payload);
      toast.success(editing ? t.toast.client_updated : t.toast.client_created);
      onSaved?.(res.data);
    } catch (e2) {
      setErr(formatApiError(e2));
    } finally {
      setSaving(false);
    }
  };

  const doDelete = async () => {
    if (!editing) return;
    if (!window.confirm(t.clientes.form.delete_confirm)) return;
    setDeleting(true);
    try {
      await api.delete(`/clients/${initial.id}`);
      toast.success(t.toast.client_deleted);
      onDelete?.(initial.id);
    } catch (e2) {
      toast.error(formatApiError(e2));
      setDeleting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/70 backdrop-blur-sm p-0 sm:p-6"
      onClick={onClose}
      data-testid="client-form-overlay"
    >
      <div
        className="w-full sm:max-w-lg card-tactical p-5 sm:p-6 max-h-[92vh] overflow-y-auto rounded-t-2xl sm:rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display uppercase text-xl tracking-wider text-white">
            {editing ? t.clientes.edit : t.clientes.new}
          </h2>
          <button
            type="button"
            className="text-zinc-500 hover:text-white p-1"
            onClick={onClose}
            aria-label="Close"
            data-testid="client-form-close"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={submit} className="space-y-4" data-testid="client-form">
          <div>
            <label className="block text-[11px] uppercase tracking-widest font-mono-tactical text-zinc-500 mb-1.5">
              {t.clientes.form.tipo}
            </label>
            <div className="grid grid-cols-3 gap-2">
              {TYPES.map((tp) => {
                const Icon = TYPE_ICONS[tp];
                const active = tipo === tp;
                return (
                  <button
                    key={tp}
                    type="button"
                    onClick={() => setTipo(tp)}
                    data-testid={`client-form-tipo-${tp}`}
                    className={`h-12 rounded-lg border flex items-center justify-center gap-2 text-xs uppercase tracking-widest font-mono-tactical transition-colors ${
                      active
                        ? "border-[#dc2626] bg-[#dc262614] text-white"
                        : "border-[#262626] bg-[#0d0d0d] text-zinc-500 hover:text-white hover:border-[#3a3a3a]"
                    }`}
                  >
                    <Icon size={13} />
                    {t.clientes.types[tp]}
                  </button>
                );
              })}
            </div>
          </div>

          <FieldInput
            testId="client-form-nombre"
            label={t.clientes.form.nombre}
            value={nombre}
            onChange={setNombre}
            required
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <FieldInput
              testId="client-form-telefono"
              label={t.clientes.form.telefono}
              value={telefono}
              onChange={setTelefono}
              type="tel"
            />
            <FieldInput
              testId="client-form-email"
              label={t.clientes.form.email}
              value={email}
              onChange={setEmail}
              type="email"
            />
          </div>
          <FieldInput
            testId="client-form-direccion"
            label={t.clientes.form.direccion}
            value={direccion}
            onChange={setDireccion}
          />
          <div>
            <label className="block text-[11px] uppercase tracking-widest font-mono-tactical text-zinc-500 mb-1.5">
              {t.clientes.form.notas}
            </label>
            <textarea
              className="w-full min-h-[80px] bg-[#0d0d0d] border border-[#262626] rounded-lg px-3.5 py-2.5 text-sm text-white outline-none focus:border-[#dc2626] transition-colors"
              value={notas}
              onChange={(e) => setNotas(e.target.value)}
              data-testid="client-form-notas"
            />
          </div>

          {err && (
            <div
              className="rounded-lg border border-red-800/70 bg-red-950/40 px-3.5 py-2.5 text-sm text-red-200"
              data-testid="client-form-error"
            >
              {err}
            </div>
          )}

          <div className="flex flex-col sm:flex-row gap-2 sm:gap-3 pt-1">
            <button
              type="submit"
              className="armenta-btn-primary flex-1 flex items-center justify-center gap-2 !h-12"
              disabled={saving}
              data-testid="client-form-submit"
            >
              {saving ? <span className="spinner" /> : null}
              {saving ? t.clientes.form.saving : t.clientes.form.save}
            </button>
            {editing && (
              <button
                type="button"
                onClick={doDelete}
                className="h-12 px-4 rounded-lg border border-red-900/60 bg-red-950/30 text-red-300 hover:bg-red-900/40 hover:text-white flex items-center justify-center gap-2 transition-colors text-sm"
                disabled={deleting}
                data-testid="client-form-delete"
              >
                <Trash2 size={14} />
                {t.clientes.form.delete}
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="armenta-btn-ghost !h-12 !px-4"
              data-testid="client-form-cancel"
            >
              {t.clientes.form.cancel}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function FieldInput({ testId, label, value, onChange, type = "text", required }) {
  return (
    <div>
      <label className="block text-[11px] uppercase tracking-widest font-mono-tactical text-zinc-500 mb-1.5">
        {label}
        {required && <span className="text-[#dc2626] ml-1">*</span>}
      </label>
      <input
        type={type}
        className="w-full h-11 bg-[#0d0d0d] border border-[#262626] rounded-lg px-3.5 text-sm text-white outline-none focus:border-[#dc2626] transition-colors"
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
        data-testid={testId}
      />
    </div>
  );
}

export default function Clientes() {
  const { t, locale } = useI18n();
  const { user } = useAuth();
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("all");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (q.trim()) params.q = q.trim();
      if (filter !== "all") params.tipo = filter;
      const { data } = await api.get("/clients", { params });
      setItems(data.items || []);
      setTotal(data.total || 0);
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setLoading(false);
    }
  }, [q, filter]);

  useEffect(() => {
    const id = setTimeout(fetchList, 220);
    return () => clearTimeout(id);
  }, [fetchList]);

  const onSaved = () => {
    setFormOpen(false);
    setEditing(null);
    fetchList();
  };

  const onDeleted = () => {
    setFormOpen(false);
    setEditing(null);
    fetchList();
  };

  const openNew = () => {
    setEditing(null);
    setFormOpen(true);
  };
  const openEdit = (c) => {
    setEditing(c);
    setFormOpen(true);
  };

  const dateFmt = useMemo(
    () =>
      new Intl.DateTimeFormat(locale === "es" ? "es-MX" : "en-US", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      }),
    [locale],
  );

  return (
    <div className="space-y-5" data-testid="clientes-page">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="font-mono-tactical text-[11px] uppercase tracking-widest text-zinc-500 mb-1">
            {t.clientes.subtitle}
          </div>
          <h1 className="font-display uppercase text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
            {t.clientes.title}
          </h1>
          <p
            className="text-sm text-zinc-400 mt-2 font-mono-tactical"
            data-testid="clientes-total"
          >
            {t.clientes.total(total)}
          </p>
        </div>
        <button
          type="button"
          className="armenta-btn-primary !w-auto !h-12 !px-5 flex items-center justify-center gap-2"
          onClick={openNew}
          data-testid="clientes-new-button"
        >
          <Plus size={16} />
          {t.clientes.new}
        </button>
      </div>

      <div className="card-tactical p-4 flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search
            size={16}
            className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-500"
          />
          <input
            className="w-full h-11 bg-[#0d0d0d] border border-[#262626] rounded-lg pl-10 pr-3.5 text-sm text-white outline-none focus:border-[#dc2626] transition-colors"
            placeholder={t.clientes.search_placeholder}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            data-testid="clientes-search"
          />
        </div>
        <div className="flex gap-2 overflow-x-auto">
          {["all", ...TYPES].map((tp) => {
            const active = filter === tp;
            const label =
              tp === "all" ? t.clientes.filter_all : t.clientes.types[tp];
            return (
              <button
                key={tp}
                type="button"
                onClick={() => setFilter(tp)}
                data-testid={`clientes-filter-${tp}`}
                className={`h-11 px-4 rounded-lg border text-xs uppercase font-mono-tactical tracking-widest whitespace-nowrap transition-colors ${
                  active
                    ? "border-[#dc2626] bg-[#dc262614] text-white"
                    : "border-[#262626] bg-[#0d0d0d] text-zinc-500 hover:text-white hover:border-[#3a3a3a]"
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>

      {loading ? (
        <div className="card-tactical p-10 flex items-center justify-center">
          <span className="spinner spinner-gold" />
        </div>
      ) : items.length === 0 ? (
        <div
          className="card-tactical p-8 text-center"
          data-testid="clientes-empty"
        >
          <div className="w-14 h-14 rounded-2xl bg-[#0d0d0d] border border-[#262626] flex items-center justify-center mx-auto mb-4">
            <Users size={22} className="text-[#dc2626]" />
          </div>
          <h3 className="text-white font-semibold mb-1">
            {t.clientes.empty_title}
          </h3>
          <p className="text-sm text-zinc-500 max-w-sm mx-auto">
            {t.clientes.empty_desc}
          </p>
          <button
            type="button"
            onClick={openNew}
            className="armenta-btn-primary !w-auto !h-11 !px-5 mt-5 mx-auto flex items-center gap-2"
            data-testid="clientes-empty-create"
          >
            <Plus size={15} />
            {t.clientes.new}
          </button>
        </div>
      ) : (
        <div
          className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3"
          data-testid="clientes-list"
        >
          {items.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => openEdit(c)}
              className="card-tactical p-4 text-left hover:border-[#dc262666]"
              data-testid={`client-card-${c.id}`}
            >
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="min-w-0 flex-1">
                  <div className="text-white font-semibold truncate">
                    {c.nombre}
                  </div>
                  <div className="text-[10px] font-mono-tactical uppercase tracking-widest text-zinc-500 mt-1">
                    {t.clientes.created_at}: {dateFmt.format(new Date(c.created_at))}
                  </div>
                </div>
                <TypePill tipo={c.tipo} size="sm" />
              </div>
              <div className="space-y-1.5 text-xs text-zinc-400">
                <div className="flex items-center gap-2 truncate">
                  <Phone size={12} className="text-zinc-500 shrink-0" />
                  <span className="truncate">
                    {c.telefono || <span className="text-zinc-600">{t.clientes.no_phone}</span>}
                  </span>
                </div>
                <div className="flex items-center gap-2 truncate">
                  <Mail size={12} className="text-zinc-500 shrink-0" />
                  <span className="truncate">
                    {c.email || <span className="text-zinc-600">{t.clientes.no_email}</span>}
                  </span>
                </div>
                {c.direccion && (
                  <div className="flex items-center gap-2 truncate">
                    <MapPin size={12} className="text-zinc-500 shrink-0" />
                    <span className="truncate">{c.direccion}</span>
                  </div>
                )}
              </div>
              <div className="mt-3 pt-3 border-t border-[#1a1a1a] flex items-center justify-end text-[10px] uppercase tracking-widest font-mono-tactical text-zinc-500">
                <Pencil size={11} className="mr-1.5" />
                {t.clientes.edit}
              </div>
            </button>
          ))}
        </div>
      )}

      {formOpen && (
        <ClientForm
          initial={editing}
          onClose={() => {
            setFormOpen(false);
            setEditing(null);
          }}
          onSaved={onSaved}
          onDelete={onDeleted}
        />
      )}
    </div>
  );
}
