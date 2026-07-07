import { useEffect, useState } from "react";
import type { Reflection } from "../types";
import { IconRefresh, IconScale } from "./Icon";

/** Strategy insights — the reflection agent's look-back over the whole closed-trade
 * history. Loads the latest saved reflection on mount; "נתח עכשיו" runs a fresh one
 * (deterministic stats computed in Python; the agent only interprets them). Advisory only. */
export default function ReflectionPanel({
  loadLatest,
  runNew,
}: {
  loadLatest: () => Promise<Reflection>;
  runNew: () => Promise<Reflection>;
}) {
  const [r, setR] = useState<Reflection | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    loadLatest()
      .then((d) => setR(d))
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const run = async () => {
    setBusy(true);
    try {
      setR(await runNew());
    } catch {
      /* leave the previous reflection in place */
    } finally {
      setBusy(false);
    }
  };

  const hasContent = r && (r.summary || (r.recommendations?.length ?? 0) > 0);

  return (
    <div className="rounded-2xl border border-line bg-panel/50 p-4" dir="rtl">
      <div className="flex items-center justify-between gap-3 mb-3">
        <h2 className="text-2xs uppercase tracking-wider text-ink-3 font-mono flex items-center gap-2">
          <IconScale width={13} height={13} />
          Strategy insights · רפלקציה אסטרטגית
          {r?.engine === "llm" && (
            <span className="text-[10px] px-1.5 py-0.5 rounded text-accent border border-accent/40 bg-accent/10">
              AI
            </span>
          )}
        </h2>
        <button
          type="button"
          onClick={run}
          disabled={busy}
          className="inline-flex items-center gap-1.5 text-xs font-mono px-2.5 py-1 rounded-lg border border-line text-ink-2 hover:border-lineStrong hover:text-ink disabled:opacity-40"
        >
          <IconRefresh width={12} height={12} />
          {busy ? "מנתח…" : "נתח עכשיו"}
        </button>
      </div>

      {!hasContent && (
        <p className="text-ink-2 text-sm">
          {r && !r.enough_data && r.sample_size > 0
            ? `רק ${r.sample_size} עסקאות סגורות — אוסף עוד דאטה לפני ניתוח אמין.`
            : "אין עדיין רפלקציה — סגור כמה פוזיציות ואז לחץ “נתח עכשיו”."}
        </p>
      )}

      {hasContent && (
        <div className="space-y-3">
          <p className="text-[13.5px] text-ink leading-relaxed">{r!.summary}</p>
          {r!.recommendations?.length > 0 && (
            <div>
              <div className="text-[11px] font-mono text-ink-3 mb-1.5">המלצות (ייעוץ בלבד):</div>
              <ul className="space-y-1">
                {r!.recommendations.map((rec, i) => (
                  <li key={i} className="text-[13px] text-ink-2 leading-snug flex gap-2">
                    <span className="text-accent shrink-0">→</span>
                    <span>{rec}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="text-[10px] font-mono text-ink-3">
            מבוסס על {r!.sample_size} עסקאות סגורות · המספרים חושבו דטרמיניסטית; הסוכן רק מפרש.
          </div>
        </div>
      )}
    </div>
  );
}
