import type { Position } from "../types";
import { closeReasonLabel, shortStrikes, strategyColor, strategyLabel } from "../lib";

function Pnl({ value }: { value: number | null | undefined }) {
  if (value == null) return <span className="text-slate-500">—</span>;
  return (
    <span className={value >= 0 ? "text-good" : "text-bad"}>
      {value >= 0 ? "+" : ""}
      {value.toFixed(2)}
    </span>
  );
}

export default function Positions({ positions }: { positions: Position[] }) {
  const open = positions.filter((p) => p.status === "open");
  const closed = positions.filter((p) => p.status === "closed");

  if (positions.length === 0) {
    return (
      <div className="rounded-xl border border-line bg-panel/40 p-4">
        <h2 className="text-[11px] uppercase tracking-wider text-slate-500 font-mono mb-2">
          Open positions
        </h2>
        <div className="text-slate-500 text-sm">
          No positions yet — open one from a suggestion above.
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-line bg-panel/40 p-4">
      <h2 className="text-[11px] uppercase tracking-wider text-slate-500 font-mono mb-3">
        Positions {open.length > 0 && <span className="text-accent">· {open.length} open</span>}
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="text-left text-[10px] uppercase tracking-wider text-slate-400 font-mono">
              <th className="py-2 pr-3">status</th>
              <th className="py-2 pr-3">underlying</th>
              <th className="py-2 pr-3">strategy</th>
              <th className="py-2 pr-3">strikes</th>
              <th className="py-2 pr-3">opened</th>
              <th className="py-2 pr-3 text-right">P&L</th>
              <th className="py-2 pr-3">closed by</th>
            </tr>
          </thead>
          <tbody className="font-mono tabular-nums">
            {[...open, ...closed].map((p) => (
              <tr key={p.id} className="border-t border-line/60">
                <td className="py-2 pr-3">
                  <span
                    className={`inline-block w-2 h-2 rounded-full ${
                      p.status === "open" ? "bg-good" : "bg-slate-500"
                    }`}
                  />
                </td>
                <td className="py-2 pr-3">{p.underlying}</td>
                <td className="py-2 pr-3" style={{ color: strategyColor(p.strategy) }}>
                  {strategyLabel(p.strategy)}
                </td>
                <td className="py-2 pr-3 text-slate-300">{shortStrikes(p)}</td>
                <td className="py-2 pr-3 text-slate-400">
                  {new Date(p.opened_at).toLocaleDateString()}
                </td>
                <td className="py-2 pr-3 text-right">
                  <Pnl value={p.status === "open" ? p.unrealized_pnl : p.realized_pnl} />
                </td>
                <td className="py-2 pr-3 text-slate-400">
                  {p.status === "closed" ? closeReasonLabel(p.close_reason) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
