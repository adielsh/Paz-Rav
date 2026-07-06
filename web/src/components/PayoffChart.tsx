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
import { colors } from "../theme";

const tickStyle = { fill: colors.ink2, fontSize: 11, fontFamily: "JetBrains Mono, monospace" };

export default function PayoffChart({
  points,
  candidate,
}: {
  points: PayoffPoint[];
  candidate: Candidate | null;
}) {
  if (!candidate || points.length === 0) {
    return (
      <div className="h-64 grid place-items-center text-ink-2 text-sm">
        Select a candidate to see its payoff at expiry.
      </div>
    );
  }
  return (
    <div>
      <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs font-mono text-ink-2 mb-2.5">
        <span>
          DTE <b className="text-ink font-semibold">{candidate.dte}</b>
        </span>
        <span>
          credit <b className="text-good font-semibold">{candidate.credit.toFixed(2)}</b>
        </span>
        <span>
          max loss <b className="text-bad font-semibold">{candidate.max_loss.toFixed(2)}</b>
        </span>
        <span>
          POP <b className="text-ink font-semibold">{(candidate.pop * 100).toFixed(1)}%</b>
        </span>
        <span>
          breakevens{" "}
          <b className="text-accent font-semibold">
            {candidate.breakevens.map((b) => b.toFixed(0)).join(" / ")}
          </b>
        </span>
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={points} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
            <defs>
              <linearGradient id="pnl" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={colors.good} stopOpacity={0.5} />
                <stop offset="100%" stopColor={colors.good} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke={colors.line} strokeOpacity={0.5} />
            <XAxis
              dataKey="price"
              tick={tickStyle}
              tickLine={false}
              axisLine={{ stroke: colors.line }}
            />
            <YAxis
              tick={tickStyle}
              tickLine={false}
              axisLine={false}
              width={48}
              tickFormatter={(v: number) => `$${v}`}
            />
            <ReferenceLine y={0} stroke={colors.ink3} strokeDasharray="3 3" />
            {candidate.breakevens.map((b) => (
              <ReferenceLine key={b} x={Math.round(b)} stroke={colors.accent} strokeDasharray="2 4" />
            ))}
            <Tooltip
              contentStyle={{
                background: colors.panel,
                border: `1px solid ${colors.line}`,
                borderRadius: 8,
                fontSize: 12,
                fontFamily: "JetBrains Mono, monospace",
              }}
              labelStyle={{ color: colors.ink }}
              formatter={(v: number) => [`$${v.toFixed(2)}`, "P&L"]}
              labelFormatter={(l) => `underlying $${l}`}
            />
            <Area type="monotone" dataKey="pnl" stroke={colors.good} strokeWidth={2} fill="url(#pnl)" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
