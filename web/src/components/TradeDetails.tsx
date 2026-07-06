import type { Candidate, PayoffPoint, Review } from "../types";
import { colors } from "../theme";
import { frontExpiry, num, strategyColor, strategyLabel } from "../lib";
import LegLadder from "./LegLadder";
import PayoffChart from "./PayoffChart";
import { IconAlertTriangle, IconClock } from "./Icon";

const VERDICT: Record<string, { label: string; color: string; bg: string }> = {
  take: { label: "לפתוח", color: colors.good, bg: "rgba(52,199,149,.12)" },
  caution: { label: "בזהירות", color: colors.warn, bg: "rgba(232,162,61,.12)" },
  pass: { label: "לוותר", color: colors.bad, bg: "rgba(240,97,90,.12)" },
};

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-lg bg-panel2 border border-line px-3 py-2">
      <div className="text-2xs uppercase tracking-wider text-ink-3 font-mono">{label}</div>
      <div className="font-mono text-sm font-semibold tabular-nums mt-0.5" style={{ color: tone ?? colors.ink }}>
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
      <div className="h-full grid place-items-center text-ink-2 text-sm text-center px-6 py-10">
        Select a suggestion to see its legs, payoff and plan.
      </div>
    );
  }
  const c = candidate;
  const dacs = c.strategy === "dacs";
  const expiries = [...new Set(c.legs.map((l) => l.expiry).filter((e): e is string => !!e))];

  return (
    <div>
      <div className="flex items-center gap-3 mb-3">
        <span className="font-mono font-bold text-lg tracking-tight">{c.underlying}</span>
        <span
          className="text-xs font-mono px-2 py-0.5 rounded-full"
          style={{ background: `${strategyColor(c.strategy)}22`, color: strategyColor(c.strategy) }}
        >
          {strategyLabel(c.strategy)}
        </span>
        <span className="inline-flex items-center gap-1 text-xs text-ink-2 font-mono ml-auto">
          <IconClock width={13} height={13} />
          {frontExpiry(c)} · DTE {c.dte}
        </span>
      </div>

      {/* committee context: regime / IV rank / RSI */}
      {review?.context && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs font-mono text-ink-2 mb-3" dir="rtl">
          <span>
            משטר: <span className="text-ink">{review.context.regime}</span>
          </span>
          <span>
            IV rank: <span className="text-ink">{review.context.iv_rank}</span>
          </span>
          {review.context.rsi != null && (
            <span>
              RSI: <span className="text-ink">{review.context.rsi}</span>
            </span>
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
            className="inline-block font-semibold px-2 py-0.5 rounded-full text-xs ml-2 mb-1"
            style={{ background: VERDICT[review.verdict].color, color: colors.bg }}
          >
            {VERDICT[review.verdict].label}
          </span>
          <span className="text-ink">{review.rationale}</span>
          {review.engine === "langgraph" && (
            <span className="block mt-1.5 text-2xs font-mono text-ink-3">
              ועדת LangGraph{(review.revisions ?? 0) > 0 ? " · תוקן אחרי טיעון המבקר" : ""}
            </span>
          )}
        </div>
      )}

      {/* AI plain-language explanation — clear to a child */}
      <div className="rounded-lg bg-accent/10 border border-accent/30 p-3 mb-3 text-[13px] leading-relaxed" dir="rtl">
        {review?.explanation ? review.explanation : <span className="text-ink-2">טוען הסבר…</span>}
      </div>

      {/* critic's objection */}
      {review?.objection && (
        <div
          className="flex items-start gap-2 rounded-lg bg-bad/10 border border-bad/30 p-3 mb-4 text-xs leading-relaxed text-ink-2"
          dir="rtl"
        >
          <IconAlertTriangle width={14} height={14} className="text-bad shrink-0 mt-0.5" />
          <span>
            <span className="text-bad font-semibold">המבקר:</span> {review.objection}
          </span>
        </div>
      )}

      {/* legs — same visual language as the suggestion card, for instant recognition */}
      <LegLadder legs={c.legs} />
      {dacs && expiries.length > 1 && (
        <div className="text-2xs font-mono text-ink-3 mt-1.5 mb-3">
          שורט: {expiries[0]} · לונג: {expiries[1]}
        </div>
      )}

      {/* stats */}
      <div className="grid grid-cols-3 gap-2 my-4">
        {dacs ? (
          <>
            <Stat
              label="debit"
              value={String(num(c.meta, "long_debit") ?? Math.abs(c.credit).toFixed(2))}
              tone={colors.bad}
            />
            <Stat label="fast ratio" value={`${((num(c.meta, "fast_ratio") ?? 0) * 100).toFixed(0)}%`} tone={colors.good} />
            <Stat label="max loss" value={c.max_loss.toFixed(2)} tone={colors.bad} />
            <Stat label="stop (conserv.)" value={String(num(c.meta, "stop_conservative") ?? "—")} tone={colors.bad} />
            <Stat label="stop (aggr.)" value={String(num(c.meta, "stop_aggressive") ?? "—")} />
            <Stat label="short OTM" value={`${num(c.meta, "otm_pct") ?? "—"}%`} />
          </>
        ) : (
          <>
            <Stat label="credit" value={c.credit.toFixed(2)} tone={colors.good} />
            <Stat label="max profit" value={c.max_profit.toFixed(2)} tone={colors.good} />
            <Stat label="max loss" value={c.max_loss.toFixed(2)} tone={colors.bad} />
            <Stat label="POP" value={`${(c.pop * 100).toFixed(0)}%`} />
            <Stat label="breakevens" value={c.breakevens.map((b) => b.toFixed(0)).join(" / ")} />
            <Stat label="width" value={c.width.toFixed(0)} />
          </>
        )}
      </div>

      {dacs && (
        <div className="text-xs text-ink-2 mb-4 leading-relaxed border-r-2 border-accent/50 pr-3" dir="rtl">
          <b className="text-ink">סגירה אוטומטית:</b> קבע פקודת רווח מותנית כבר עכשיו (למשל קנית ב־30¢ ←
          מכירה ב־~1.1$). אם מתקרבים לסטופ — מורידים את הפקודה או יוצאים במרקט. נשתדל לסגור ~שבועיים לפני
          הפקיעה, לא לחכות לרגע האחרון.
        </div>
      )}

      <PayoffChart points={points} candidate={c} />
    </div>
  );
}
