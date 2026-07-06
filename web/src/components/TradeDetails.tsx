import type { Candidate, PayoffPoint, Review } from "../types";
import { frontExpiry, num, strategyColor, strategyLabel } from "../lib";
import PayoffChart from "./PayoffChart";

const VERDICT: Record<string, { label: string; color: string; bg: string }> = {
  take: { label: "לפתוח", color: "#4fb187", bg: "rgba(79,177,135,.12)" },
  caution: { label: "בזהירות", color: "#d6a854", bg: "rgba(214,168,84,.12)" },
  pass: { label: "לוותר", color: "#e06e60", bg: "rgba(224,110,96,.12)" },
};

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
  review,
}: {
  candidate: Candidate | null;
  points: PayoffPoint[];
  review: Review | null;
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

      {/* committee context: regime / IV rank / RSI */}
      {review?.context && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] font-mono text-slate-400 mb-3" dir="rtl">
          <span>משטר: <span className="text-slate-200">{review.context.regime}</span></span>
          <span>IV rank: <span className="text-slate-200">{review.context.iv_rank}</span></span>
          {review.context.rsi != null && (
            <span>RSI: <span className="text-slate-200">{review.context.rsi}</span></span>
          )}
        </div>
      )}

      {/* analyst verdict */}
      {review?.verdict && (
        <div
          className="rounded-lg p-3 mb-3 text-[13px] leading-relaxed"
          style={{ background: VERDICT[review.verdict].bg, border: `1px solid ${VERDICT[review.verdict].color}55` }}
          dir="rtl"
        >
          <span
            className="font-semibold px-2 py-0.5 rounded-full text-xs ml-2"
            style={{ background: VERDICT[review.verdict].color, color: "#0c111a" }}
          >
            {VERDICT[review.verdict].label}
          </span>
          <span className="text-slate-200">{review.rationale}</span>
          {review.engine === "langgraph" && (
            <span className="block mt-1.5 text-[10px] font-mono text-slate-500">
              ⚙ ועדת LangGraph{(review.revisions ?? 0) > 0 ? " · תוקן אחרי טיעון המבקר" : ""}
            </span>
          )}
        </div>
      )}

      {/* AI plain-language explanation — clear to a child */}
      <div className="rounded-lg bg-accent/10 border border-accent/30 p-3 mb-3 text-[13px] leading-relaxed" dir="rtl">
        {review?.explanation ? review.explanation : <span className="text-slate-500">טוען הסבר…</span>}
      </div>

      {/* critic's objection */}
      {review?.objection && (
        <div className="rounded-lg bg-bad/10 border border-bad/30 p-3 mb-4 text-[12px] leading-relaxed text-slate-300" dir="rtl">
          <span className="text-bad font-semibold ml-1">המבקר:</span> {review.objection}
        </div>
      )}

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
