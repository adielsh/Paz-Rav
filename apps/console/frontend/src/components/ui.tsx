import type { ReactNode } from "react";
import { useT } from "../i18n/useT";
import type { TKey } from "../i18n/translations";
import { money } from "../lib/format";

export type Tone = "pos" | "neg" | "accent" | "warn" | "flat";

/** Tone derived from a number — the one rule the whole app uses for gain/loss. */
export const toneOf = (v: number | null | undefined): Tone =>
  v == null ? "flat" : v > 0 ? "pos" : v < 0 ? "neg" : "flat";

export function Tile({ k, children, cls, tone, hint }: {
  k: string; children: ReactNode; cls?: string; tone?: Tone; hint?: ReactNode;
}) {
  return (
    <div className={`tile${tone ? ` t-${tone}` : ""}`}>
      <div className="k">{k}</div>
      <div className={`v ${cls ?? ""}`}>{children}</div>
      {hint != null && <div className="hint">{hint}</div>}
    </div>
  );
}

/**
 * A money tile whose colour, rail and arrow all follow the sign, so a loss is
 * never mistakable for a gain — the point of `כל צבע צריך להיות ברור`.
 */
export function PnLTile({ k, value, small, hint, format = money }: {
  k: string; value: number | null | undefined; small?: boolean; hint?: ReactNode;
  format?: (v: number) => string;
}) {
  const tone = toneOf(value);
  return (
    <Tile k={k} tone={tone} cls={`kpi${small ? " small" : ""}`} hint={hint}>
      <PnL value={value} format={format} />
    </Tile>
  );
}

/** Inline signed number: arrow + explicit sign + semantic colour. */
export function PnL({ value, format = money, chip, arrow = true }: {
  value: number | null | undefined; format?: (v: number) => string;
  chip?: boolean; arrow?: boolean;
}) {
  if (value == null) return <span className="pnl flat">—</span>;
  const dir = value > 0 ? "up" : value < 0 ? "down" : "flat";
  const glyph = value > 0 ? "▲" : value < 0 ? "▼" : "•";
  // Only add the sign if the formatter didn't already produce one — a percent formatter
  // that emits "+8.1%" was otherwise rendered as "++8.1%".
  const body = format(value);
  const signed = /^[+\-−]/.test(body);
  const text = (value > 0 && !signed ? "+" : "") + body;
  return (
    <span className={`pnl ${dir}${chip ? " chip" : ""}`}>
      {arrow && <span className="arw" aria-hidden>{glyph}</span>}
      {text}
    </span>
  );
}

export function Panel({ title, count, right, flush, children }: {
  title: string; count?: number; right?: ReactNode; flush?: boolean; children: ReactNode;
}) {
  return (
    <div className="panel">
      <div className="hd">
        <h2>{title}{count != null && <span className="cnt">{count}</span>}</h2>
        <div className="row">{right}</div>
      </div>
      {flush ? children : children}
    </div>
  );
}

export function Empty({ text }: { text: string }) {
  return <div className="empty">{text}</div>;
}

export function Pill({ kind, plain, children }: {
  kind: "ok" | "bad" | "warn" | "info" | "mut"; plain?: boolean; children: ReactNode;
}) {
  return <span className={`pill ${kind}${plain ? " plain" : ""}`}>{children}</span>;
}

export function StatusPill({ status }: { status: string }) {
  const { t } = useT();
  const s = status?.toLowerCase();
  const map: Record<string, "ok" | "bad" | "warn" | "info" | "mut"> = {
    open: "info", filled: "ok", closed: "mut", expired: "ok", stopped: "warn",
    cancelled: "bad", pendingsubmit: "warn", submitted: "warn",
  };
  const key = `st_${s}` as TKey;
  const label = ["open", "closed", "stopped", "expired"].includes(s) ? t(key) : status;
  return <Pill kind={map[s] ?? "mut"}>{label}</Pill>;
}
