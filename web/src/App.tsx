import { useEffect, useMemo, useState } from "react";
import type { User } from "firebase/auth";
import DacsGuide from "./components/DacsGuide";
import Positions from "./components/Positions";
import ReflectionPanel from "./components/Reflection";
import HowItWorks from "./components/HowItWorks";
import AmbientBackground from "./components/AmbientBackground";
import KpiStrip from "./components/KpiStrip";
import Sidebar, { type ViewId } from "./components/Sidebar";
import StrategyPage from "./components/StrategyPage";
import Topbar from "./components/Topbar";
import { authedFetch } from "./api";
import { currentIdToken } from "./auth";
import { pct } from "./format";
import { strategyColor, strategyLabel } from "./lib";
import { useThemeColors } from "./theme-context";
import type { Candidate, CloseAdvice, Position, Reflection } from "./types";

interface Group {
  strategy: string;
  trades: Candidate[];
}

const VIEW_META: Record<ViewId, { title: string; subtitle: string }> = {
  dashboard: { title: "לוח מסחר", subtitle: "מבט-על · פוזיציות · התראות" },
  condor: { title: "Iron Condor", subtitle: "מכירת פרמיה בסיכון מוגדר — top 5" },
  dacs: { title: "DACS 1.0", subtitle: "קלנדר דיאגונלי אדפטיבי — top 5" },
  insights: { title: "תובנות אסטרטגיה", subtitle: "רפלקציה על העסקאות שנסגרו" },
  dacsGuide: { title: "מדריך DACS 1.0", subtitle: "האסטרטגיה, שלב אחר שלב" },
  how: { title: "איך המערכת בנויה", subtitle: "ארכיטקטורה · שכבת ה-AI" },
};

const EMPTY_NOTE: Record<string, string> = {
  iron_condor:
    "המערכת מחפשת קונדורים סביב דלתא 16–25 עם כנפיים שוות, נזילות סבירה וקרדיט חיובי. " +
    "כשאין הצעות — לרוב ה-chain דליל (למשל כשהשוק סגור) או שאף מבנה לא עומד בתנאים. " +
    "הסריקה רצה כל דקה, אז הצעות יופיעו כאן ברגע שיימצאו.",
  dacs:
    "DACS נפתח רק בתנאים קפדניים: IV נמוך (rank מתחת ל-50), RSI סביב 60, בלי דוח רווחים " +
    "בשבועיים הקרובים, שורט ~10% מעל המחיר בדלתא ≤ 0.20, ו-Fast Ratio של לפחות 12%. " +
    "רוב הזמן אין מועמד שעובר את כולם — וזה בכוונה: עדיף לוותר מלפתוח עסקה בינונית. " +
    "כשמופיע כאן מועמד, הוא כבר עבר את כל המסננים.",
};

function StrategySummaryCard({
  strategy,
  trades,
  onGo,
}: {
  strategy: string;
  trades: Candidate[];
  onGo: () => void;
}) {
  const c = useThemeColors();
  const color = strategyColor(strategy, c);
  const best = trades[0];
  return (
    <button
      type="button"
      onClick={onGo}
      className="relative overflow-hidden text-right rounded-2xl border border-line bg-panel/80 p-5 shadow-card hover:-translate-y-0.5 hover:border-lineStrong transition-all"
    >
      <span className="absolute inset-y-0 left-0 w-1" style={{ background: color }} aria-hidden="true" />
      <div className="flex items-center gap-2 mb-1.5">
        <span className="w-2 h-2 rounded-full" style={{ background: color }} aria-hidden="true" />
        <span className="font-bold text-[15px]" style={{ color }}>
          {strategyLabel(strategy)}
        </span>
        <span className="text-xs font-mono text-ink-3 mr-auto">{trades.length} הצעות</span>
      </div>
      {best ? (
        <p className="text-[13px] text-ink-2 font-mono">
          הטובה ביותר: <b className="text-ink">{best.underlying}</b>
          {strategy === "dacs"
            ? ` · Fast Ratio ${pct(typeof best.meta?.fast_ratio === "number" ? best.meta.fast_ratio : 0)}`
            : ` · POP ${pct(best.pop)}`}
        </p>
      ) : (
        <p className="text-[13px] text-ink-2">אין כרגע מועמדים — היכנס לעמוד לפרטים.</p>
      )}
      <span className="block mt-2 text-xs font-semibold" style={{ color }}>
        לעמוד המלא ←
      </span>
    </button>
  );
}

export default function App({ user }: { user: User | null }) {
  const [view, setView] = useState<ViewId>("dashboard");
  const [menuOpen, setMenuOpen] = useState(false);
  const [groups, setGroups] = useState<Group[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
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

  const condorTrades = useMemo(
    () => groups.find((g) => g.strategy === "iron_condor")?.trades ?? [],
    [groups],
  );
  const dacsTrades = useMemo(
    () => groups.find((g) => g.strategy === "dacs")?.trades ?? [],
    [groups],
  );

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
            <div className="grid sm:grid-cols-2 gap-4">
              <StrategySummaryCard strategy="iron_condor" trades={condorTrades} onGo={() => setView("condor")} />
              <StrategySummaryCard strategy="dacs" trades={dacsTrades} onGo={() => setView("dacs")} />
            </div>
            <Positions positions={positions} onClose={closePosition} onAdvice={advisePosition} />
          </div>
        )}

        {view === "condor" && (
          <div className="animate-in">
            <StrategyPage
              strategy="iron_condor"
              trades={condorTrades}
              onOpenPosition={openPosition}
              emptyNote={EMPTY_NOTE.iron_condor}
            />
          </div>
        )}

        {view === "dacs" && (
          <div className="animate-in">
            <StrategyPage
              strategy="dacs"
              trades={dacsTrades}
              onOpenPosition={openPosition}
              emptyNote={EMPTY_NOTE.dacs}
            />
          </div>
        )}

        {view === "insights" && (
          <div className="animate-in max-w-3xl">
            <ReflectionPanel loadLatest={loadReflection} runNew={runReflection} />
          </div>
        )}

        {view === "dacsGuide" && (
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
