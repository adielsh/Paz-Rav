import type { Feature } from "../types";

function IvGauge({ rank }: { rank: number }) {
  const pct = Math.max(0, Math.min(100, rank));
  const color = pct >= 50 ? "#4fb187" : "#7d8aa0";
  return (
    <div className="mt-2">
      <div className="flex justify-between text-[10px] text-slate-400 font-mono">
        <span>IV RANK</span>
        <span style={{ color }}>{pct.toFixed(0)}</span>
      </div>
      <div className="h-1.5 rounded-full bg-slate-700/60 mt-1 overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

export default function MarketOverview({
  features,
  selected,
  onSelect,
}: {
  features: Record<string, Feature>;
  selected: string | null;
  onSelect: (u: string) => void;
}) {
  const rows = Object.values(features);
  if (rows.length === 0) {
    return <div className="text-slate-500 text-sm">Waiting for the first scan…</div>;
  }
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      {rows.map((f) => {
        const friendly = f.regime.startsWith("range") && f.regime.endsWith("high-vol");
        const active = f.underlying === selected;
        return (
          <button
            key={f.underlying}
            onClick={() => onSelect(f.underlying)}
            className={`text-left rounded-xl border p-3 transition ${
              active ? "border-accent bg-panel" : "border-line bg-panel/60 hover:border-slate-500"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="font-mono font-semibold">{f.underlying}</span>
              <span
                className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${
                  friendly ? "bg-good/15 text-good" : "bg-slate-600/30 text-slate-300"
                }`}
              >
                {friendly ? "CONDOR OK" : "WAIT"}
              </span>
            </div>
            <div className="mt-1 text-lg font-mono tabular-nums">{f.spot.toFixed(2)}</div>
            <div className="text-[11px] text-slate-400">{f.regime}</div>
            <IvGauge rank={f.iv_rank} />
            <div className="mt-2 text-[10px] font-mono text-slate-400">
              ±{f.expected_move.toFixed(1)} exp.move
            </div>
          </button>
        );
      })}
    </div>
  );
}
