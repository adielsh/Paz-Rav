import { useEffect, useMemo, useRef, useState } from "react";
import MarketOverview from "./components/MarketOverview";
import CandidatesTable from "./components/CandidatesTable";
import PayoffChart from "./components/PayoffChart";
import type { Candidate, Feature, PayoffPoint } from "./types";

export default function App() {
  const [features, setFeatures] = useState<Record<string, Feature>>({});
  const [candidates, setCandidates] = useState<Record<string, Candidate[]>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [idx, setIdx] = useState(0);
  const [payoff, setPayoff] = useState<PayoffPoint[]>([]);
  const [connected, setConnected] = useState(false);
  const selectedRef = useRef<string | null>(null);
  selectedRef.current = selected;

  // Live WebSocket with auto-reconnect.
  useEffect(() => {
    let ws: WebSocket;
    let closed = false;
    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/ws`);
      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!closed) setTimeout(connect, 1500);
      };
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data);
        if (msg.type === "snapshot") {
          const fmap: Record<string, Feature> = {};
          for (const f of msg.features as Feature[]) fmap[f.underlying] = f;
          setFeatures(fmap);
          setCandidates(msg.candidates);
          if (!selectedRef.current && msg.features.length) setSelected(msg.features[0].underlying);
        } else if (msg.type === "feature") {
          const f = msg.data as Feature;
          setFeatures((prev) => ({ ...prev, [f.underlying]: f }));
        } else if (msg.type === "candidates") {
          setCandidates((prev) => ({ ...prev, [msg.data.underlying]: msg.data.candidates }));
        }
      };
    };
    connect();
    return () => {
      closed = true;
      ws?.close();
    };
  }, []);

  // Fetch the payoff for the selected candidate.
  useEffect(() => {
    if (!selected) return;
    setIdx(0);
  }, [selected]);

  useEffect(() => {
    if (!selected) return;
    fetch(`/api/payoff/${selected}/${idx}`)
      .then((r) => r.json())
      .then((d) => setPayoff(d.points ?? []))
      .catch(() => setPayoff([]));
  }, [selected, idx, candidates]);

  const currentCandidates = selected ? candidates[selected] ?? [] : [];
  const currentCandidate = useMemo(
    () => currentCandidates[idx] ?? null,
    [currentCandidates, idx],
  );

  return (
    <div className="max-w-6xl mx-auto px-5 py-6">
      <header className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Paz Rav <span className="text-accent">·</span>{" "}
            <span className="text-slate-400 text-base font-normal">live options engine</span>
          </h1>
          <p className="text-xs text-slate-500 font-mono mt-1">
            deterministic core · every number computed
          </p>
        </div>
        <span
          className={`text-[11px] font-mono px-2.5 py-1 rounded-full border ${
            connected
              ? "border-good/40 text-good bg-good/10"
              : "border-bad/40 text-bad bg-bad/10"
          }`}
        >
          {connected ? "● live" : "○ reconnecting"}
        </span>
      </header>

      <section className="mb-6">
        <h2 className="text-[11px] uppercase tracking-wider text-slate-500 font-mono mb-2">
          Market overview
        </h2>
        <MarketOverview features={features} selected={selected} onSelect={setSelected} />
      </section>

      <div className="grid lg:grid-cols-2 gap-5">
        <section className="rounded-xl border border-line bg-panel/60 p-4">
          <h2 className="text-[11px] uppercase tracking-wider text-slate-500 font-mono mb-3">
            Ranked candidates{selected ? ` · ${selected}` : ""}
          </h2>
          <CandidatesTable candidates={currentCandidates} selectedIdx={idx} onSelect={setIdx} />
        </section>

        <section className="rounded-xl border border-line bg-panel/60 p-4">
          <h2 className="text-[11px] uppercase tracking-wider text-slate-500 font-mono mb-3">
            Trade inspector · payoff at expiry
          </h2>
          <PayoffChart points={payoff} candidate={currentCandidate} />
        </section>
      </div>
    </div>
  );
}
