import { useEffect, useMemo, useState } from "react";
import type { User } from "firebase/auth";
import Suggestions from "./components/Suggestions";
import TradeDetails from "./components/TradeDetails";
import DacsGuide from "./components/DacsGuide";
import Positions from "./components/Positions";
import ReflectionPanel from "./components/Reflection";
import HowItWorks from "./components/HowItWorks";
import AmbientBackground from "./components/AmbientBackground";
import KpiStrip from "./components/KpiStrip";
import Sidebar, { type ViewId } from "./components/Sidebar";
import Topbar from "./components/Topbar";
import { authedFetch } from "./api";
import { currentIdToken } from "./auth";
import { strategyColor, strategyLabel } from "./lib";
import { useThemeColors } from "./theme-context";
import type { Candidate, CloseAdvice, PayoffPoint, Position, Reflection, Review } from "./types";

interface Group {
  strategy: string;
  trades: Candidate[];
}

const VIEW_META: Record<ViewId, { title: string; subtitle: string }> = {
  dashboard: { title: "לוח מסחר", subtitle: "Iron Condor · DACS 1.0 — top 5 each" },
  insights: { title: "תובנות אסטרטגיה", subtitle: "רפלקציה על העסקאות שנסגרו" },
  dacs: { title: "מדריך DACS 1.0", subtitle: "האסטרטגיה, שלב אחר שלב" },
  how: { title: "איך המערכת בנויה", subtitle: "ארכיטקטורה · שכבת ה-AI" },
};

export default function App({ user }: { user: User | null }) {
  const c = useThemeColors();
  const [view, setView] = useState<ViewId>("dashboard");
  const [menuOpen, setMenuOpen] = useState(false);
  const [groups, setGroups] = useState<Group[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [sel, setSel] = useState(0);
  const [payoff, setPayoff] = useState<PayoffPoint[]>([]);
  const [review, setReview] = useState<Review | null>(null);
  const [connected, setConnected] = useState(false);

  const refreshTop = () =>
    authedFetch("/api/top?n=5")
      .then((r) => r.json())
      .then((d) => setGroups(d.groups ?? []))
      .catch(() => {});

  const refreshPositions = () =>
    authedFetch("/api/positions")
      .then((r) => r.json())
      .then((d) => setPositions(d.positions ?? []))
      .catch(() => {});

  const openPosition = async (candidate: Candidate) => {
    const idx = candidate.u_idx ?? 0;
    const r = await authedFetch(`/api/positions/open/${candidate.underlying}/${idx}`, { method: "POST" });
    if (!r.ok) throw new Error("open failed");
    await refreshPositions();
  };

  const advisePosition = async (id: string, force: boolean): Promise<CloseAdvice> => {
    const r = await authedFetch(`/api/positions/${id}/close-advice`, { method: force ? "POST" : "GET" });
    if (!r.ok) throw new Error("advice failed");
    return r.json();
  };

  const loadReflection = async (): Promise<Reflection> =>
    authedFetch("/api/reflection").then((r) => r.json());

  const runReflection = async (): Promise<Reflection> => {
    const r = await authedFetch("/api/reflection", { method: "POST" });
    if (!r.ok) throw new Error("reflection failed");
    return r.json();
  };

  const closePosition = async (id: string, exitCredit: number) => {
    const r = await authedFetch(`/api/positions/${id}/close`, {
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
    const connect = async () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      const token = await currentIdToken();
      const q = token ? `?token=${encodeURIComponent(token)}` : "";
      ws = new WebSocket(`${proto}://${location.host}/ws${q}`);
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
          refreshPositions();
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
  // A STABLE identity for the selected trade. Every WebSocket scan replaces `groups` with a
  // fresh array, so `current` is a new object reference each tick even when it's the same
  // trade — keying the fetch effect on the object made the detail panel refetch and blank
  // (flicker) on every scan. Keying on this string means we only refetch when the *trade*
  // actually changes, not on each background refresh.
  const currentKey = current ? `${current.underlying}:${current.u_idx ?? 0}:${current.strategy}` : null;

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

  const meta = VIEW_META[view];

  return (
    <div className="flex min-h-dvh" dir="rtl">
      <AmbientBackground />
      <Sidebar view={view} onSelect={setView} open={menuOpen} onClose={() => setMenuOpen(false)} />

      <main className="flex-1 min-w-0 px-4 sm:px-6 pb-16 max-w-[1400px] mx-auto w-full">
        <Topbar
          title={meta.title}
          subtitle={meta.subtitle}
          connected={connected}
          user={user}
          onMenu={() => setMenuOpen(true)}
        />

        {view === "dashboard" && (
          <div className="animate-in space-y-6">
            <KpiStrip groups={groups} positions={positions} />

            <div className="grid lg:grid-cols-[1.15fr_1fr] gap-5">
              <div className="space-y-6">
                {groups.length === 0 && (
                  <div className="rounded-2xl border border-line bg-panel/60 p-8 text-center text-ink-2 text-sm shadow-card">
                    ממתין לסריקה הראשונה…
                  </div>
                )}
                {groups.map((g, gi) => {
                  const offset = groups.slice(0, gi).reduce((a, x) => a + x.trades.length, 0);
                  return (
                    <section key={g.strategy}>
                      <h2 className="text-xs font-semibold font-mono mb-2.5 flex items-center gap-2 tracking-wide">
                        <span
                          className="w-2 h-2 rounded-full"
                          style={{ background: strategyColor(g.strategy, c) }}
                          aria-hidden="true"
                        />
                        <span style={{ color: strategyColor(g.strategy, c) }}>{strategyLabel(g.strategy)}</span>
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
                className="rounded-2xl border border-line bg-panel/80 p-5 lg:sticky lg:top-24 self-start shadow-card"
                style={
                  current
                    ? { boxShadow: `0 0 0 1px ${strategyColor(current.strategy, c)}22, 0 20px 50px -24px ${strategyColor(current.strategy, c)}44` }
                    : undefined
                }
              >
                <TradeDetails candidate={current} points={payoff} review={review} />
              </section>
            </div>

            <Positions positions={positions} onClose={closePosition} onAdvice={advisePosition} />
          </div>
        )}

        {view === "insights" && (
          <div className="animate-in max-w-3xl">
            <ReflectionPanel loadLatest={loadReflection} runNew={runReflection} />
          </div>
        )}

        {view === "dacs" && (
          <div className="animate-in max-w-3xl">
            <DacsGuide />
          </div>
        )}

        {view === "how" && (
          <div className="animate-in max-w-3xl">
            <HowItWorks />
          </div>
        )}
      </main>
    </div>
  );
}
