import React from "react";
import { X } from "lucide-react";

/** Shared modal shell used across every module form. */
export function Modal({ title, onClose, children, testId = "modal", size = "md" }) {
  const width = size === "lg" ? "sm:max-w-2xl" : size === "xl" ? "sm:max-w-4xl" : "sm:max-w-lg";
  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/70 backdrop-blur-sm p-0 sm:p-6"
      onClick={onClose}
      data-testid={`${testId}-overlay`}
    >
      <div
        className={`w-full ${width} card-tactical p-5 sm:p-6 max-h-[92vh] overflow-y-auto rounded-t-2xl sm:rounded-2xl`}
        onClick={(e) => e.stopPropagation()}
        data-testid={testId}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display uppercase text-xl tracking-wider text-white">{title}</h2>
          <button
            type="button"
            className="text-zinc-500 hover:text-white p-1"
            onClick={onClose}
            aria-label="Close"
            data-testid={`${testId}-close`}
          >
            <X size={18} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Field({ label, required, children }) {
  return (
    <div>
      <label className="block text-[11px] uppercase tracking-widest font-mono-tactical text-zinc-500 mb-1.5">
        {label}
        {required && <span className="text-[#dc2626] ml-1">*</span>}
      </label>
      {children}
    </div>
  );
}

export function Input({ testId, value, onChange, type = "text", placeholder = "" }) {
  return (
    <input
      type={type}
      className="w-full h-11 bg-[#0d0d0d] border border-[#262626] rounded-lg px-3.5 text-sm text-white outline-none focus:border-[#dc2626] transition-colors"
      value={value ?? ""}
      onChange={(e) => onChange(type === "number" ? (e.target.value === "" ? "" : Number(e.target.value)) : e.target.value)}
      placeholder={placeholder}
      data-testid={testId}
    />
  );
}

export function Textarea({ testId, value, onChange, rows = 3 }) {
  return (
    <textarea
      rows={rows}
      className="w-full bg-[#0d0d0d] border border-[#262626] rounded-lg px-3.5 py-2.5 text-sm text-white outline-none focus:border-[#dc2626] transition-colors"
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value)}
      data-testid={testId}
    />
  );
}

export function Select({ testId, value, onChange, options }) {
  return (
    <select
      className="w-full h-11 bg-[#0d0d0d] border border-[#262626] rounded-lg px-3.5 text-sm text-white outline-none focus:border-[#dc2626] transition-colors"
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value)}
      data-testid={testId}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  );
}

export function StatusBadge({ label, tone = "default" }) {
  const tones = {
    default: "border-[#262626] bg-[#0d0d0d] text-zinc-400",
    red: "border-red-800/60 bg-red-950/40 text-red-300",
    green: "border-emerald-800/60 bg-emerald-950/40 text-emerald-300",
    amber: "border-amber-800/60 bg-amber-950/40 text-amber-300",
    blue: "border-blue-800/60 bg-blue-950/40 text-blue-300",
    gray: "border-zinc-700 bg-zinc-900/50 text-zinc-400",
  };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border font-mono-tactical uppercase tracking-widest px-2.5 py-1 text-[10px] ${tones[tone] || tones.default}`}>
      {label}
    </span>
  );
}

export function PageHeader({ title, subtitle, action }) {
  return (
    <div className="flex items-start justify-between gap-4 flex-wrap">
      <div>
        <div className="font-mono-tactical text-[11px] uppercase tracking-widest text-zinc-500 mb-1">
          {subtitle}
        </div>
        <h1 className="font-display uppercase text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
          {title}
        </h1>
      </div>
      {action}
    </div>
  );
}
