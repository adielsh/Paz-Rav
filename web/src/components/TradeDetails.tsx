import type { Candidate, PayoffPoint } from "../types";
import { frontExpiry, num, strategyColor, strategyLabel } from "../lib";
import PayoffChart from "./PayoffChart";

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-lg bg-panel/70 border border-line px-3 py-2">
      <div className="text-[9px] uppercase tracking-wider text-slate-500 font-mono">{label}</div>
      <div className="font-mono text-sm tabular-nums" style={{ color: tone }}>
        {value}
      </div>
    </div>
  );
}

export default function TradeDetails({
  candidate,
  points,
  explanation,
}: {
  candidate: Candidate | null;
  points: PayoffPoint[];
  explanation: string;
}) {
  if (!candidate) {
    return (
      <div className="h-full grid place-items-center text-slate-500 text-sm">
        Select a suggestion to see its legs, payoff and plan.
      </div>
    );
  }
  const c = candidate;
  const dacs = c.strategy === "dacs";

  return (
    <div>
      <div className="flex items-center gap-3 mb-3">
        <span className="font-mono font-semibold text-lg">{c.underlying}</span>
        <span
          className="text-xs font-mono px-2 py-0.5 rounded-full"
          style={{ background: `${strategyColor(c.strategy)}22`, color: strategyColor(c.strategy) }}
        >
          {strategyLabel(c.strategy)}
        </span>
        <span className="text-xs text-slate-400 font-mono ml-auto">⏱ {frontExpiry(c)} · DTE {c.dte}</span>
      </div>

      {/* AI plain-language explanation — clear to a child */}
      <div className="rounded-lg bg-accent/10 border border-accent/30 p-3 mb-4 text-[13px] leading-relaxed" dir="rtl">
        {explanation ? explanation : <span className="text-slate-500">טוען הסבר…</span>}
      </div>

      {/* legs */}
      <table className="w-full text-xs font-mono mb-4">
        <thead className="text-slate-500">
          <tr className="text-left">
            <th className="py-1">action</th>
            <th>type</th>
            <th className="text-right">strike</th>
            <th className="text-right">expiry</th>
          </tr>
        </thead>
        <tbody>
          {c.legs.map((l, i) => (
            <tr key={i} className="border-t border-line/50">
              <td className={`py-1 ${l.side === "sell" ? "text-bad" : "text-good"}`}>{l.side}</td>
              <td>{l.option_type}</td>
              <td className="text-right tabular-nums">{l.strike}</td>
              <td className="text-right text-slate-400">{l.expiry ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* stats */}
      <div className="grid grid-cols-3 gap-2 mb-4">
        {dacs ? (
          <>
            <Stat label="debit" value={String(num(c.meta, "long_debit") ?? Math.abs(c.credit).toFixed(2))} tone="#e06e60" />
            <Stat label="fast ratio" value={`${((num(c.meta, "fast_ratio") ?? 0) * 100).toFixed(0)}%`} tone="#4fb187" />
            <Stat label="max loss" value={c.max_loss.toFixed(2)} tone="#e06e60" />
            <Stat label="stop (conserv.)" value={String(num(c.meta, "stop_conservative") ?? "—")} tone="#e06e60" />
            <Stat label="stop (aggr.)" value={String(num(c.meta, "stop_aggressive") ?? "—")} />
            <Stat label="short OTM" value={`${num(c.meta, "otm_pct") ?? "—"}%`} />
          </>
        ) : (
          <>
            <Stat label="credit" value={c.credit.toFixed(2)} tone="#4fb187" />
            <Stat label="max profit" value={c.max_profit.toFixed(2)} tone="#4fb187" />
            <Stat label="max loss" value={c.max_loss.toFixed(2)} tone="#e06e60" />
            <Stat label="POP" value={`${(c.pop * 100).toFixed(0)}%`} />
            <Stat label="breakevens" value={c.breakevens.map((b) => b.toFixed(0)).join(" / ")} />
            <Stat label="width" value={c.width.toFixed(0)} />
          </>
        )}
      </div>

      {dacs && (
        <div className="text-[11px] text-slate-400 mb-4 leading-relaxed border-l-2 border-accent/50 pl-3">
          <b className="text-slate-200">סגירה אוטומטית:</b> קבע פקודת רווח מותנית כבר עכשיו (למשל
          קנית ב־30¢ → מכירה ב־~1.1$). אם מתקרבים לסטופ — מורידים את הפקודה או יוצאים במרקט.
          נשתדל לסגור ~שבועיים לפני הפקיעה, לא לחכות לרגע האחרון.
        </div>
      )}

      <PayoffChart points={points} candidate={c} />
    </div>
  );
}
