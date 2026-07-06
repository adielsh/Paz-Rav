import { useState, type KeyboardEvent, type MouseEvent } from "react";
import type { Candidate } from "../types";
import { colors } from "../theme";
import { frontExpiry, num, strategyColor, strategyLabel } from "../lib";
import LegLadder from "./LegLadder";
import { IconCheckCircle, IconClock } from "./Icon";

const VERDICT: Record<string, { label: string; color: string }> = {
  take: { label: "לפתוח", color: colors.good },
  caution: { label: "בזהירות", color: colors.warn },
  pass: { label: "לוותר", color: colors.bad },
};

function OpenButton({ onOpen }: { onOpen: () => Promise<void> }) {
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
  const tone = { idle: colors.good, opening: colors.ink2, opened: colors.good, error: colors.bad }[state];

  return (
    <button
      type="button"
      onClick={click}
      onKeyDown={(e) => e.stopPropagation()}
      disabled={state === "opening" || state === "opened"}
      aria-live="polite"
      className="shrink-0 inline-flex items-center gap-1.5 text-xs font-mono font-semibold px-3 py-1.5 rounded-lg border"
      style={{ borderColor: `${tone}66`, color: tone, background: `${tone}18` }}
    >
      {state === "opened" && <IconCheckCircle width={13} height={13} />}
      {label}
    </button>
  );
}

/** One clean metrics line — a few key numbers separated by a middot, not a boxy grid. */
function MetricLine({ items }: { items: [string, string, string?][] }) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-2.5 text-[13px] font-mono">
      {items.map(([label, value, tone], i) => (
        <span key={label} className="flex items-baseline gap-1.5">
          {i > 0 && <span className="text-ink-3">·</span>}
          <span className="text-ink-2">{label}</span>
          <span className="font-semibold tabular-nums" style={{ color: tone ?? colors.ink }}>
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
  if (trades.length === 0) {
    return <div className="text-ink-2 text-sm">Waiting for the first scan…</div>;
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>, i: number) => {
    // ignore key events bubbling up from a nested control (e.g. the Open button)
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
        return (
          <div
            key={i}
            role="button"
            tabIndex={0}
            onClick={() => onSelect(i)}
            onKeyDown={(e) => handleKeyDown(e, i)}
            aria-pressed={active}
            className={`rounded-xl border p-4 transition ${
              active
                ? "border-accent bg-panel shadow-elevated"
                : "border-line bg-panel/60 hover:border-lineStrong hover:bg-panel"
            }`}
          >
            <div className="flex items-center gap-2 mb-3">
              <span className="text-ink-3 font-mono text-sm tabular-nums">{i + 1}</span>
              <span className="font-mono font-bold text-lg tracking-tight">{c.underlying}</span>
              <span
                className="text-xs font-mono px-2 py-0.5 rounded-full"
                style={{ background: `${strategyColor(c.strategy)}22`, color: strategyColor(c.strategy) }}
              >
                {strategyLabel(c.strategy)}
              </span>
              {c.verdict && (
                <span
                  className="text-[11px] font-bold px-2 py-0.5 rounded-full"
                  style={{ background: VERDICT[c.verdict].color, color: colors.bg }}
                >
                  {VERDICT[c.verdict].label}
                </span>
              )}
              <span className="inline-flex items-center gap-1 text-[11px] font-mono text-ink-2 ml-auto">
                <IconClock width={12} height={12} />
                {frontExpiry(c)}
              </span>
            </div>

            <LegLadder legs={c.legs} />

            <div className="flex items-center justify-between mt-3 gap-3">
              {dacs ? (
                <MetricLine
                  items={[
                    ["Fast Ratio", `${((num(c.meta, "fast_ratio") ?? 0) * 100).toFixed(0)}%`, colors.good],
                    ["סטופ", String(num(c.meta, "stop_conservative") ?? "—"), colors.bad],
                    ["OTM", `${num(c.meta, "otm_pct") ?? "—"}%`],
                  ]}
                />
              ) : (
                <MetricLine
                  items={[
                    ["סיכוי", `${(c.pop * 100).toFixed(0)}%`],
                    ["קרדיט", `+${c.credit.toFixed(2)}`, colors.good],
                    ["הפסד מקס", `-${c.max_loss.toFixed(2)}`, colors.bad],
                  ]}
                />
              )}
              <OpenButton onOpen={() => onOpenPosition(c)} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
