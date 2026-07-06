import { useState } from "react";
import type { Candidate } from "../types";
import { frontExpiry, num, shortStrikes, strategyColor, strategyLabel } from "../lib";

const VERDICT: Record<string, { label: string; color: string }> = {
  take: { label: "לפתוח", color: "#4fb187" },
  caution: { label: "בזהירות", color: "#d6a854" },
  pass: { label: "לוותר", color: "#e06e60" },
};

function Metric({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-[9px] uppercase tracking-wider text-slate-500 font-mono">{label}</span>
      <span className="text-sm font-mono tabular-nums" style={{ color: tone }}>
        {value}
      </span>
    </div>
  );
}

function OpenButton({ onOpen }: { onOpen: () => Promise<void> }) {
  const [state, setState] = useState<"idle" | "opening" | "opened" | "error">("idle");

  const click = async (e: React.MouseEvent) => {
    e.stopPropagation();   // don't also trigger the card's select-for-details click
    if (state !== "idle") return;
    setState("opening");
    try {
      await onOpen();
      setState("opened");
    } catch {
      setState("error");
    }
  };

  const label = { idle: "פתח פוזיציה", opening: "פותח…", opened: "נפתחה ✓", error: "שגיאה" }[state];
  const tone = { idle: "#4fb187", opening: "#8a94a1", opened: "#4fb187", error: "#e06e60" }[state];

  return (
    <button
      onClick={click}
      disabled={state !== "idle"}
      className="text-[11px] font-mono px-2.5 py-1 rounded-full border transition disabled:cursor-default"
      style={{ borderColor: `${tone}55`, color: tone, background: `${tone}15` }}
    >
      {label}
    </button>
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
    return <div className="text-slate-500 text-sm">Waiting for the first scan…</div>;
  }
  return (
    <div className="grid gap-3">
      {trades.map((c, i) => {
        const dacs = c.strategy === "dacs";
        const active = i === selected;
        return (
          <div
            key={i}
            onClick={() => onSelect(i)}
            className={`cursor-pointer rounded-xl border p-4 transition ${
              active ? "border-accent bg-panel" : "border-line bg-panel/50 hover:border-slate-500"
            }`}
          >
            <div className="flex items-center gap-3">
              <span className="text-slate-500 font-mono text-sm w-5">{i + 1}</span>
              <span className="font-mono font-semibold text-base w-16">{c.underlying}</span>
              <span
                className="text-xs font-mono px-2 py-0.5 rounded-full"
                style={{ background: `${strategyColor(c.strategy)}22`, color: strategyColor(c.strategy) }}
              >
                {strategyLabel(c.strategy)}
              </span>
              {c.verdict && (
                <span
                  className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full"
                  style={{ background: `${VERDICT[c.verdict].color}22`, color: VERDICT[c.verdict].color }}
                >
                  {VERDICT[c.verdict].label}
                </span>
              )}
              <span className="font-mono text-xs text-slate-400 ml-auto flex items-center gap-2">
                <span className="text-slate-300">{dacs ? "sell 1mo · buy 2mo" : `short ${shortStrikes(c)}`}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5">⏱ {frontExpiry(c)}</span>
              </span>
            </div>

            <div className="mt-3 flex items-end gap-3 pl-8">
              <div className="grid grid-cols-4 gap-3 flex-1">
                {dacs ? (
                  <>
                    <Metric label="short call" value={String(shortStrikes(c))} />
                    <Metric
                      label="fast ratio"
                      value={`${((num(c.meta, "fast_ratio") ?? 0) * 100).toFixed(0)}%`}
                      tone="#4fb187"
                    />
                    <Metric label="stop" value={String(num(c.meta, "stop_conservative") ?? "—")} tone="#e06e60" />
                    <Metric label="OTM" value={`${num(c.meta, "otm_pct") ?? "—"}%`} />
                  </>
                ) : (
                  <>
                    <Metric label="POP" value={`${(c.pop * 100).toFixed(0)}%`} />
                    <Metric label="credit" value={c.credit.toFixed(2)} tone="#4fb187" />
                    <Metric label="max loss" value={c.max_loss.toFixed(2)} tone="#e06e60" />
                    <Metric label="width" value={c.width.toFixed(0)} />
                  </>
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
