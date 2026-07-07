import { useEffect, useState } from "react";
import type { CloseAdvice, Position } from "../types";
import { closeReasonLabel, strategyColor, strategyLabel } from "../lib";
import { colors } from "../theme";
import LegLadder from "./LegLadder";
import {
  IconAlertTriangle,
  IconArrowDownCircle,
  IconArrowUpCircle,
  IconCheckCircle,
  IconClock,
  IconRefresh,
  IconScale,
} from "./Icon";

const DECISION: Record<string, { label: string; cls: string; color: string }> = {
  hold: { label: "החזק", cls: "bg-good/15 text-good border-good/40", color: colors.good },
  close: { label: "שקול לסגור", cls: "bg-bad/15 text-bad border-bad/40", color: colors.bad },
  reduce: { label: "הקטן פוזיציה", cls: "bg-warn/15 text-warn border-warn/40", color: colors.warn },
};

const STANCE_LABEL: Record<string, string> = { hold: "החזק", close: "סגור", reduce: "הקטן" };

const ALERT_LABEL: Record<string, string> = {
  profit_target: "הגיע ליעד רווח — שקול לסגור",
  stop_loss: "הגיע לנקודת סטופ — סגור עכשיו",
  time_stop: "קרוב לפקיעה — זמן לסגור",
  expired: "פג תוקף",
};

function Pnl({ value }: { value: number | null | undefined }) {
  if (value == null) return <span className="text-ink-3">—</span>;
  return (
    <span className={`font-semibold tabular-nums ${value >= 0 ? "text-good" : "text-bad"}`}>
      {value >= 0 ? "+" : "-"}${Math.abs(value).toFixed(2)}
    </span>
  );
}

type Direction = "received" | "paid";

function CloseForm({
  onConfirm,
  onCancel,
}: {
  onConfirm: (exitCredit: number) => Promise<void>;
  onCancel: () => void;
}) {
  const [direction, setDirection] = useState<Direction>("received");
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);

  const parsed = parseFloat(amount);
  const valid = !Number.isNaN(parsed) && parsed >= 0;

  const submit = async () => {
    if (!valid) return;
    setBusy(true);
    const exitCredit = direction === "received" ? parsed : -parsed;
    await onConfirm(exitCredit);
  };

  return (
    <div className="mt-3 p-3 rounded-lg bg-panel2 border border-line" dir="rtl">
      <div className="text-xs text-ink-2 mb-2.5">בסגירת כל הפוזיציה:</div>

      <div className="flex items-center gap-3 flex-wrap">
        {/* received / paid segmented toggle */}
        <div className="inline-flex rounded-lg border border-line overflow-hidden" role="group" aria-label="כיוון התשלום">
          <button
            type="button"
            onClick={() => setDirection("received")}
            aria-pressed={direction === "received"}
            className={`inline-flex items-center gap-1.5 text-[13px] font-semibold px-3 py-1.5 transition ${
              direction === "received" ? "bg-good/25 text-good" : "text-ink-2 hover:bg-panel"
            }`}
          >
            <IconArrowDownCircle width={14} height={14} />
            קיבלתי
          </button>
          <button
            type="button"
            onClick={() => setDirection("paid")}
            aria-pressed={direction === "paid"}
            className={`inline-flex items-center gap-1.5 text-[13px] font-semibold px-3 py-1.5 border-r border-line transition ${
              direction === "paid" ? "bg-bad/25 text-bad" : "text-ink-2 hover:bg-panel"
            }`}
          >
            <IconArrowUpCircle width={14} height={14} />
            שילמתי
          </button>
        </div>

        {/* amount, always positive, with a clear $ prefix */}
        <div className="relative">
          <span className="absolute inset-y-0 right-3 flex items-center text-ink-2 font-mono text-sm pointer-events-none">
            $
          </span>
          <input
            autoFocus
            type="number"
            inputMode="decimal"
            step="0.01"
            min="0"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0.00"
            dir="ltr"
            aria-label="סכום בדולרים"
            className="w-28 text-right text-sm font-mono font-semibold tabular-nums pl-2 pr-7 py-1.5 rounded-lg bg-panel border border-line text-ink focus:border-accent outline-none"
          />
        </div>

        <button
          type="button"
          onClick={submit}
          disabled={busy || !valid}
          className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-good/20 text-good border border-good/40 disabled:opacity-40"
        >
          {busy ? "שומר…" : "אשר סגירה"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={busy}
          className="text-xs px-3 py-1.5 rounded-lg text-ink-2 border border-line hover:border-lineStrong"
        >
          ביטול
        </button>
      </div>

      {amount !== "" && valid && (
        <div className="text-[11px] font-mono text-ink-2 mt-2.5" aria-live="polite">
          יירשם כ:{" "}
          <span className={`font-semibold ${direction === "received" ? "text-good" : "text-bad"}`}>
            {direction === "received" ? "+" : "-"}${parsed.toFixed(2)}
          </span>
        </div>
      )}
    </div>
  );
}

function Stance({ title, s }: { title: string; s: CloseAdvice["analyst"] }) {
  const conf = s.confidence != null ? ` · ${Math.round(s.confidence * 100)}%` : "";
  return (
    <div>
      <div className="text-[11px] font-mono text-ink-3 mb-1">
        {title} — <span className="text-ink-2">{STANCE_LABEL[s.stance] ?? s.stance}</span>
        {conf}
      </div>
      <ul className="space-y-0.5">
        {s.reasons.map((r, i) => (
          <li key={i} className="text-[12px] text-ink-2 leading-snug flex gap-1.5">
            <span className="text-ink-3 shrink-0">•</span>
            <span>{r}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function CloseAdvicePanel({
  positionId,
  onAdvice,
}: {
  positionId: string;
  onAdvice: (id: string, force: boolean) => Promise<CloseAdvice>;
}) {
  const [advice, setAdvice] = useState<CloseAdvice | null>(null);
  const [busy, setBusy] = useState(true);
  const [open, setOpen] = useState(false);
  const [err, setErr] = useState(false);

  const load = async (force: boolean) => {
    setBusy(true);
    setErr(false);
    try {
      const a = await onAdvice(positionId, force);
      if (a.error) setErr(true);
      else setAdvice(a);
    } catch {
      setErr(true);
    } finally {
      setBusy(false);
    }
  };

  // Fetch once on mount (server serves it from the state-signature cache, so ordinary
  // refreshes are instant and don't re-spend on the LLM debate). "בדוק עכשיו" forces one.
  useEffect(() => {
    void load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [positionId]);

  const d = advice ? DECISION[advice.decision] ?? DECISION.hold : null;

  return (
    <div className="mt-3 pt-3 border-t border-line/70" dir="rtl">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="inline-flex items-center gap-1.5 text-[11px] font-mono text-ink-3">
          <IconScale width={13} height={13} />
          מתי לסגור?
        </span>

        {busy && !advice && <span className="text-[12px] text-ink-3">מתייעץ…</span>}

        {err && !advice && (
          <span className="text-[12px] text-ink-3">אין ייעוץ כרגע</span>
        )}

        {d && advice && (
          <>
            <span className={`inline-flex items-center gap-1.5 text-xs font-bold px-2.5 py-1 rounded-full border ${d.cls}`}>
              {advice.decision === "hold" ? (
                <IconCheckCircle width={13} height={13} />
              ) : (
                <IconAlertTriangle width={13} height={13} />
              )}
              {d.label}
              {advice.confidence != null && (
                <span className="opacity-70 font-mono">{Math.round(advice.confidence * 100)}%</span>
              )}
            </span>
            <span
              className="text-[10px] font-mono px-1.5 py-0.5 rounded text-ink-3 border border-line"
              title={
                advice.engine === "llm"
                  ? advice.orchestration === "langgraph"
                    ? "דיבייט של 3 מודלי שפה, מתוזמר ב-LangGraph"
                    : "דיבייט של 3 מודלי שפה (סדרתי)"
                  : "הערכה דטרמיניסטית (ללא מפתח מודל)"
              }
            >
              {advice.engine === "llm"
                ? advice.orchestration === "langgraph"
                  ? "LangGraph · 3 LLMs"
                  : "AI debate"
                : "rule-based"}
            </span>
            {!!advice.revisions && advice.revisions > 0 && (
              <span
                className="inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded text-accent border border-accent/40 bg-accent/10"
                title="המכריע לא היה בטוח — ההחלטה חזרה למנתח לסבב אחד"
              >
                <IconRefresh width={10} height={10} />
                revised
              </span>
            )}
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              className="text-[11px] font-mono text-ink-2 hover:text-ink underline decoration-dotted underline-offset-2 mr-auto"
            >
              {open ? "הסתר" : "פרטים"}
            </button>
            <button
              type="button"
              onClick={() => load(true)}
              disabled={busy}
              className="inline-flex items-center gap-1 text-[11px] font-mono text-ink-2 hover:text-ink disabled:opacity-40"
              title="הרץ דיבייט חדש עכשיו"
            >
              <IconRefresh width={12} height={12} />
              {busy ? "בודק…" : "בדוק עכשיו"}
            </button>
          </>
        )}
      </div>

      {open && advice && (
        <div className="mt-2.5 space-y-2.5">
          <p className="text-[13px] text-ink leading-relaxed">{advice.rationale}</p>
          <div className="grid sm:grid-cols-2 gap-3 p-2.5 rounded-lg bg-panel2/60 border border-line">
            <Stance title="מנתח" s={advice.analyst} />
            <Stance title="מבקר (איפכא מסתברא)" s={advice.critic} />
          </div>
          {!!advice.recalled && advice.recalled.length > 0 && (
            <div className="p-2.5 rounded-lg bg-panel2/60 border border-line">
              <div className="text-[11px] font-mono text-ink-3 mb-1.5">
                עסקאות דומות שנסגרו · זיכרון מקרים
              </div>
              <ul className="space-y-0.5">
                {advice.recalled.map((r, i) => (
                  <li key={i} className="text-[12px] leading-snug flex items-center gap-2">
                    <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${r.won ? "bg-good" : "bg-bad"}`} />
                    <span className="text-ink-2 flex-1">{r.summary}</span>
                    <span className="text-ink-3 font-mono text-[10px]">
                      {Math.round(r.similarity * 100)}% דמיון
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="text-[10px] font-mono text-ink-3 flex items-center gap-1.5">
            <IconClock width={11} height={11} />
            חושב {new Date(advice.computed_at).toLocaleTimeString("he-IL")} · המספרים חושבו
            דטרמיניסטית; המודלים רק שוקלים אותם. ייעוץ בלבד.
          </div>
        </div>
      )}
    </div>
  );
}

function PositionCard({
  p,
  onClose,
  onAdvice,
}: {
  p: Position;
  onClose: (id: string, exitCredit: number) => Promise<void>;
  onAdvice: (id: string, force: boolean) => Promise<CloseAdvice>;
}) {
  const [closing, setClosing] = useState(false);
  const isOpen = p.status === "open";
  const hasAlert = isOpen && !!p.alert;
  const rail = hasAlert ? colors.bad : strategyColor(p.strategy);

  return (
    <div
      className={`relative overflow-hidden rounded-xl border pl-5 pr-4 py-4 ${
        hasAlert ? "border-bad/45 bg-bad/5" : isOpen ? "border-line bg-panel/60" : "border-line/60 bg-panel/25"
      }`}
    >
      <span
        className={`absolute inset-y-0 left-0 w-1 ${hasAlert ? "animate-pulse-soft" : ""}`}
        style={{ background: rail }}
        aria-hidden="true"
      />
      <div className="flex items-center gap-2 mb-2.5">
        <span
          className={`w-2 h-2 rounded-full shrink-0 ${
            hasAlert ? "bg-bad animate-pulse-soft" : isOpen ? "bg-good" : "bg-ink3"
          }`}
          aria-hidden="true"
        />
        <span className="font-mono font-bold text-base tracking-tight">{p.underlying}</span>
        <span
          className="text-xs font-mono px-2 py-0.5 rounded-full"
          style={{ background: `${strategyColor(p.strategy)}22`, color: strategyColor(p.strategy) }}
        >
          {strategyLabel(p.strategy)}
        </span>
        <span className="text-[11px] font-mono text-ink-3 ml-auto">
          {isOpen
            ? `נפתח ${new Date(p.opened_at).toLocaleDateString("he-IL")}`
            : `נסגר ${p.closed_at ? new Date(p.closed_at).toLocaleDateString("he-IL") : ""}`}
        </span>
      </div>

      {isOpen && <LegLadder legs={p.legs} compact />}

      <div className="flex items-center justify-between mt-3 gap-3 flex-wrap">
        <div className="flex items-center gap-2.5 text-[13px] font-mono">
          <span className="text-ink-2">{isOpen ? "רווח לא ממומש:" : "רווח ממומש:"}</span>
          <Pnl value={isOpen ? p.unrealized_pnl : p.realized_pnl} />
          {!isOpen && p.close_reason && (
            <span className="text-ink-3 text-xs">· {closeReasonLabel(p.close_reason)}</span>
          )}
        </div>

        {isOpen && (
          <div className="flex items-center gap-2">
            {hasAlert ? (
              <span
                className="inline-flex items-center gap-1.5 text-xs font-bold px-2.5 py-1 rounded-full bg-bad/20 text-bad border border-bad/40"
                role="alert"
              >
                <IconAlertTriangle width={13} height={13} />
                {ALERT_LABEL[p.alert!] ?? p.alert}
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 text-xs font-mono px-2.5 py-1 rounded-full bg-good/10 text-good border border-good/30">
                <IconCheckCircle width={13} height={13} />
                תקין להחזיק
              </span>
            )}
            {!closing && (
              <button
                type="button"
                onClick={() => setClosing(true)}
                className="text-xs font-mono px-2.5 py-1 rounded-lg border border-line text-ink-2 hover:border-lineStrong hover:text-ink"
              >
                סגור פוזיציה
              </button>
            )}
          </div>
        )}
      </div>

      {isOpen && <CloseAdvicePanel positionId={p.id} onAdvice={onAdvice} />}

      {closing && (
        <CloseForm
          onConfirm={async (exitCredit) => {
            await onClose(p.id, exitCredit);
            setClosing(false);
          }}
          onCancel={() => setClosing(false)}
        />
      )}
    </div>
  );
}

export default function Positions({
  positions,
  onClose,
  onAdvice,
}: {
  positions: Position[];
  onClose: (id: string, exitCredit: number) => Promise<void>;
  onAdvice: (id: string, force: boolean) => Promise<CloseAdvice>;
}) {
  const open = positions.filter((p) => p.status === "open");
  const closed = positions.filter((p) => p.status === "closed");
  const alerts = open.filter((p) => p.alert);

  return (
    <div className="rounded-2xl border border-line bg-panel/50 p-4">
      <h2 className="text-2xs uppercase tracking-wider text-ink-3 font-mono mb-3">
        Positions
        {open.length > 0 && <span className="text-accent"> · {open.length} open</span>}
        {alerts.length > 0 && <span className="text-bad"> · {alerts.length} need attention</span>}
      </h2>
      {positions.length === 0 ? (
        <div className="text-ink-2 text-sm">No positions yet — open one from a suggestion above.</div>
      ) : (
        <div className="grid gap-3">
          {[...open, ...closed].map((p) => (
            <PositionCard key={p.id} p={p} onClose={onClose} onAdvice={onAdvice} />
          ))}
        </div>
      )}
    </div>
  );
}
