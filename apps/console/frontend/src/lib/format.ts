export const money = (v: number | null | undefined) =>
  (v ?? 0).toLocaleString(undefined, { style: "currency", currency: "USD" });

export const num = (v: number | null | undefined, d = 2) =>
  v == null ? "—" : v.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });

export const dt = (s: string | null | undefined) => {
  if (!s) return "—";
  const d = new Date(s);
  return isNaN(d.getTime()) ? s : d.toLocaleString(undefined,
    { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
};

export const expiry = (s: string) =>
  s && s.length === 8 ? `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}` : s;
