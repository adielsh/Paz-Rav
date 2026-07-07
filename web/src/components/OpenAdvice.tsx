import { useEffect, useState } from "react";
import type { OpenAdvice } from "../types";
import { IconAlertTriangle, IconBrain, IconCheckCircle, IconClock, IconRefresh } from "./Icon";

const DECISION: Record<string, { label: string; cls: string }> = {
  open: { label: "פתח עכשיו", cls: "bg-good/15 text-good border-good/40" },
  wait: { label: "המתן / גודל קטן", cls: "bg-warn/15 text-warn border-warn/40" },
  skip: { label: "ותר על העסקה", cls: "bg-bad/15 text-bad border-bad/40" },
};
const STANCE_LABEL: Record<string, string> = { open: "פתח", wait: "המתן", skip: "ותר" };

function Stance({ title, s }: { title: string; s: OpenAdvice["analyst"] }) {
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

/** "Second opinion before opening" — an explicit button (LLM spend only on demand) that
 * runs the three-model open-timing debate for the selected candidate. Mirrors the
 * close-advice panel so both debates read the same across the app. Advisory only. */
export default function OpenAdvicePanel({
  tradeKey,
  onAdvice,
}: {
  /** stable identity of the selected candidate — clears stale advice when it changes */
  tradeKey: string;
  onAdvice: (force: boolean) => Promise<OpenAdvice>;
}) {
  const [advice, setAdvice] = useState<OpenAdvice | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(false);

  // a different candidate was selected — the previous debate no longer applies
  useEffect(() => {
    setAdvice(null);
    setErr(false);
  }, [tradeKey]);

  const load = async (force: boolean) => {
    setBusy(true);
    setErr(false);
    try {
      const a = await onAdvice(force);
      if (a.error) setErr(true);
      else setAdvice(a);
    } catch {
      setErr(true);
    } finally {
      setBusy(false);
    }
  };

  const d = advice ? DECISION[advice.decision] ?? DECISION.wait : null;

  return (
    <div className="mt-4 pt-3 border-t border-line/70" dir="rtl">
      {!advice && (
        <button
          type="button"
          onClick={() => load(false)}
          disabled={busy}
          className="inline-flex items-center gap-2 text-[13px] font-semibold px-3.5 py-2 rounded-xl border border-primary/40 text-primary bg-primary/5 hover:bg-primary/10 active:scale-[0.98] disabled:opacity-50"
        >
          <IconBrain width={16} height={16} />
          {busy ? "שלושה מודלים מתווכחים…" : "חוות דעת AI — האם לפתוח?"}
        </button>
      )}
      {err && !advice && !busy && (
        <div className="text-[12px] text-ink-3 mt-1.5">אין חוות דעת כרגע — נסה שוב.</div>
      )}

      {d && advice && (
        <div className="space-y-2.5">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`inline-flex items-center gap-1.5 text-xs font-bold px-2.5 py-1 rounded-full border ${d.cls}`}>
              {advice.decision === "open" ? (
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
              title={advice.engine === "llm" ? "דיבייט של 3 מודלי שפה" : "הערכה דטרמיניסטית (ללא מפתח מודל)"}
            >
              {advice.engine === "llm" ? "AI debate · 3 LLMs" : "rule-based"}
            </span>
            <button
              type="button"
              onClick={() => load(true)}
              disabled={busy}
              className="inline-flex items-center gap-1 text-[11px] font-mono text-ink-2 hover:text-ink disabled:opacity-40 mr-auto"
              title="הרץ דיבייט חדש עכשיו"
            >
              <IconRefresh width={12} height={12} />
              {busy ? "בודק…" : "בדוק שוב"}
            </button>
          </div>

          <p className="text-[13px] text-ink leading-relaxed">{advice.rationale}</p>
          <div className="grid sm:grid-cols-2 gap-3 p-2.5 rounded-lg bg-panel2/60 border border-line">
            <Stance title="מנתח" s={advice.analyst} />
            <Stance title="מבקר (איפכא מסתברא)" s={advice.critic} />
          </div>
          {!!advice.recalled && advice.recalled.length > 0 && (
            <div className="p-2.5 rounded-lg bg-panel2/60 border border-line">
              <div className="text-[11px] font-mono text-ink-3 mb-1.5">עסקאות דומות שנסגרו · זיכרון מקרים</div>
              <ul className="space-y-0.5">
                {advice.recalled.map((r, i) => (
                  <li key={i} className="text-[12px] leading-snug flex items-center gap-2">
                    <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${r.won ? "bg-good" : "bg-bad"}`} />
                    <span className="text-ink-2 flex-1">{r.summary}</span>
                    <span className="text-ink-3 font-mono text-[10px]">{Math.round(r.similarity * 100)}% דמיון</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="text-[10px] font-mono text-ink-3 flex items-center gap-1.5">
            <IconClock width={11} height={11} />
            חושב {new Date(advice.computed_at).toLocaleTimeString("he-IL")} · המספרים חושבו דטרמיניסטית;
            המודלים רק שוקלים אותם. ייעוץ בלבד.
          </div>
        </div>
      )}
    </div>
  );
}
