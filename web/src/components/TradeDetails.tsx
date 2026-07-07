import type { Candidate, PayoffPoint, Review } from "../types";
import { useThemeColors } from "../theme-context";
import { frontExpiry, num, strategyColor, strategyLabel } from "../lib";
import { pct, usdContract, usdStrike } from "../format";
import LegLadder from "./LegLadder";
import PayoffChart from "./PayoffChart";
import { InfoButton } from "./Modal";
import { IconAlertTriangle, IconClock } from "./Icon";

const VERDICT_LABEL: Record<string, string> = { take: "לפתוח", caution: "בזהירות", pass: "לוותר" };

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  const p = useThemeColors();
  return (
    <div className="rounded-lg bg-panel2 border border-line px-3 py-2">
      <div className="text-2xs uppercase tracking-wider text-ink-3 font-mono">{label}</div>
      <div className="font-mono text-sm font-semibold tabular-nums mt-0.5" style={{ color: tone ?? p.ink }}>
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
  const p = useThemeColors();
  const verdictColor: Record<string, string> = { take: p.good, caution: p.warn, pass: p.bad };

  if (!candidate) {
    return (
      <div className="h-full grid place-items-center text-ink-2 text-sm text-center px-6 py-10">
        בחר הצעה כדי לראות את הרגליים, גרף הרווח והתוכנית.
      </div>
    );
  }
  const c = candidate;
  const dacs = c.strategy === "dacs";
  const rail = strategyColor(c.strategy, p);
  const expiries = [...new Set(c.legs.map((l) => l.expiry).filter((e): e is string => !!e))];

  return (
    <div>
      <div className="flex items-center gap-3 mb-3">
        <span className="font-mono font-bold text-lg tracking-tight text-ink">{c.underlying}</span>
        <span className="text-xs font-mono px-2 py-0.5 rounded-full" style={{ background: `${rail}22`, color: rail }}>
          {strategyLabel(c.strategy)}
        </span>
        <span className="inline-flex items-center gap-1 text-xs text-ink-2 font-mono ml-auto">
          <IconClock width={13} height={13} />
          {frontExpiry(c)} · DTE {c.dte}
        </span>
      </div>

      {review?.context && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs font-mono text-ink-2 mb-3" dir="rtl">
          <span>משטר: <span className="text-ink">{review.context.regime}</span></span>
          <span>IV rank: <span className="text-ink">{review.context.iv_rank}</span></span>
          {review.context.rsi != null && <span>RSI: <span className="text-ink">{review.context.rsi}</span></span>}
        </div>
      )}

      {review?.verdict && (
        <div
          className="rounded-lg p-3 mb-3 text-[13px] leading-relaxed"
          style={{ background: `${verdictColor[review.verdict]}18`, border: `1px solid ${verdictColor[review.verdict]}55` }}
          dir="rtl"
        >
          <span
            className="inline-block font-semibold px-2 py-0.5 rounded-full text-xs ml-2 mb-1 text-white"
            style={{ background: verdictColor[review.verdict] }}
          >
            {VERDICT_LABEL[review.verdict]}
          </span>
          <span className="text-ink">{review.rationale}</span>
          {review.engine === "langgraph" && (
            <span className="block mt-1.5 text-2xs font-mono text-ink-3">
              ועדת LangGraph{(review.revisions ?? 0) > 0 ? " · תוקן אחרי טיעון המבקר" : ""}
            </span>
          )}
        </div>
      )}

      <div className="rounded-lg bg-primary/10 border border-primary/30 p-3 mb-3 text-[13px] leading-relaxed text-ink" dir="rtl">
        {review?.explanation ? review.explanation : <span className="text-ink-2">טוען הסבר…</span>}
      </div>

      {review?.objection && (
        <div className="flex items-start gap-2 rounded-lg bg-bad/10 border border-bad/30 p-3 mb-4 text-xs leading-relaxed text-ink-2" dir="rtl">
          <IconAlertTriangle width={14} height={14} className="text-bad shrink-0 mt-0.5" />
          <span>
            <span className="text-bad font-semibold">המבקר:</span> {review.objection}
          </span>
        </div>
      )}

      <LegLadder legs={c.legs} />
      {dacs && expiries.length > 1 && (
        <div className="text-2xs font-mono text-ink-3 mt-1.5 mb-3">
          שורט: {expiries[0]} · לונג: {expiries[1]}
        </div>
      )}

      <div className="grid grid-cols-3 gap-2 my-4">
        {dacs ? (
          <>
            <Stat label="עלות (debit)" value={usdContract(num(c.meta, "long_debit") ?? Math.abs(c.credit))} tone={p.bad} />
            <Stat label="fast ratio" value={pct(num(c.meta, "fast_ratio") ?? 0)} tone={p.good} />
            <Stat label="הפסד מקס" value={usdContract(c.max_loss)} tone={p.bad} />
            <Stat label="סטופ (שמרני)" value={usdStrike(num(c.meta, "stop_conservative"))} tone={p.bad} />
            <Stat label="סטופ (אגרסיבי)" value={usdStrike(num(c.meta, "stop_aggressive"))} />
            <Stat label="short OTM" value={`${num(c.meta, "otm_pct") ?? "—"}%`} />
          </>
        ) : (
          <>
            <Stat label="קרדיט" value={usdContract(c.credit)} tone={p.good} />
            <Stat label="רווח מקס" value={usdContract(c.max_profit)} tone={p.good} />
            <Stat label="הפסד מקס" value={usdContract(c.max_loss)} tone={p.bad} />
            <Stat label="POP" value={pct(c.pop)} />
            <Stat label="נק' איזון" value={c.breakevens.map((b) => usdStrike(b)).join(" / ")} />
            <Stat label="רוחב כנף" value={usdStrike(c.width)} />
          </>
        )}
      </div>

      {dacs && (
        <div className="flex items-center gap-2 mb-4 text-xs text-ink-2">
          <span>תוכנית ניהול הפוזיציה</span>
          <InfoButton title="סגירה אוטומטית — DACS" label="הסבר ניהול">
            <p className="text-[13.5px] text-ink-2 leading-relaxed" dir="rtl">
              קבע <b className="text-ink">פקודת רווח מותנית</b> כבר עכשיו (למשל קנית ב־30¢ ← מכירה ב־~1.1$).
              אם מתקרבים לסטופ — מורידים את הפקודה או יוצאים במרקט. נשתדל לסגור ~שבועיים לפני הפקיעה,
              לא לחכות לרגע האחרון.
            </p>
          </InfoButton>
        </div>
      )}

      <PayoffChart points={points} candidate={c} />
    </div>
  );
}
