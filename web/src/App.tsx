import { useEffect, useMemo, useState } from "react";
import Suggestions from "./components/Suggestions";
import TradeDetails from "./components/TradeDetails";
import DacsGuide from "./components/DacsGuide";
import type { Candidate, PayoffPoint } from "./types";

export default function App() {
  const [top, setTop] = useState<Candidate[]>([]);
  const [sel, setSel] = useState(0);
  const [payoff, setPayoff] = useState<PayoffPoint[]>([]);
  const [explanation, setExplanation] = useState("");
  const [connected, setConnected] = useState(false);

  const refreshTop = () =>
    fetch("/api/top?n=5")
      .then((r) => r.json())
      .then((d) => setTop(d.top ?? []))
      .catch(() => {});

  // Live WebSocket: any new scan refreshes the Top-5.
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

  const current = useMemo(() => top[sel] ?? null, [top, sel]);

  // Fetch payoff + AI explanation for the selected suggestion.
  useEffect(() => {
    if (!current) {
      setPayoff([]);
      setExplanation("");
      return;
    }
    const idx = current.u_idx ?? 0;
    fetch(`/api/payoff/${current.underlying}/${idx}`)
      .then((r) => r.json())
      .then((d) => setPayoff(d.points ?? []))
      .catch(() => setPayoff([]));
    setExplanation("");
    fetch(`/api/explain/${current.underlying}/${idx}`)
      .then((r) => r.json())
      .then((d) => setExplanation(d.text ?? ""))
      .catch(() => setExplanation(""));
  }, [current]);

  return (
    <div className="max-w-5xl mx-auto px-5 py-6">
      <header className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">
            Paz Rav <span className="text-slate-500 text-sm font-normal">· top 5 to open</span>
          </h1>
          <p className="text-[11px] text-slate-500 font-mono mt-0.5">
            Iron Condor · DACS 1.0 — every number computed
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
        <section>
          <h2 className="text-[11px] uppercase tracking-wider text-slate-500 font-mono mb-2">
            5 best positions to open
          </h2>
          <Suggestions trades={top} selected={sel} onSelect={setSel} />
        </section>

        <section className="rounded-xl border border-line bg-panel/40 p-4">
          <TradeDetails candidate={current} points={payoff} explanation={explanation} />
        </section>
      </div>

      <section className="mt-5">
        <DacsGuide />
      </section>
    </div>
  );
}
