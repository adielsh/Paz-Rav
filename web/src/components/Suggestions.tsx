import { useState } from "react";
import type { Candidate } from "../types";
import { frontExpiry, num, strategyColor, strategyLabel } from "../lib";
import LegLadder from "./LegLadder";

const VERDICT: Record<string, { label: string; color: string }> = {
  take: { label: "לפתוח", color: "#4fb187" },
  caution: { label: "בזהירות", color: "#d6a854" },
  pass: { label: "לוותר", color: "#e06e60" },
};

function OpenButton({ onOpen }: { onOpen: () => Promise<void> }) {
  const [state, setState] = useState<"idle" | "opening" | "opened" | "error">("idle");

  const click = async (e: React.MouseEvent) => {
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

  const label = { idle: "פתח פוזיציה", opening: "פותח…", opened: "נפתחה ✓", error: "שגיאה, נסה שוב" }[state];
  const tone = { idle: "#4fb187", opening: "#8a94a1", opened: "#4fb187", error: "#e06e60" }[state];

  return (
    <button
      onClick={click}
      disabled={state === "opening" || state === "opened"}
      className="shrink-0 text-[12px] font-mono font-semibold px-3 py-1.5 rounded-lg border transition disabled:cursor-default"
      style={{ borderColor: `${tone}66`, color: tone, background: `${tone}18` }}
    >
      {label}
    </button>
  );
}

/** One clean metrics line — a few key numbers separated by a middot, not a boxy grid. */
function MetricLine({ items }: { items: [string, string, string?][] }) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-2 text-[13px] font-mono">
      {items.map(([label, value, tone], i) => (
        <span key={label} className="flex items-baseline gap-1">
          {i > 0 && <span className="text-slate-600 mx-1">·</span>}
          <span className="text-slate-500">{label}</span>
          <span className="font-semibold" style={{ color: tone }}>{value}</span>
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
            <div className="flex items-center gap-2 mb-3">
              <span className="text-slate-500 font-mono text-sm">{i + 1}</span>
              <span className="font-mono font-bold text-lg">{c.underlying}</span>
              <span
                className="text-xs font-mono px-2 py-0.5 rounded-full"
                style={{ background: `${strategyColor(c.strategy)}22`, color: strategyColor(c.strategy) }}
              >
                {strategyLabel(c.strategy)}
              </span>
              {c.verdict && (
                <span
                  className="text-[11px] font-bold px-2 py-0.5 rounded-full"
                  style={{ background: VERDICT[c.verdict].color, color: "#0c111a" }}
                >
                  {VERDICT[c.verdict].label}
                </span>
              )}
              <span className="text-[11px] font-mono text-slate-400 ml-auto">⏱ {frontExpiry(c)}</span>
            </div>

            <LegLadder legs={c.legs} />

            <div className="flex items-center justify-between mt-3 gap-3">
              {dacs ? (
                <MetricLine
                  items={[
                    ["Fast Ratio", `${((num(c.meta, "fast_ratio") ?? 0) * 100).toFixed(0)}%`, "#4fb187"],
                    ["סטופ", String(num(c.meta, "stop_conservative") ?? "—"), "#e06e60"],
                    ["OTM", `${num(c.meta, "otm_pct") ?? "—"}%`],
                  ]}
                />
              ) : (
                <MetricLine
                  items={[
                    ["סיכוי", `${(c.pop * 100).toFixed(0)}%`],
                    ["קרדיט", `+${c.credit.toFixed(2)}`, "#4fb187"],
                    ["הפסד מקס", `-${c.max_loss.toFixed(2)}`, "#e06e60"],
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
