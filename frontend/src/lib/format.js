// Money + date helpers
export function fmtMoney(amount, currency = "MXN", locale = "es-MX") {
  const val = Number.isFinite(amount) ? amount : 0;
  try {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency,
      minimumFractionDigits: 2,
    }).format(val);
  } catch {
    return `$${val.toFixed(2)} ${currency}`;
  }
}

export function fmtDate(iso, locale = "es-MX") {
  if (!iso) return "";
  const d = typeof iso === "string" ? new Date(iso) : iso;
  if (isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat(locale, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(d);
}

export function fmtDateTime(iso, locale = "es-MX") {
  if (!iso) return "";
  const d = typeof iso === "string" ? new Date(iso) : iso;
  if (isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat(locale, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}
