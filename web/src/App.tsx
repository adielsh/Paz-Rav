import { useEffect, useMemo, useState } from "react";
import Suggestions from "./components/Suggestions";
import TradeDetails from "./components/TradeDetails";
import DacsGuide from "./components/DacsGuide";
import Positions from "./components/Positions";
import AmbientBackground from "./components/AmbientBackground";
import KpiStrip from "./components/KpiStrip";
import { strategyColor, strategyLabel } from "./lib";
import type { Candidate, PayoffPoint, Position, Review } from "./types";

interface Group {
  strategy: string;
  trades: Candidate[];
}

function Logo() {
  // A one-off decorative gradient (lighter/darker variants of the brand gold) — not a
  // reusable semantic token, so it's not in theme.ts.
  return (
    <div className="relative shrink-0">
      <div className="absolute inset-0 rounded-xl bg-accent/40 blur-lg" aria-hidden="true" />
      <div
        className="relative w-10 h-10 rounded-xl grid place-items-center font-mono font-bold text-base shadow-elevated"
        style={{ background: "linear-gradient(155deg, #E8C179, #B4863B)", color: "#1A1206" }}
        aria-hidden="true"
      >
        P
      </div>
    </div>
  );
}

function ConnectionBadge({ connected }: { connected: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs font-mono font-medium px-2.5 py-1.5 rounded-full border ${
        connected ? "border-good/35 text-good bg-good/10" : "border-bad/35 text-bad bg-bad/10"
      }`}
      role="status"
      aria-live="polite"
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${connected ? "bg-good" : "bg-bad"} ${
          connected ? "" : "animate-pulse-soft"
        }`}
      />
      {connected ? "Live" : "Reconnecting…"}
    </span>
  );
}

export default function App() {
  const [groups, setGroups] = useState<Group[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [sel, setSel] = useState(0);
  const [payoff, setPayoff] = useState<PayoffPoint[]>([]);
  const [review, setReview] = useState<Review | null>(null);
  const [connected, setConnected] = useState(false);

  const refreshTop = () =>
    fetch("/api/top?n=5")
      .then((r) => r.json())
      .then((d) => setGroups(d.groups ?? []))
      .catch(() => {});

  const refreshPositions = () =>
    fetch("/api/positions")
      .then((r) => r.json())
      .then((d) => setPositions(d.positions ?? []))
      .catch(() => {});

  const openPosition = async (c: Candidate) => {
    const idx = c.u_idx ?? 0;
    const r = await fetch(`/api/positions/open/${c.underlying}/${idx}`, { method: "POST" });
    if (!r.ok) throw new Error("open failed");
    await refreshPositions();
  };

  const closePosition = async (id: string, exitCredit: number) => {
    const r = await fetch(`/api/positions/${id}/close`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ exit_credit: exitCredit }),
    });
    if (!r.ok) throw new Error("close failed");
    await refreshPositions();
  };

  useEffect(() => {
    let ws: WebSocket;
    let closed = false;
    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/ws`);
      ws.onopen = () => {
        setConnected(true);
        refreshTop();
        refreshPositions();
      };
      ws.onclose = () => {
        setConnected(false);
        if (!closed) setTimeout(connect, 1500);
      };
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data);
        if (msg.type === "candidates" || msg.type === "snapshot") {
          refreshTop();
          refreshPositions(); // a scan may have swept the Exit Manager too
        }
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
    <div className="relative max-w-7xl mx-auto px-4 sm:px-6 py-7">
      <AmbientBackground />
      <header className="flex items-center justify-between gap-4 mb-7">
        <div className="flex items-center gap-3.5">
          <Logo />
          <div>
            <h1 className="text-xl font-bold tracking-tight leading-none">
              Paz Rav
              <span className="text-ink-2 text-sm font-normal ml-2.5">best positions to open</span>
            </h1>
            <p className="text-2xs uppercase tracking-wider text-ink-3 font-mono mt-1.5">
              Iron Condor · DACS 1.0 — top 5 each
            </p>
          </div>
        </div>
        <ConnectionBadge connected={connected} />
      </header>

      <KpiStrip groups={groups} positions={positions} />

      <div className="grid lg:grid-cols-[1.15fr_1fr] gap-5">
        <div className="space-y-6">
          {groups.length === 0 && (
            <div className="rounded-2xl border border-line bg-panel/60 p-6 text-center text-ink-2 text-sm">
              Waiting for the first scan…
            </div>
          )}
          {groups.map((g, gi) => {
            const offset = groups.slice(0, gi).reduce((a, x) => a + x.trades.length, 0);
            return (
              <section key={g.strategy}>
                <h2 className="text-xs font-semibold font-mono mb-2.5 flex items-center gap-2 tracking-wide">
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ background: strategyColor(g.strategy) }}
                    aria-hidden="true"
                  />
                  <span style={{ color: strategyColor(g.strategy) }}>{strategyLabel(g.strategy)}</span>
                  <span className="text-ink-3 font-normal">— top {g.trades.length}</span>
                </h2>
                <Suggestions
                  trades={g.trades}
                  selected={sel - offset}
                  onSelect={(i) => setSel(offset + i)}
                  onOpenPosition={openPosition}
                />
              </section>
            );
          })}
        </div>

        <section
          className="rounded-2xl border border-line bg-panel/70 p-5 lg:sticky lg:top-6 self-start"
          style={
            current
              ? { boxShadow: `0 0 0 1px ${strategyColor(current.strategy)}22, 0 20px 50px -20px ${strategyColor(current.strategy)}33` }
              : undefined
          }
        >
          <TradeDetails candidate={current} points={payoff} review={review} />
        </section>
      </div>

      <section className="mt-6">
        <Positions positions={positions} onClose={closePosition} />
      </section>

      <section className="mt-6">
        <DacsGuide />
      </section>
    </div>
  );
}
