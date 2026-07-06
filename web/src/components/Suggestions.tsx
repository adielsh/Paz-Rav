import type { Candidate } from "../types";
import { frontExpiry, num, shortStrikes, strategyColor, strategyLabel } from "../lib";

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

export default function Suggestions({
  trades,
  selected,
  onSelect,
}: {
  trades: Candidate[];
  selected: number;
  onSelect: (i: number) => void;
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
          <button
            key={i}
            onClick={() => onSelect(i)}
            className={`text-left rounded-xl border p-4 transition ${
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
              <span className="font-mono text-xs text-slate-400 ml-auto flex items-center gap-2">
                <span className="text-slate-300">{dacs ? "sell 1mo · buy 2mo" : `short ${shortStrikes(c)}`}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5">⏱ {frontExpiry(c)}</span>
              </span>
            </div>

            <div className="mt-3 grid grid-cols-4 gap-3 pl-8">
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
          </button>
        );
      })}
    </div>
  );
}
