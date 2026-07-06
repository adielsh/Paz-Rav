import type { ReactNode } from "react";
import type { Candidate, Position } from "../types";
import { colors } from "../theme";
import { IconAlertTriangle } from "./Icon";

interface Group {
  strategy: string;
  trades: Candidate[];
}

function Tile({
  label,
  value,
  tone,
  sub,
}: {
  label: string;
  value: string;
  tone?: string;
  sub?: ReactNode;
}) {
  return (
    <div className="relative rounded-2xl border border-line bg-panel/70 p-4 overflow-hidden">
      <div
        className="absolute inset-x-0 top-0 h-px"
        style={{ background: `linear-gradient(90deg, transparent, ${tone ?? colors.lineStrong}88, transparent)` }}
      />
      <div className="text-2xs uppercase tracking-wider text-ink-3 font-mono">{label}</div>
      <div
        className="text-[26px] leading-tight font-bold font-mono tabular-nums mt-1"
        style={{ color: tone ?? colors.ink }}
      >
        {value}
      </div>
      {sub && <div className="text-xs text-ink-2 mt-0.5">{sub}</div>}
    </div>
  );
}

export default function KpiStrip({ groups, positions }: { groups: Group[]; positions: Position[] }) {
  const trades = groups.flatMap((g) => g.trades);
  const actionable = trades.filter((t) => t.verdict === "take" || t.verdict === "caution").length;
  const open = positions.filter((p) => p.status === "open");
  const alerts = open.filter((p) => p.alert);
  const unrealized = open.reduce((sum, p) => sum + (p.unrealized_pnl ?? 0), 0);
  const closed = positions.filter((p) => p.status === "closed");
  const realized = closed.reduce((sum, p) => sum + (p.realized_pnl ?? 0), 0);

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
      <Tile label="Signals ready" value={String(actionable)} sub="take / caution" />
      <Tile
        label="Open positions"
        value={String(open.length)}
        tone={open.length > 0 ? colors.accent : undefined}
        sub={unrealized !== 0 ? `${unrealized >= 0 ? "+" : "-"}$${Math.abs(unrealized).toFixed(2)} unrealized` : undefined}
      />
      <Tile
        label="Need attention"
        value={String(alerts.length)}
        tone={alerts.length > 0 ? colors.bad : colors.good}
        sub={
          alerts.length > 0 ? (
            <span className="inline-flex items-center gap-1">
              <IconAlertTriangle width={11} height={11} /> exit alert active
            </span>
          ) : undefined
        }
      />
      <Tile
        label="Realized (closed)"
        value={closed.length > 0 ? `${realized >= 0 ? "+" : "-"}$${Math.abs(realized).toFixed(2)}` : "—"}
        tone={closed.length > 0 ? (realized >= 0 ? colors.good : colors.bad) : undefined}
        sub={closed.length > 0 ? `${closed.length} closed` : "no trades closed yet"}
      />
    </div>
  );
}
