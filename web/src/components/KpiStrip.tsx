import type { ReactNode } from "react";
import type { Candidate, Position } from "../types";
import { useThemeColors } from "../theme-context";
import { usdContractSigned } from "../format";
import { IconAlertTriangle } from "./Icon";

interface Group {
  strategy: string;
  trades: Candidate[];
}

function Tile({ label, value, tone, sub }: { label: string; value: string; tone?: string; sub?: ReactNode }) {
  const p = useThemeColors();
  return (
    <div className="relative rounded-2xl border border-line bg-panel/80 p-4 overflow-hidden shadow-card">
      <div
        className="absolute inset-x-0 top-0 h-0.5"
        style={{ background: `linear-gradient(90deg, transparent, ${tone ?? p.lineStrong}, transparent)` }}
      />
      <div className="text-2xs uppercase tracking-wider text-ink-3 font-mono">{label}</div>
      <div className="text-[26px] leading-tight font-bold font-mono tabular-nums mt-1" style={{ color: tone ?? p.ink }}>
        {value}
      </div>
      {sub && <div className="text-xs text-ink-2 mt-0.5">{sub}</div>}
    </div>
  );
}

export default function KpiStrip({ groups, positions }: { groups: Group[]; positions: Position[] }) {
  const p = useThemeColors();
  const trades = groups.flatMap((g) => g.trades);
  const actionable = trades.filter((t) => t.verdict === "take" || t.verdict === "caution").length;
  const open = positions.filter((x) => x.status === "open");
  const alerts = open.filter((x) => x.alert);
  const unrealized = open.reduce((sum, x) => sum + (x.unrealized_pnl ?? 0), 0);
  const closed = positions.filter((x) => x.status === "closed");
  const realized = closed.reduce((sum, x) => sum + (x.realized_pnl ?? 0), 0);

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      <Tile label="הצעות מוכנות" value={String(actionable)} sub="לפתוח / בזהירות" />
      <Tile
        label="פוזיציות פתוחות"
        value={String(open.length)}
        tone={open.length > 0 ? p.accent : undefined}
        sub={unrealized !== 0 ? `${usdContractSigned(unrealized)} לא ממומש` : undefined}
      />
      <Tile
        label="דורש תשומת לב"
        value={String(alerts.length)}
        tone={alerts.length > 0 ? p.bad : p.good}
        sub={
          alerts.length > 0 ? (
            <span className="inline-flex items-center gap-1">
              <IconAlertTriangle width={11} height={11} /> התראת סגירה פעילה
            </span>
          ) : undefined
        }
      />
      <Tile
        label="רווח ממומש (סגורות)"
        value={closed.length > 0 ? usdContractSigned(realized) : "—"}
        tone={closed.length > 0 ? (realized >= 0 ? p.good : p.bad) : undefined}
        sub={closed.length > 0 ? `${closed.length} נסגרו` : "טרם נסגרו עסקאות"}
      />
    </div>
  );
}
