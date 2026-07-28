import { useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useT } from "../i18n/useT";
import { PnL, type Tone } from "./ui";

/* --------------------------------------------------------------- cluster -- */

export interface Detail {
  /** Overrides the headline value shown in the dialog; defaults to the cell's own. */
  value?: ReactNode;
  formula?: ReactNode;
  rows?: DetailRow[];
  note?: ReactNode;
}
export interface MetricDef extends Omit<MetricProps, "onClick"> { detail?: Detail }
export interface HeroDef {
  label: string; value: number | null | undefined;
  format?: (v: number) => string;
  curve?: number[]; sub?: ReactNode; right?: ReactNode; detail?: Detail;
}

/**
 * The one metric surface every page uses: a hero reading plus a dense cell grid, each
 * cell opening its own breakdown. Pages declare data; layout, interaction and the dialog
 * live here, so a figure looks and behaves the same wherever it appears.
 */
export function Cluster({ hero, metrics }: { hero?: HeroDef; metrics: MetricDef[] }) {
  const [open, setOpen] = useState<number | null>(null);
  const active = open == null ? null
    : open === -1
      ? (hero ? { title: hero.label, d: hero.detail, fallback: <PnL value={hero.value} format={hero.format} /> } : null)
      : (metrics[open] ? { title: metrics[open].k, d: metrics[open].detail, fallback: metrics[open].v } : null);

  return (
    <>
      <div className="cluster">
        {hero && (
          <HeroMetric {...hero} onClick={hero.detail ? () => setOpen(-1) : undefined} />
        )}
        <div className="cells">
          {metrics.map((m, i) => (
            <Metric key={i} {...m} onClick={m.detail ? () => setOpen(i) : undefined} />
          ))}
        </div>
      </div>
      {active && (
        <MetricModal open onClose={() => setOpen(null)} title={active.title}
          value={active.d?.value ?? active.fallback}
          formula={active.d?.formula} rows={active.d?.rows} note={active.d?.note} />
      )}
    </>
  );
}

/* ------------------------------------------------------------------ hero -- */

/**
 * The one number the page exists to answer, with the period's equity curve drawn
 * behind it. Everything else on the panel is context for this.
 */
export function HeroMetric({ label, value, sub, curve, onClick, right, format }: {
  label: string; value: number | null | undefined; sub?: ReactNode;
  curve?: number[]; onClick?: () => void; right?: ReactNode;
  format?: (v: number) => string;
}) {
  const tone: Tone = value == null ? "flat" : value > 0 ? "pos" : value < 0 ? "neg" : "flat";
  return (
    <div className={`hero t-${tone}`} onClick={onClick} role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={(e) => { if (onClick && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onClick(); } }}>
      {curve && curve.length > 1 && <Spark data={curve} tone={tone} fill />}
      <div className="heroin">
        <div className="k">{label}</div>
        <div className="v"><PnL value={value} format={format} /></div>
        {sub && <div className="sub">{sub}</div>}
      </div>
      {right && <div className="heroright">{right}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ cell -- */

export interface MetricProps {
  k: string;
  v: ReactNode;
  tone?: Tone;
  /** Micro-visualisation drawn under the value: a sparkline or a ratio bar. */
  spark?: number[];
  ratio?: { win: number; loss: number };
  meter?: number;                 // 0..1 fill
  sub?: ReactNode;
  muted?: boolean;                // statement-scope: not filtered by the range
  onClick?: () => void;
}

/** One instrument in the cluster. Dense by design: label, value, one micro-visual. */
export function Metric({ k, v, tone = "flat", spark, ratio, meter, sub, muted, onClick }: MetricProps) {
  return (
    <div className={`cell t-${tone}${muted ? " muted" : ""}`} onClick={onClick}
      role={onClick ? "button" : undefined} tabIndex={onClick ? 0 : undefined}
      onKeyDown={(e) => { if (onClick && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onClick(); } }}>
      <div className="k">{k}</div>
      <div className="v">{v}</div>
      {spark && spark.length > 1 && <Spark data={spark} tone={tone} />}
      {ratio && <RatioBar {...ratio} />}
      {meter != null && (
        <div className="meter"><span style={{ width: `${Math.max(0, Math.min(1, meter)) * 100}%` }} /></div>
      )}
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}

/* --------------------------------------------------------- micro-visuals -- */

/** Inline sparkline. Pure SVG, no library — it has to stay cheap at 12 per screen. */
export function Spark({ data, tone = "flat", fill }: { data: number[]; tone?: Tone; fill?: boolean }) {
  const n = data.length;
  const lo = Math.min(...data), hi = Math.max(...data);
  const span = hi - lo || 1;
  const x = (i: number) => (i / (n - 1)) * 100;
  const y = (v: number) => 100 - ((v - lo) / span) * 100;
  const line = data.map((v, i) => `${x(i).toFixed(2)},${y(v).toFixed(2)}`).join(" ");
  const zero = lo < 0 && hi > 0 ? y(0) : null;
  return (
    <svg className={`spark ${fill ? "big" : ""}`} viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
      {fill && <polygon points={`0,100 ${line} 100,100`} className={`sfillarea t-${tone}`} />}
      {zero != null && <line x1="0" x2="100" y1={zero} y2={zero} className="szero" />}
      <polyline points={line} className={`sline t-${tone}`} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/** Win/loss split as one proportional bar — reads faster than "215 W / 88 L". */
export function RatioBar({ win, loss }: { win: number; loss: number }) {
  const total = win + loss || 1;
  return (
    <div className="ratiobar" aria-hidden>
      <span className="w" style={{ width: `${(win / total) * 100}%` }} />
      <span className="l" style={{ width: `${(loss / total) * 100}%` }} />
    </div>
  );
}

/* ----------------------------------------------------------------- modal -- */

export interface DetailRow { k: string; v: ReactNode; tone?: "pos" | "neg" }

/**
 * Metric detail. Its job is to answer "where does this number come from" — the
 * question that has caused every reconciliation dispute with the broker — so the
 * formula is shown with the real values substituted, not in the abstract.
 */
export function MetricModal({ open, onClose, title, value, formula, rows, note }: {
  open: boolean; onClose: () => void;
  title: string; value: ReactNode;
  formula?: ReactNode; rows?: DetailRow[]; note?: ReactNode;
}) {
  const { t } = useT();
  useEffect(() => {
    if (!open) return;
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", esc);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", esc); document.body.style.overflow = prev; };
  }, [open, onClose]);

  if (!open) return null;
  return createPortal(
    <div className="mbackdrop" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title}
        onClick={(e) => e.stopPropagation()}>
        <div className="mhd">
          <h3>{title}</h3>
          <button className="iconbtn" onClick={onClose} aria-label={t("close")}>✕</button>
        </div>
        <div className="mval">{value}</div>
        {formula && (
          <div className="mformula">
            <div className="lbl">{t("m_how")}</div>
            <div className="expr ltr">{formula}</div>
          </div>
        )}
        {rows && rows.length > 0 && (
          <table className="mtable">
            <tbody>{rows.map((r, i) => (
              <tr key={i}>
                <td className="mk">{r.k}</td>
                <td className={`mv${r.tone ? ` ${r.tone}` : ""}`}>{r.v}</td>
              </tr>
            ))}</tbody>
          </table>
        )}
        {note && <div className="mnote">{note}</div>}
      </div>
    </div>,
    document.body,
  );
}
