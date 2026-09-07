import { useEffect, useMemo, useRef, useState } from "react";
import { useT } from "../i18n/useT";
import type { TKey } from "../i18n/translations";

export interface DateRange { from: string; to: string }   // "yyyy-mm-dd" (empty = unbounded)

interface Props {
  value: DateRange;
  onChange: (r: DateRange) => void;
  min?: string;                    // clamp: earliest selectable day
  max?: string;                    // clamp: latest selectable day
  /** Presets anchor to `max` (last day with data) rather than "today". */
  anchor?: string;
}

/* ---- day math on local midnights (no timezone drift) ---- */
const pad = (n: number) => String(n).padStart(2, "0");
export const toISO = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const parse = (s: string): Date | null => {
  if (!s) return null;
  const [y, m, d] = s.split("-").map(Number);
  return y && m && d ? new Date(y, m - 1, d) : null;
};
const addDays = (d: Date, n: number) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
const addMonths = (d: Date, n: number) => new Date(d.getFullYear(), d.getMonth() + n, 1);
const startOfMonth = (d: Date) => new Date(d.getFullYear(), d.getMonth(), 1);
const daysBetween = (a: Date, b: Date) => Math.round((b.getTime() - a.getTime()) / 864e5) + 1;
const clamp = (d: Date, lo: Date | null, hi: Date | null) =>
  lo && d < lo ? lo : hi && d > hi ? hi : d;

type PresetId = "day" | "week" | "month" | "quarter" | "ytd" | "year" | "all";
const PRESETS: { id: PresetId; key: TKey }[] = [
  { id: "day", key: "p_day" }, { id: "week", key: "p_week" }, { id: "month", key: "p_month" },
  { id: "quarter", key: "p_quarter" }, { id: "ytd", key: "p_ytd" }, { id: "year", key: "p_year" },
  { id: "all", key: "p_all" },
];

export default function DateRangePicker({ value, onChange, min, max, anchor }: Props) {
  const { t, lang } = useT();
  const [open, setOpen] = useState(false);
  // Which end of the range the next calendar click sets. Explicit and visible, so you can
  // nudge one edge without re-picking the whole range.
  const [editing, setEditing] = useState<"from" | "to">("from");
  const [hover, setHover] = useState<Date | null>(null);
  const box = useRef<HTMLDivElement>(null);

  const fromD = parse(value.from);
  const toD = parse(value.to);
  const anchorD = parse(anchor ?? "") ?? parse(max ?? "") ?? new Date();
  // The slider needs real bounds. Without data, fall back to a year ending at the anchor.
  const minD = parse(min ?? "") ?? addDays(anchorD, -364);
  const maxD = parse(max ?? "") ?? anchorD;

  const [view, setView] = useState<Date>(() => startOfMonth(toD ?? anchorD));
  useEffect(() => {
    if (!open) return;
    setView(startOfMonth(toD ?? anchorD));
    setEditing("from");
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) close(); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", away); document.removeEventListener("keydown", esc); };
  });
  const close = () => { setOpen(false); setHover(null); };

  /** Jump the calendar to whichever edge is being edited. */
  const focusEdge = (which: "from" | "to") => {
    setEditing(which);
    const d = which === "from" ? fromD : toD;
    if (d) setView(startOfMonth(d));
  };

  const viewClamped = (d: Date) => {
    let v = startOfMonth(d);
    if (v > startOfMonth(maxD)) v = startOfMonth(maxD);
    if (v < startOfMonth(minD)) v = startOfMonth(minD);
    return v;
  };
  const years = useMemo(() => {
    const lo = minD.getFullYear(), hi = maxD.getFullYear();
    return Array.from({ length: Math.max(1, hi - lo + 1) }, (_, i) => lo + i);
  }, [min, max]); // eslint-disable-line react-hooks/exhaustive-deps

  const applyPreset = (id: PresetId) => {
    const end = anchorD;
    let start: Date;
    switch (id) {
      case "day":     start = end; break;
      case "week":    start = addDays(end, -6); break;
      case "month":   start = addDays(end, -30); break;
      case "quarter": start = addDays(end, -91); break;
      case "ytd":     start = new Date(end.getFullYear(), 0, 1); break;
      case "year":    start = addDays(end, -364); break;
      case "all":     onChange({ from: toISO(minD), to: toISO(maxD) }); setView(startOfMonth(maxD)); return;
    }
    start = clamp(start, minD, maxD);
    onChange({ from: toISO(start), to: toISO(end) });
    setView(startOfMonth(end));
  };

  const activePreset = useMemo<PresetId | null>(() => {
    if (!fromD || !toD) return null;
    if (toISO(fromD) === toISO(minD) && toISO(toD) === toISO(maxD)) return "all";
    if (toISO(toD) !== toISO(anchorD)) return null;
    const byLen: Record<number, PresetId> = { 1: "day", 7: "week", 31: "month", 92: "quarter", 365: "year" };
    const hit = byLen[daysBetween(fromD, toD)];
    if (hit) return hit;
    if (fromD.getMonth() === 0 && fromD.getDate() === 1 && fromD.getFullYear() === toD.getFullYear()) return "ytd";
    return null;
  }, [value, fromD, toD, anchorD, minD, maxD]);

  // A calendar click sets whichever edge is active, then hands off to the other one —
  // so the familiar "click start, click end" flow still works, but you can also click the
  // From/To tabs to re-pick just one side.
  const pick = (d: Date) => {
    const a = fromD ?? minD, b = toD ?? maxD;
    if (editing === "from") {
      const to = d > b ? d : b;                     // dragging the start past the end takes both
      onChange({ from: toISO(d), to: toISO(to) });
      setEditing("to");
    } else {
      if (d < a) { onChange({ from: toISO(d), to: toISO(a) }); setEditing("to"); return; }
      onChange({ from: toISO(a), to: toISO(d) });
      setEditing("from");
    }
  };

  // Slider edits commit immediately and pull the calendar to the edge being moved.
  // Handles are clamped rather than swapped: a thumb that changes identity mid-drag
  // yanks the cursor away from what you grabbed.
  const setEdge = (which: "from" | "to", d: Date) => {
    const a = fromD ?? minD, b = toD ?? maxD;
    const next = which === "from"
      ? { from: clamp(d, minD, b), to: b }
      : { from: a, to: clamp(d, a, maxD) };
    onChange({ from: toISO(next.from), to: toISO(next.to) });
    setView(startOfMonth(which === "from" ? next.from : next.to));
  };

  /** Slide the whole window while keeping its length — "same 30 days, one month earlier". */
  const shiftBy = (days: number) => {
    const a = fromD ?? minD, b = toD ?? maxD;
    const len = daysBetween(a, b) - 1;
    let s = addDays(a, days);
    if (s < minD) s = minD;
    if (addDays(s, len) > maxD) s = addDays(maxD, -len);
    if (s < minD) s = minD;
    onChange({ from: toISO(s), to: toISO(clamp(addDays(s, len), minD, maxD)) });
    setView(startOfMonth(s));
  };

  // Live preview: hovering a day shows the range you'd get if you clicked it now.
  const shown = useMemo(() => {
    if (!fromD || !toD) return null;
    if (hover) {
      const a = editing === "from" ? hover : fromD;
      const b = editing === "from" ? (hover > toD ? hover : toD) : (hover < fromD ? fromD : hover);
      return a <= b ? { a, b } : { a: b, b: a };
    }
    return { a: fromD, b: toD };
  }, [fromD, toD, hover, editing]);

  const label = fmtRange(value, lang);
  const span = fromD && toD ? daysBetween(fromD, toD) : 0;

  return (
    <div className="drp" ref={box}>
      <button type="button" className={`drp-trigger${open ? " open" : ""}`}
        onClick={() => (open ? close() : setOpen(true))}
        aria-haspopup="dialog" aria-expanded={open}>
        <span className="cal" aria-hidden>▦</span>
        <span className="lbl">{label || t("dr_pick")}</span>
        {span > 0 && <span className="days">{span}{t("dr_days_suffix")}</span>}
        <span className="caret" aria-hidden>▾</span>
      </button>

      {open && (
        <div className="drp-pop" role="dialog" aria-label={t("dr_title")}>
          <div className="drp-quick">
            {PRESETS.map((p) => (
              <button key={p.id} type="button" className={activePreset === p.id ? "on" : ""}
                onClick={() => applyPreset(p.id)}>{t(p.key)}</button>
            ))}
          </div>

          <div className="drp-body">
            {/* Explicit range selection: pick which end you are setting. */}
            <div className="drp-edges" role="tablist">
              {(["from", "to"] as const).map((w) => {
                const d = w === "from" ? fromD : toD;
                return (
                  <button key={w} type="button" role="tab" aria-selected={editing === w}
                    className={`edge${editing === w ? " on" : ""}`}
                    onClick={() => focusEdge(w)}>
                    <span className="k">{t(w === "from" ? "dr_from" : "dr_to")}</span>
                    <span className="v">{d ? fmtDay(d, lang) : "—"}</span>
                  </button>
                );
              })}
              <span className="edgearrow" aria-hidden>→</span>
            </div>

            <div className="drp-nav">
              <button type="button" onClick={() => setView(addMonths(view, -1))}
                disabled={startOfMonth(view) <= startOfMonth(minD)} aria-label={t("dr_prev")}>
                <span className="chev">‹</span>
              </button>
              <div className="drp-jump">
                <select value={view.getMonth()} aria-label={t("dr_month")}
                  onChange={(e) => setView(viewClamped(new Date(view.getFullYear(), +e.target.value, 1)))}>
                  {Array.from({ length: 12 }, (_, m) => (
                    <option key={m} value={m}>
                      {new Date(2024, m, 1).toLocaleDateString(locale(lang), { month: "long" })}
                    </option>
                  ))}
                </select>
                <select value={view.getFullYear()} aria-label={t("dr_year")}
                  onChange={(e) => setView(viewClamped(new Date(+e.target.value, view.getMonth(), 1)))}>
                  {years.map((y) => <option key={y} value={y}>{y}</option>)}
                </select>
              </div>
              <button type="button" onClick={() => setView(addMonths(view, 1))}
                disabled={startOfMonth(view) >= startOfMonth(maxD)} aria-label={t("dr_next")}>
                <span className="chev">›</span>
              </button>
            </div>

            <Month month={view} lang={lang} range={shown} min={minD} max={maxD}
              editing={editing} from={fromD} to={toD}
              onPick={pick} onHover={setHover} />

            <RangeSlider min={minD} max={maxD} from={fromD ?? minD} to={toD ?? maxD}
              lang={lang} onEdge={setEdge} onShift={shiftBy} t={t} />

            <div className="drp-foot">
              <div className="fields">
                <input type="date" value={value.from} min={toISO(minD)} max={value.to || toISO(maxD)}
                  onChange={(e) => onChange({ ...value, from: e.target.value })} aria-label={t("dr_from")} />
                <span className="arrow">→</span>
                <input type="date" value={value.to} min={value.from || toISO(minD)} max={toISO(maxD)}
                  onChange={(e) => onChange({ ...value, to: e.target.value })} aria-label={t("dr_to")} />
              </div>
              <div className="spacer" />
              <span className="drp-hint picking">
                {t(editing === "from" ? "dr_setting_from" : "dr_setting_to")}
              </span>
              <button type="button" className="primary" onClick={close}>{t("dr_done")}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------- slider ---- */
/**
 * Dual-handle timeline over the whole data span. Dragging is the fast way to reshape a
 * range; the calendar above stays in sync for precise days. Forced LTR so the geometry
 * is identical under Hebrew.
 */
function RangeSlider({ min, max, from, to, lang, onEdge, onShift, t }: {
  min: Date; max: Date; from: Date; to: Date; lang: string;
  onEdge: (which: "from" | "to", d: Date) => void;
  onShift: (days: number) => void;
  t: (k: TKey) => string;
}) {
  const track = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<null | "from" | "to" | "band">(null);
  const grabbed = useRef(0);                       // day-offset inside the band when grabbed
  const total = Math.max(1, daysBetween(min, max) - 1);
  const pctOf = (d: Date) => (daysBetween(min, d) - 1) / total * 100;
  const l = Math.max(0, Math.min(100, pctOf(from)));
  const r = Math.max(0, Math.min(100, pctOf(to)));
  const len = daysBetween(from, to);

  const dayAt = (clientX: number) => {
    const box = track.current!.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (clientX - box.left) / box.width));
    return Math.round(pct * total);
  };
  const dateAt = (clientX: number) => addDays(min, dayAt(clientX));

  const startEdge = (which: "from" | "to") => (e: React.PointerEvent) => {
    e.preventDefault(); e.stopPropagation();
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
    setDrag(which);
  };
  const startBand = (e: React.PointerEvent) => {
    e.preventDefault(); e.stopPropagation();
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
    grabbed.current = dayAt(e.clientX) - (daysBetween(min, from) - 1);
    setDrag("band");
  };
  const move = (e: React.PointerEvent) => {
    if (!drag) return;
    if (drag === "band") onShift(dayAt(e.clientX) - grabbed.current - (daysBetween(min, from) - 1));
    else onEdge(drag, dateAt(e.clientX));
  };
  const end = () => setDrag(null);

  // Click on empty track moves whichever handle is nearer.
  const jump = (e: React.PointerEvent) => {
    if (drag) return;
    const d = dateAt(e.clientX);
    const nearer = Math.abs(daysBetween(from, d)) <= Math.abs(daysBetween(to, d)) ? "from" : "to";
    onEdge(nearer, d);
  };

  const key = (which: "from" | "to", cur: Date) => (e: React.KeyboardEvent) => {
    const step = e.key === "ArrowLeft" ? -1 : e.key === "ArrowRight" ? 1
      : e.key === "PageDown" ? -30 : e.key === "PageUp" ? 30 : 0;
    if (!step) return;
    e.preventDefault();
    onEdge(which, clamp(addDays(cur, step), min, max));
  };
  const bandKey = (e: React.KeyboardEvent) => {
    const step = e.key === "ArrowLeft" ? -1 : e.key === "ArrowRight" ? 1
      : e.key === "PageDown" ? -30 : e.key === "PageUp" ? 30 : 0;
    if (!step) return;
    e.preventDefault();
    onShift(step);
  };

  return (
    <div className="drp-slider ltr">
      <div className={`strack${drag ? " dragging" : ""}`} ref={track}
        onPointerMove={move} onPointerUp={end} onPointerCancel={end} onPointerDown={jump}>
        {/* The band is grabbable: slide the whole window without changing its length. */}
        <div className={`sfill${drag === "band" ? " on" : ""}`} role="button" tabIndex={0}
          style={{ left: `${l}%`, width: `${Math.max(0, r - l)}%` }}
          onPointerDown={startBand} onKeyDown={bandKey}
          aria-label={t("dr_shift")} title={t("dr_shift")}>
          <span className="grip" />
        </div>
        {(["from", "to"] as const).map((w) => {
          const d = w === "from" ? from : to;
          return (
            <button key={w} type="button" className={`sthumb${drag === w ? " on" : ""}`}
              style={{ left: `${w === "from" ? l : r}%` }}
              onPointerDown={startEdge(w)} onKeyDown={key(w, d)}
              role="slider" aria-valuemin={0} aria-valuemax={total}
              aria-valuenow={daysBetween(min, d) - 1} aria-valuetext={fmtDay(d, lang)}
              aria-label={w === "from" ? t("dr_from") : t("dr_to")}>
              <span className="bubble">{fmtShort(d, lang)}</span>
            </button>
          );
        })}
      </div>
      <div className="sends">
        <span>{fmtShort(min, lang)}</span>
        <span className={`slen${drag ? " on" : ""}`}>{len} {t("dr_days")}</span>
        <span>{fmtShort(max, lang)}</span>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- month -- */
function Month({ month, lang, range, min, max, editing, from, to, onPick, onHover }: {
  month: Date; lang: string;
  range: { a: Date; b: Date } | null;
  min: Date | null; max: Date | null;
  editing: "from" | "to"; from: Date | null; to: Date | null;
  onPick: (d: Date) => void; onHover: (d: Date | null) => void;
}) {
  const first = startOfMonth(month);
  const lead = first.getDay();
  const len = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const today = toISO(new Date());
  const cells = [...Array(lead).fill(null), ...Array.from({ length: len }, (_, i) =>
    new Date(month.getFullYear(), month.getMonth(), i + 1))];

  return (
    <div className="drp-cal">
      <div className="drp-grid" aria-hidden>
        {dowNames(lang).map((d, i) => <div key={i} className="drp-dow">{d}</div>)}
      </div>
      <div className="drp-grid" onMouseLeave={() => onHover(null)}>
        {cells.map((d, i) => {
          if (!d) return <span key={i} className="drp-day off" />;
          const iso = toISO(d);
          const disabled = (!!min && d < min) || (!!max && d > max);
          const inRange = !!range && d >= range.a && d <= range.b;
          const isStart = !!range && iso === toISO(range.a);
          const isEnd = !!range && iso === toISO(range.b);
          // Ring the edge you're currently setting, so the active end is obvious.
          const armed = (editing === "from" && from && iso === toISO(from))
            || (editing === "to" && to && iso === toISO(to));
          const cls = ["drp-day",
            iso === today ? "today" : "",
            inRange && !isStart && !isEnd ? "inrange" : "",
            isStart || isEnd ? "edge" : "",
            isStart ? "edge-start" : "", isEnd ? "edge-end" : "",
            armed ? "armed" : ""].filter(Boolean).join(" ");
          return (
            <button key={i} type="button" className={cls} disabled={disabled}
              onClick={() => onPick(d)} onMouseEnter={() => onHover(d)}
              aria-label={iso} aria-pressed={inRange}>
              {d.getDate()}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------ formatting -- */
const locale = (lang: string) => (lang === "he" ? "he-IL" : "en-US");

const fmtDay = (d: Date, lang: string) =>
  d.toLocaleDateString(locale(lang), { day: "2-digit", month: "short", year: "numeric" });

const fmtShort = (d: Date, lang: string) =>
  d.toLocaleDateString(locale(lang), { day: "2-digit", month: "short" });

function dowNames(lang: string) {
  const base = new Date(2024, 0, 7);                             // a Sunday
  return Array.from({ length: 7 }, (_, i) =>
    addDays(base, i).toLocaleDateString(locale(lang), { weekday: "narrow" }));
}

export function fmtRange(r: DateRange, lang: string): string {
  const a = parse(r.from), b = parse(r.to);
  if (!a || !b) return "";
  const opts: Intl.DateTimeFormatOptions = { day: "2-digit", month: "short" };
  const sameYear = a.getFullYear() === b.getFullYear();
  const l = locale(lang);
  const A = a.toLocaleDateString(l, sameYear ? opts : { ...opts, year: "numeric" });
  const B = b.toLocaleDateString(l, { ...opts, year: "numeric" });
  return A === B ? B : `${A} → ${B}`;
}
