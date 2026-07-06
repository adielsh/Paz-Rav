import { useEffect, useMemo, useState } from "react";
import Suggestions from "./components/Suggestions";
import TradeDetails from "./components/TradeDetails";
import DacsGuide from "./components/DacsGuide";
import { strategyColor, strategyLabel } from "./lib";
import type { Candidate, PayoffPoint, Review } from "./types";

interface Group {
  strategy: string;
  trades: Candidate[];
}

export default function App() {
  const [groups, setGroups] = useState<Group[]>([]);
  const [sel, setSel] = useState(0);
  const [payoff, setPayoff] = useState<PayoffPoint[]>([]);
  const [review, setReview] = useState<Review | null>(null);
  const [connected, setConnected] = useState(false);

  const refreshTop = () =>
    fetch("/api/top?n=5")
      .then((r) => r.json())
      .then((d) => setGroups(d.groups ?? []))
      .catch(() => {});

  useEffect(() => {
    let ws: WebSocket;
    let closed = false;
    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/ws`);
      ws.onopen = () => {
        setConnected(true);
        refreshTop();
      };
      ws.onclose = () => {
        setConnected(false);
        if (!closed) setTimeout(connect, 1500);
      };
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data);
        if (msg.type === "candidates" || msg.type === "snapshot") refreshTop();
      };
    };
    connect();
    return () => {
      closed = true;
      ws?.close();
    };
  }, []);

  const flat = useMemo(() => groups.flatMap((g) => g.trades), [groups]);
  const current = flat[sel] ?? null;

  useEffect(() => {
    if (!current) {
      setPayoff([]);
      setReview(null);
      return;
    }
    const idx = current.u_idx ?? 0;
    fetch(`/api/payoff/${current.underlying}/${idx}`)
      .then((r) => r.json())
      .then((d) => setPayoff(d.points ?? []))
      .catch(() => setPayoff([]));
    setReview(null);
    fetch(`/api/review/${current.underlying}/${idx}`)
      .then((r) => r.json())
      .then((d) => setReview(d))
      .catch(() => setReview(null));
  }, [current]);

  return (
    <div className="max-w-6xl mx-auto px-5 py-6">
      <header className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">
            Paz Rav <span className="text-slate-500 text-sm font-normal">· best positions to open</span>
          </h1>
          <p className="text-[11px] text-slate-500 font-mono mt-0.5">
            5 best per strategy — Iron Condor · DACS 1.0
          </p>
        </div>
        <span
          className={`text-[11px] font-mono px-2.5 py-1 rounded-full border ${
            connected ? "border-good/40 text-good bg-good/10" : "border-bad/40 text-bad bg-bad/10"
          }`}
        >
          {connected ? "● live" : "○ reconnecting"}
        </span>
      </header>

      <div className="grid lg:grid-cols-[1.1fr_1fr] gap-5">
        <div className="space-y-5">
          {groups.length === 0 && (
            <div className="text-slate-500 text-sm">Waiting for the first scan…</div>
          )}
          {groups.map((g, gi) => {
            const offset = groups.slice(0, gi).reduce((a, x) => a + x.trades.length, 0);
            return (
              <section key={g.strategy}>
                <h2
                  className="text-xs font-semibold font-mono mb-2 flex items-center gap-2"
                  style={{ color: strategyColor(g.strategy) }}
                >
                  <span className="w-2 h-2 rounded-full" style={{ background: strategyColor(g.strategy) }} />
                  {strategyLabel(g.strategy)} — top {g.trades.length}
                </h2>
                <Suggestions
                  trades={g.trades}
                  selected={sel - offset}
                  onSelect={(i) => setSel(offset + i)}
                />
              </section>
            );
          })}
        </div>

        <section className="rounded-xl border border-line bg-panel/40 p-4 lg:sticky lg:top-6 self-start">
          <TradeDetails candidate={current} points={payoff} review={review} />
        </section>
      </div>

      <section className="mt-5">
        <DacsGuide />
      </section>
    </div>
  );
}
