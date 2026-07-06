import { useState } from "react";
import type { Position } from "../types";
import { closeReasonLabel, strategyColor, strategyLabel } from "../lib";
import LegLadder from "./LegLadder";

const ALERT_LABEL: Record<string, string> = {
  profit_target: "הגיע ליעד רווח — שקול לסגור",
  stop_loss: "הגיע לנקודת סטופ — סגור עכשיו",
  time_stop: "קרוב לפקיעה — זמן לסגור",
  expired: "פג תוקף",
};

function Pnl({ value }: { value: number | null | undefined }) {
  if (value == null) return <span className="text-slate-500">—</span>;
  return (
    <span className={value >= 0 ? "text-good" : "text-bad"}>
      {value >= 0 ? "+" : ""}
      {value.toFixed(2)}
    </span>
  );
}

function CloseForm({
  onConfirm,
  onCancel,
}: {
  onConfirm: (exitCredit: number) => Promise<void>;
  onCancel: () => void;
}) {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    const n = parseFloat(value);
    if (Number.isNaN(n)) return;
    setBusy(true);
    await onConfirm(n);
  };

  return (
    <div className="flex items-center gap-2 mt-2 p-2 rounded-lg bg-white/5 border border-line" dir="rtl">
      <span className="text-[12px] text-slate-300 whitespace-nowrap">
        כמה קיבלת (או שילמת) בסגירת כל הפוזיציה?
      </span>
      <input
        autoFocus
        type="number"
        step="0.01"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="למשל 1.10 או -0.30"
        className="w-28 text-sm font-mono px-2 py-1 rounded bg-panel border border-line text-slate-100"
      />
      <button
        onClick={submit}
        disabled={busy || value === ""}
        className="text-[12px] font-semibold px-2.5 py-1 rounded bg-good/20 text-good border border-good/40 disabled:opacity-50"
      >
        {busy ? "שומר…" : "אשר סגירה"}
      </button>
      <button
        onClick={onCancel}
        disabled={busy}
        className="text-[12px] px-2.5 py-1 rounded text-slate-400 border border-line"
      >
        ביטול
      </button>
    </div>
  );
}

function PositionCard({
  p,
  onClose,
}: {
  p: Position;
  onClose: (id: string, exitCredit: number) => Promise<void>;
}) {
  const [closing, setClosing] = useState(false);
  const isOpen = p.status === "open";
  const hasAlert = isOpen && !!p.alert;

  return (
    <div
      className={`rounded-xl border p-4 ${
        hasAlert ? "border-bad/50 bg-bad/5" : isOpen ? "border-line bg-panel/50" : "border-line/50 bg-panel/20"
      }`}
    >
      <div className="flex items-center gap-2 mb-2">
        <span
          className={`w-2.5 h-2.5 rounded-full ${
            hasAlert ? "bg-bad animate-pulse" : isOpen ? "bg-good" : "bg-slate-500"
          }`}
        />
        <span className="font-mono font-bold text-base">{p.underlying}</span>
        <span
          className="text-xs font-mono px-2 py-0.5 rounded-full"
          style={{ background: `${strategyColor(p.strategy)}22`, color: strategyColor(p.strategy) }}
        >
          {strategyLabel(p.strategy)}
        </span>
        <span className="text-[11px] font-mono text-slate-500 ml-auto">
          {isOpen
            ? `נפתח ${new Date(p.opened_at).toLocaleDateString("he-IL")}`
            : `נסגר ${p.closed_at ? new Date(p.closed_at).toLocaleDateString("he-IL") : ""}`}
        </span>
      </div>

      {isOpen && <LegLadder legs={p.legs} compact />}

      <div className="flex items-center justify-between mt-3 gap-3 flex-wrap">
        <div className="flex items-center gap-3 text-[13px] font-mono">
          <span className="text-slate-500">
            {isOpen ? "רווח לא ממומש:" : "רווח ממומש:"}
          </span>
          <Pnl value={isOpen ? p.unrealized_pnl : p.realized_pnl} />
          {!isOpen && p.close_reason && (
            <span className="text-slate-400 text-[12px]">· {closeReasonLabel(p.close_reason)}</span>
          )}
        </div>

        {isOpen && (
          <div className="flex items-center gap-2">
            {hasAlert ? (
              <span className="text-[12px] font-bold px-2.5 py-1 rounded-full bg-bad/20 text-bad border border-bad/40">
                ⚠️ {ALERT_LABEL[p.alert!] ?? p.alert}
              </span>
            ) : (
              <span className="text-[12px] font-mono px-2.5 py-1 rounded-full bg-good/10 text-good border border-good/30">
                ✓ תקין להחזיק
              </span>
            )}
            {!closing && (
              <button
                onClick={() => setClosing(true)}
                className="text-[12px] font-mono px-2.5 py-1 rounded-lg border border-line text-slate-300 hover:border-slate-400"
              >
                סגור פוזיציה
              </button>
            )}
          </div>
        )}
      </div>

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
}: {
  positions: Position[];
  onClose: (id: string, exitCredit: number) => Promise<void>;
}) {
  const open = positions.filter((p) => p.status === "open");
  const closed = positions.filter((p) => p.status === "closed");
  const alerts = open.filter((p) => p.alert);

  return (
    <div className="rounded-xl border border-line bg-panel/40 p-4">
      <h2 className="text-[11px] uppercase tracking-wider text-slate-500 font-mono mb-3">
        Positions
        {open.length > 0 && <span className="text-accent"> · {open.length} open</span>}
        {alerts.length > 0 && <span className="text-bad"> · {alerts.length} need attention</span>}
      </h2>
      {positions.length === 0 ? (
        <div className="text-slate-500 text-sm">No positions yet — open one from a suggestion above.</div>
      ) : (
        <div className="grid gap-3">
          {[...open, ...closed].map((p) => (
            <PositionCard key={p.id} p={p} onClose={onClose} />
          ))}
        </div>
      )}
    </div>
  );
}
