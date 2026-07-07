/** Money + number formatting — a single source so every dollar value on screen reads the
 * same way ($1,234.56, always with the $ sign, to avoid any ambiguity about units). */

const USD = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** "$1,234.56". Null/undefined -> an em-dash. */
export function usd(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return USD.format(value);
}

/** Signed money: "+$12.50" / "-$3.00" — for P&L where the sign carries meaning. */
export function usdSigned(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  const sign = value >= 0 ? "+" : "-";
  return `${sign}${USD.format(Math.abs(value))}`;
}

/** A bare strike/level with a $ and no forced decimals: "$6,000", "$66.5". */
export function usdStrike(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return "$" + value.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

/** "72%" from a 0..1 fraction. */
export function pct(fraction: number | null | undefined, digits = 0): string {
  if (fraction == null || Number.isNaN(fraction)) return "—";
  return (fraction * 100).toFixed(digits) + "%";
}

/** US options are quoted PER SHARE; one contract controls 100 shares. Premiums and P&L on
 * a candidate/position are per-share, so account dollars = value × 100. Strikes/breakevens
 * are price levels and must NOT be multiplied (use usd/usdStrike for those). */
export const CONTRACT_MULTIPLIER = 100;

/** Per-share premium/P&L -> real per-contract dollars: 9.55 -> "$955.00". */
export function usdContract(perShare: number | null | undefined): string {
  if (perShare == null || Number.isNaN(perShare)) return "—";
  return usd(perShare * CONTRACT_MULTIPLIER);
}

/** Signed per-contract dollars: 5.55 -> "+$555.00". */
export function usdContractSigned(perShare: number | null | undefined): string {
  if (perShare == null || Number.isNaN(perShare)) return "—";
  return usdSigned(perShare * CONTRACT_MULTIPLIER);
}
