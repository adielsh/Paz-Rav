import { useEffect, useState } from "react";
import type { Candidate, OpenAdvice, PayoffPoint, Review } from "../types";
import { authedFetch } from "../api";
import { strategyColor, strategyLabel } from "../lib";
import { useThemeColors } from "../theme-context";
import Suggestions from "./Suggestions";
import TradeDetails from "./TradeDetails";
import OpenAdvicePanel from "./OpenAdvice";

/** One strategy's page: its ranked suggestions, the detail panel for the selected one, and
 * the on-demand "should I open?" AI debate. Each strategy lives on its own page (sidebar
 * navigation) so the two are never visually mixed. */
export default function StrategyPage({
  strategy,
  trades,
  onOpenPosition,
  emptyNote,
}: {
  strategy: string;
  trades: Candidate[];
  onOpenPosition: (c: Candidate) => Promise<void>;
  emptyNote: string;
}) {
  const c = useThemeColors();
  const [sel, setSel] = useState(0);
  const [payoff, setPayoff] = useState<PayoffPoint[]>([]);
  const [review, setReview] = useState<Review | null>(null);

  const current = trades[Math.min(sel, Math.max(trades.length - 1, 0))] ?? null;
  // stable identity — refetch details only when the actual trade changes, not every scan
  const currentKey = current ? `${current.underlying}:${current.u_idx ?? 0}:${strategy}` : null;

  useEffect(() => {
    if (!current) {
      setPayoff([]);
      setReview(null);
      return;
    }
    const idx = current.u_idx ?? 0;
    authedFetch(`/api/payoff/${current.underlying}/${idx}`)
      .then((r) => r.json())
      .then((d) => setPayoff(d.points ?? []))
      .catch(() => setPayoff([]));
    setReview(null);
    authedFetch(`/api/review/${current.underlying}/${idx}`)
      .then((r) => r.json())
      .then((d) => setReview(d))
      .catch(() => setReview(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentKey]);

  const openAdvice = async (force: boolean): Promise<OpenAdvice> => {
    if (!current) throw new Error("no candidate selected");
    const idx = current.u_idx ?? 0;
    const r = await authedFetch(`/api/open-advice/${current.underlying}/${idx}`, {
      method: force ? "POST" : "GET",
    });
    if (!r.ok) throw new Error("open advice failed");
    return r.json();
  };

  if (trades.length === 0) {
    return (
      <div className="rounded-2xl border border-line bg-panel/70 p-8 shadow-card max-w-2xl" dir="rtl">
        <h2 className="font-bold text-ink mb-2" style={{ color: strategyColor(strategy, c) }}>
          אין כרגע מועמדים ל-{strategyLabel(strategy)}
        </h2>
        <p className="text-[14px] text-ink-2 leading-relaxed">{emptyNote}</p>
      </div>
    );
  }

  return (
    <div className="grid lg:grid-cols-[1.15fr_1fr] gap-5">
      <div>
        <Suggestions
          trades={trades}
          selected={sel}
          onSelect={setSel}
          onOpenPosition={onOpenPosition}
        />
      </div>

      <section
        className="rounded-2xl border border-line bg-panel/80 p-5 lg:sticky lg:top-24 self-start shadow-card"
        style={
          current
            ? { boxShadow: `0 0 0 1px ${strategyColor(strategy, c)}22, 0 20px 50px -24px ${strategyColor(strategy, c)}44` }
            : undefined
        }
      >
        <TradeDetails candidate={current} points={payoff} review={review} />
        {current && currentKey && <OpenAdvicePanel tradeKey={currentKey} onAdvice={openAdvice} />}
      </section>
    </div>
  );
}
