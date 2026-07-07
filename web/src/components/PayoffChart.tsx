import {
  Area,
  CartesianGrid,
  ComposedChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Candidate, PayoffPoint } from "../types";
import { useThemeColors } from "../theme-context";
import { pct, usd, usdStrike } from "../format";

export default function PayoffChart({ points, candidate }: { points: PayoffPoint[]; candidate: Candidate | null }) {
  const c = useThemeColors();
  const tickStyle = { fill: c.ink2, fontSize: 11, fontFamily: "JetBrains Mono, monospace" };

  if (!candidate || points.length === 0) {
    return (
      <div className="h-64 grid place-items-center text-ink-2 text-sm">
        בחר עסקה כדי לראות את גרף הרווח בפקיעה.
      </div>
    );
  }
  return (
    <div>
      <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs font-mono text-ink-2 mb-2.5">
        <span>DTE <b className="text-ink font-semibold">{candidate.dte}</b></span>
        <span>credit <b className="text-good font-semibold">{usd(candidate.credit)}</b></span>
        <span>max loss <b className="text-bad font-semibold">{usd(candidate.max_loss)}</b></span>
        <span>POP <b className="text-ink font-semibold">{pct(candidate.pop, 1)}</b></span>
        <span>
          breakevens{" "}
          <b className="text-accent font-semibold">
            {candidate.breakevens.map((b) => usdStrike(b)).join(" / ")}
          </b>
        </span>
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={points} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
            <defs>
              <linearGradient id="pnl" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={c.good} stopOpacity={0.5} />
                <stop offset="100%" stopColor={c.good} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke={c.line} strokeOpacity={0.6} />
            <XAxis dataKey="price" tick={tickStyle} tickLine={false} axisLine={{ stroke: c.line }} />
            <YAxis tick={tickStyle} tickLine={false} axisLine={false} width={52} tickFormatter={(v: number) => `$${v}`} />
            <ReferenceLine y={0} stroke={c.ink3} strokeDasharray="3 3" />
            {candidate.breakevens.map((b) => (
              <ReferenceLine key={b} x={Math.round(b)} stroke={c.accent} strokeDasharray="2 4" />
            ))}
            <Tooltip
              contentStyle={{
                background: c.panel,
                border: `1px solid ${c.line}`,
                borderRadius: 8,
                fontSize: 12,
                fontFamily: "JetBrains Mono, monospace",
                color: c.ink,
              }}
              labelStyle={{ color: c.ink }}
              itemStyle={{ color: c.ink }}
              formatter={(v: number) => [usd(v), "P&L"]}
              labelFormatter={(l) => `מחיר הנכס $${l}`}
            />
            <Area type="monotone" dataKey="pnl" stroke={c.good} strokeWidth={2} fill="url(#pnl)" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
