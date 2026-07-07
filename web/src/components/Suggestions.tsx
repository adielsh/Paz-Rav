import { useState, type KeyboardEvent, type MouseEvent } from "react";
import type { Candidate } from "../types";
import { useThemeColors } from "../theme-context";
import { frontExpiry, num, strategyColor, strategyLabel } from "../lib";
import { pct, usdContractSigned, usdStrike } from "../format";
import LegLadder from "./LegLadder";
import { IconCheckCircle, IconClock } from "./Icon";

const VERDICT_LABEL: Record<string, string> = { take: "לפתוח", caution: "בזהירות", pass: "לוותר" };

function OpenButton({ onOpen }: { onOpen: () => Promise<void> }) {
  const p = useThemeColors();
  const [state, setState] = useState<"idle" | "opening" | "opened" | "error">("idle");

  const click = async (e: MouseEvent) => {
    e.stopPropagation();
    if (state !== "idle") return;
    setState("opening");
    try {
      await onOpen();
      setState("opened");
    } catch {
      setState("error");
    }
  };

  const label = { idle: "פתח פוזיציה", opening: "פותח…", opened: "נפתחה", error: "שגיאה, נסה שוב" }[state];
  const tone = { idle: p.good, opening: p.ink2, opened: p.good, error: p.bad }[state];

  return (
    <button
      type="button"
      onClick={click}
      onKeyDown={(e) => e.stopPropagation()}
      disabled={state === "opening" || state === "opened"}
      aria-live="polite"
      className="shrink-0 inline-flex items-center gap-1.5 text-xs font-mono font-semibold px-3 py-1.5 rounded-lg border hover:brightness-105 active:scale-[0.97]"
      style={{ borderColor: `${tone}66`, color: tone, background: `${tone}18` }}
    >
      {state === "opened" && <IconCheckCircle width={13} height={13} />}
      {label}
    </button>
  );
}

/** A headline number (the metric that decides the trade) plus supporting figures at a
 * smaller weight — hierarchy by size/weight, not a wall of equal-weight numbers. */
function HeadlineStat({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="shrink-0 text-right">
      <div className="text-2xs uppercase tracking-wider text-ink-3 font-mono">{label}</div>
      <div className="text-2xl font-bold font-mono tabular-nums leading-tight" style={{ color: tone }}>
        {value}
      </div>
    </div>
  );
}

function MetricLine({ items }: { items: [string, string, string?][] }) {
  const p = useThemeColors();
  return (
    <div className="flex flex-wrap items-baseline gap-x-2.5 text-[13px] font-mono">
      {items.map(([label, value, tone], i) => (
        <span key={label} className="flex items-baseline gap-1.5">
          {i > 0 && <span className="text-ink-3">·</span>}
          <span className="text-ink-2">{label}</span>
          <span className="font-semibold tabular-nums" style={{ color: tone ?? p.ink }}>
            {value}
          </span>
        </span>
      ))}
    </div>
  );
}

export default function Suggestions({
  trades,
  selected,
  onSelect,
  onOpenPosition,
}: {
  trades: Candidate[];
  selected: number;
  onSelect: (i: number) => void;
  onOpenPosition: (c: Candidate) => Promise<void>;
}) {
  const p = useThemeColors();
  const verdictColor: Record<string, string> = { take: p.good, caution: p.warn, pass: p.bad };

  if (trades.length === 0) {
    return <div className="text-ink-2 text-sm">ממתין לסריקה הראשונה…</div>;
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>, i: number) => {
    if (e.target !== e.currentTarget) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelect(i);
    }
  };

  return (
    <div className="grid gap-3">
      {trades.map((c, i) => {
        const dacs = c.strategy === "dacs";
        const active = i === selected;
        const rail = strategyColor(c.strategy, p);
        return (
          <div
            key={i}
            role="button"
            tabIndex={0}
            onClick={() => onSelect(i)}
            onKeyDown={(e) => handleKeyDown(e, i)}
            aria-pressed={active}
            className={`relative overflow-hidden rounded-xl border pl-5 pr-4 py-4 transition-all shadow-card ${
              active
                ? "border-primary/50 bg-panel -translate-y-0.5"
                : "border-line bg-panel/60 hover:border-lineStrong hover:bg-panel hover:-translate-y-0.5"
            }`}
            style={
              active
                ? { boxShadow: `0 0 0 1px ${rail}33, 0 14px 34px -12px ${rail}66` }
                : undefined
            }
          >
            <span className="absolute inset-y-0 left-0 w-1" style={{ background: rail }} aria-hidden="true" />

            <div className="flex items-start justify-between gap-3 mb-3">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-ink-3 font-mono text-sm tabular-nums">{i + 1}</span>
                <span className="font-mono font-bold text-lg tracking-tight text-ink">{c.underlying}</span>
                {num(c.meta, "spot") != null && (
                  <span className="text-xs font-mono text-ink-2 tabular-nums" title="מחיר הנכס בזמן הסריקה">
                    {usdStrike(num(c.meta, "spot"))}
                  </span>
                )}
                <span
                  className="text-xs font-mono px-2 py-0.5 rounded-full"
                  style={{ background: `${rail}22`, color: rail }}
                >
                  {strategyLabel(c.strategy)}
                </span>
                {c.verdict && (
                  <span
                    className="text-[11px] font-bold px-2 py-0.5 rounded-full text-white"
                    style={{ background: verdictColor[c.verdict] }}
                  >
                    {VERDICT_LABEL[c.verdict]}
                  </span>
                )}
              </div>
              {dacs ? (
                <HeadlineStat label="Fast Ratio" value={pct(num(c.meta, "fast_ratio") ?? 0)} tone={p.good} />
              ) : (
                <HeadlineStat label="סיכוי" value={pct(c.pop)} tone={p.info} />
              )}
            </div>

            <LegLadder legs={c.legs} />

            <div className="flex items-center justify-between mt-3 gap-3">
              <div className="flex items-center gap-3">
                <span className="inline-flex items-center gap-1 text-[11px] font-mono text-ink-3">
                  <IconClock width={12} height={12} />
                  {frontExpiry(c)}
                </span>
                {dacs ? (
                  <MetricLine
                    items={[
                      ["סטופ", usdStrike(num(c.meta, "stop_conservative")), p.bad],
                      ["OTM", `${num(c.meta, "otm_pct") ?? "—"}%`],
                    ]}
                  />
                ) : (
                  <MetricLine
                    items={[
                      ["קרדיט", usdContractSigned(c.credit), p.good],
                      ["הפסד מקס", usdContractSigned(-c.max_loss), p.bad],
                    ]}
                  />
                )}
              </div>
              <OpenButton onOpen={() => onOpenPosition(c)} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
