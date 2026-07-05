import {
  Area,
  ComposedChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Candidate, PayoffPoint } from "../types";

export default function PayoffChart({
  points,
  candidate,
}: {
  points: PayoffPoint[];
  candidate: Candidate | null;
}) {
  if (!candidate || points.length === 0) {
    return (
      <div className="h-64 grid place-items-center text-slate-500 text-sm">
        Select a candidate to see its payoff at expiry.
      </div>
    );
  }
  return (
    <div>
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-[11px] font-mono text-slate-400 mb-2">
        <span>DTE {candidate.dte}</span>
        <span>credit <span className="text-good">{candidate.credit.toFixed(2)}</span></span>
        <span>max loss <span className="text-bad">{candidate.max_loss.toFixed(2)}</span></span>
        <span>POP {(candidate.pop * 100).toFixed(1)}%</span>
        <span>breakevens {candidate.breakevens.map((b) => b.toFixed(0)).join(" / ")}</span>
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={points} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
            <defs>
              <linearGradient id="pnl" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#4fb187" stopOpacity={0.5} />
                <stop offset="100%" stopColor="#4fb187" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="price"
              tick={{ fill: "#8a94a1", fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: "#212c3c" }}
            />
            <YAxis
              tick={{ fill: "#8a94a1", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={44}
            />
            <ReferenceLine y={0} stroke="#4a5568" strokeDasharray="3 3" />
            {candidate.breakevens.map((b) => (
              <ReferenceLine key={b} x={Math.round(b)} stroke="#d6a854" strokeDasharray="2 4" />
            ))}
            <Tooltip
              contentStyle={{
                background: "#131a26",
                border: "1px solid #212c3c",
                borderRadius: 8,
                fontSize: 12,
              }}
              labelStyle={{ color: "#e6ebf2" }}
              formatter={(v: number) => [v.toFixed(2), "P&L"]}
              labelFormatter={(l) => `underlying ${l}`}
            />
            <Area
              type="monotone"
              dataKey="pnl"
              stroke="#4fb187"
              strokeWidth={2}
              fill="url(#pnl)"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
