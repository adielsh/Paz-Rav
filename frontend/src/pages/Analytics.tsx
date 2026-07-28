import { useMemo } from "react";
import {
  ResponsiveContainer, AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine,
} from "recharts";
import { useTradesQuery, useGateDecisionsQuery } from "../store/api";
import { Tile, PnLTile, Panel, Empty } from "../components/ui";
import { useT } from "../i18n/useT";
import { money, num } from "../lib/format";
import { useChartTheme, CHART_TIP } from "../lib/chartTheme";
import type { Trade } from "../store/types";

function Chart({ title, children }: { title: string; children: React.ReactElement }) {
  return (
    <Panel title={title}>
      <div className="chartbox ltr">
        <ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer>
      </div>
    </Panel>
  );
}

export default function Analytics() {
  const { t } = useT();
  const ct = useChartTheme();
  const C = ct; const tip = CHART_TIP;
  const ax = { stroke: ct.axis, fontSize: 12, tickLine: false } as const;
  const { data: trades } = useTradesQuery(500, { pollingInterval: 30000 });
  const { data: gates } = useGateDecisionsQuery(500, { pollingInterval: 30000 });

  const a = useMemo(() => compute(trades ?? []), [trades]);
  const gateReasons = useMemo(() => {
    const m = new Map<string, number>();
    (gates ?? []).filter((g) => !g.accepted).forEach((g) =>
      m.set(g.reason, (m.get(g.reason) ?? 0) + 1));
    return [...m.entries()].map(([reason, count]) => ({ reason: shorten(reason), count }))
      .sort((x, y) => y.count - x.count);
  }, [gates]);

  if (!trades) return <Empty text={t("loading")} />;
  if (a.closed === 0) return <Empty text={t("no_closed")} />;

  const pf = a.grossLoss > 0 ? a.grossWin / a.grossLoss : Infinity;

  return (
    <>
      {/* KPI grid */}
      <div className="tiles">
        <Tile k={t("a_win_rate")} cls="kpi" tone={a.winRate >= 0.5 ? "pos" : "neg"}
          hint={`${a.wins} W / ${a.losses} L`}>{num(a.winRate * 100, 1)}%</Tile>
        <Tile k={t("a_profit_factor")} cls="kpi" tone={pf >= 1 ? "pos" : "neg"}>
          {pf === Infinity ? "∞" : num(pf, 2)}</Tile>
        <PnLTile k={t("a_expectancy")} value={a.expectancy} />
        <PnLTile k={t("a_max_dd")} value={-a.maxDD} />
        <PnLTile k={t("a_total_pnl")} value={a.total} />
        <Tile k={t("a_total_trades")} cls="kpi" tone="accent">{a.closed}</Tile>
      </div>
      <div className="tiles">
        <PnLTile k={t("a_avg_win")} value={a.avgWin} small />
        <PnLTile k={t("a_avg_loss")} value={a.avgLoss} small />
        <PnLTile k={t("a_best")} value={a.best} small />
        <PnLTile k={t("a_worst")} value={a.worst} small />
        <Tile k={t("a_avg_credit")} cls="kpi small" tone="flat">{num(a.avgCredit, 2)}</Tile>
        <Tile k={t("a_avg_dte")} cls="kpi small" tone="flat">{num(a.avgDte, 0)}</Tile>
      </div>

      <div className="chartgrid">
        <Chart title={t("a_equity")}>
          <AreaChart data={a.equity} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
            <defs><linearGradient id="eq" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={C.blue} stopOpacity={0.5} />
              <stop offset="100%" stopColor={C.blue} stopOpacity={0} /></linearGradient></defs>
            <CartesianGrid stroke={C.grid} vertical={false} />
            <XAxis dataKey="i" {...ax} /><YAxis {...ax} tickFormatter={(v) => `$${num(v, 0)}`} />
            <Tooltip contentStyle={tip} formatter={(v: number) => money(v)} />
            <Area type="monotone" dataKey="equity" stroke={C.blue} strokeWidth={2} fill="url(#eq)" isAnimationActive={false} />
          </AreaChart>
        </Chart>

        <Chart title={t("a_drawdown")}>
          <AreaChart data={a.equity} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
            <defs><linearGradient id="dd" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={C.red} stopOpacity={0.05} />
              <stop offset="100%" stopColor={C.red} stopOpacity={0.5} /></linearGradient></defs>
            <CartesianGrid stroke={C.grid} vertical={false} />
            <XAxis dataKey="i" {...ax} /><YAxis {...ax} tickFormatter={(v) => `$${num(v, 0)}`} />
            <Tooltip contentStyle={tip} formatter={(v: number) => money(v)} />
            <Area type="monotone" dataKey="dd" stroke={C.red} strokeWidth={1.5} fill="url(#dd)" isAnimationActive={false} />
          </AreaChart>
        </Chart>

        <Chart title={t("a_winloss")}>
          <PieChart>
            <Pie data={[{ name: t("a_wins"), value: a.wins }, { name: t("a_losses"), value: a.losses }]}
              dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2} isAnimationActive={false}>
              <Cell fill={C.green} /><Cell fill={C.red} />
            </Pie>
            <Tooltip contentStyle={tip} />
          </PieChart>
        </Chart>

        <Chart title={t("a_outcomes")}>
          <PieChart>
            <Pie data={a.outcomes} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2} isAnimationActive={false}>
              {a.outcomes.map((o, i) => <Cell key={i} fill={[C.green, C.blue, C.red][i]} />)}
            </Pie>
            <Tooltip contentStyle={tip} />
          </PieChart>
        </Chart>

        <Chart title={t("a_monthly")}>
          <BarChart data={a.monthly} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
            <CartesianGrid stroke={C.grid} vertical={false} />
            <XAxis dataKey="m" {...ax} /><YAxis {...ax} tickFormatter={(v) => `$${num(v, 0)}`} />
            <Tooltip contentStyle={tip} formatter={(v: number) => money(v)} />
            <ReferenceLine y={0} stroke={C.muted} />
            <Bar dataKey="pnl" radius={[3, 3, 0, 0]} isAnimationActive={false}>
              {a.monthly.map((d, i) => <Cell key={i} fill={d.pnl >= 0 ? C.green : C.red} />)}
            </Bar>
          </BarChart>
        </Chart>

        <Chart title={t("a_pnl_dist")}>
          <BarChart data={a.pnlHist} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
            <CartesianGrid stroke={C.grid} vertical={false} />
            <XAxis dataKey="bucket" {...ax} /><YAxis {...ax} allowDecimals={false} />
            <Tooltip contentStyle={tip} />
            <Bar dataKey="count" radius={[3, 3, 0, 0]} isAnimationActive={false}>
              {a.pnlHist.map((d, i) => <Cell key={i} fill={d.mid >= 0 ? C.green : C.red} />)}
            </Bar>
          </BarChart>
        </Chart>

        <Chart title={t("a_by_vix")}>
          <BarChart data={a.byVix} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
            <CartesianGrid stroke={C.grid} vertical={false} />
            <XAxis dataKey="label" {...ax} /><YAxis {...ax} />
            <Tooltip contentStyle={tip} />
            <Bar dataKey="trades" name={t("a_trades")} fill={C.blue} radius={[3, 3, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </Chart>

        <Chart title={t("a_credit_dist")}>
          <BarChart data={a.creditHist} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
            <CartesianGrid stroke={C.grid} vertical={false} />
            <XAxis dataKey="bucket" {...ax} /><YAxis {...ax} allowDecimals={false} />
            <Tooltip contentStyle={tip} />
            <Bar dataKey="count" fill={C.violet} radius={[3, 3, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </Chart>

        <Chart title={t("a_dte_dist")}>
          <BarChart data={a.dteHist} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
            <CartesianGrid stroke={C.grid} vertical={false} />
            <XAxis dataKey="bucket" {...ax} /><YAxis {...ax} allowDecimals={false} />
            <Tooltip contentStyle={tip} />
            <Bar dataKey="count" fill={C.amber} radius={[3, 3, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </Chart>

        <Chart title={t("a_gate_reasons")}>
          <BarChart data={gateReasons} layout="vertical" margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
            <CartesianGrid stroke={C.grid} horizontal={false} />
            <XAxis type="number" {...ax} allowDecimals={false} />
            <YAxis type="category" dataKey="reason" {...ax} width={130} />
            <Tooltip contentStyle={tip} />
            <Bar dataKey="count" fill={C.red} radius={[0, 3, 3, 0]} isAnimationActive={false} />
          </BarChart>
        </Chart>
      </div>

      <div className="note">{t("a_note")}</div>
    </>
  );
}

// ---- pure analytics ----
function compute(trades: Trade[]) {
  const closed = trades.filter((t) => t.realized != null)
    .sort((x, y) => (x.closed_at ?? "").localeCompare(y.closed_at ?? ""));
  const R = closed.map((t) => t.realized as number);
  const wins = R.filter((r) => r > 0), losses = R.filter((r) => r <= 0);
  const grossWin = wins.reduce((s, r) => s + r, 0);
  const grossLoss = Math.abs(losses.reduce((s, r) => s + r, 0));
  const total = grossWin - grossLoss;

  let cum = 0, peak = 0, maxDD = 0;
  const equity = closed.map((t, i) => {
    cum += t.realized as number; peak = Math.max(peak, cum);
    const dd = cum - peak; maxDD = Math.max(maxDD, peak - cum);
    return { i: i + 1, equity: +cum.toFixed(2), dd: +dd.toFixed(2) };
  });

  const monthlyMap = new Map<string, number>();
  closed.forEach((t) => {
    const m = (t.closed_at ?? "").slice(0, 7);
    monthlyMap.set(m, (monthlyMap.get(m) ?? 0) + (t.realized as number));
  });
  const monthly = [...monthlyMap.entries()].sort().map(([m, pnl]) =>
    ({ m: m.slice(2), pnl: +pnl.toFixed(2) }));

  const pnlHist = histogram(R, [-400, -200, -100, -50, 0, 50, 100, 150],
    (lo, hi) => `${lo}…${hi}`).map((b) => ({ ...b, mid: (b.lo + b.hi) / 2 }));
  const creditHist = histogram(closed.map((t) => t.entry_credit),
    [1.2, 1.3, 1.4, 1.5, 1.6, 1.7], (lo, hi) => `${lo.toFixed(2)}`);
  const dteHist = histogram(closed.map((t) => t.dte),
    [35, 38, 40, 42, 44, 46], (lo) => `${lo}`);

  const byVix = [
    { label: "<14", trades: closed.filter((t) => t.vix_avg < 14).length },
    { label: "14–22", trades: closed.filter((t) => t.vix_avg >= 14 && t.vix_avg <= 22).length },
    { label: ">22", trades: closed.filter((t) => t.vix_avg > 22).length },
  ];
  const cnt = (s: string) => trades.filter((t) => t.status === s).length;
  const outcomes = [
    { name: "closed", value: cnt("closed") },
    { name: "expired", value: cnt("expired") },
    { name: "stopped", value: cnt("stopped") },
  ].filter((o) => o.value > 0);

  return {
    closed: closed.length, wins: wins.length, losses: losses.length,
    winRate: closed.length ? wins.length / closed.length : 0,
    grossWin, grossLoss, total,
    avgWin: wins.length ? grossWin / wins.length : 0,
    avgLoss: losses.length ? -grossLoss / losses.length : 0,
    expectancy: closed.length ? total / closed.length : 0,
    best: R.length ? Math.max(...R) : 0, worst: R.length ? Math.min(...R) : 0,
    avgCredit: avg(closed.map((t) => t.entry_credit)), avgDte: avg(closed.map((t) => t.dte)),
    maxDD, equity, monthly, pnlHist, creditHist, dteHist, byVix, outcomes,
  };
}

function histogram(vals: number[], edges: number[], label: (lo: number, hi: number) => string) {
  const out = [];
  for (let i = 0; i < edges.length - 1; i++) {
    const lo = edges[i], hi = edges[i + 1];
    out.push({ bucket: label(lo, hi), lo, hi, count: vals.filter((v) => v >= lo && v < hi).length });
  }
  return out;
}
const avg = (xs: number[]) => (xs.length ? xs.reduce((s, x) => s + x, 0) / xs.length : 0);
const shorten = (r: string) => r.length > 26 ? r.slice(0, 24) + "…" : r;
