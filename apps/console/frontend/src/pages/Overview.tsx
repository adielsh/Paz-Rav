import {
  usePositionsQuery, usePnlQuery, usePnlSeriesQuery, useGateDecisionsQuery, useIbAccountQuery,
} from "../store/api";
import { Panel, Empty } from "../components/ui";
import { Cluster, type MetricDef } from "../components/Metrics";
import { useT } from "../i18n/useT";
import { money, num, expiry } from "../lib/format";
import { useChartTheme, CHART_TIP } from "../lib/chartTheme";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";

/** The three most common rejection reasons, for the gate-rejects breakdown. */
function topReasons(gates: { accepted: boolean; reason: string }[]) {
  const m = new Map<string, number>();
  gates.filter((g) => !g.accepted).forEach((g) => m.set(g.reason, (m.get(g.reason) ?? 0) + 1));
  return [...m.entries()].sort((a, b) => b[1] - a[1]).slice(0, 4)
    .map(([reason, n]) => ({ k: reason.length > 34 ? reason.slice(0, 32) + "…" : reason, v: n }));
}

export default function Overview() {
  const { t } = useT();
  const ct = useChartTheme();
  const { data: positions } = usePositionsQuery();
  const { data: pnl } = usePnlQuery();
  const { data: series } = usePnlSeriesQuery();
  const { data: gates } = useGateDecisionsQuery(50);
  const { data: acct } = useIbAccountQuery();

  const rejects = (gates ?? []).filter((g) => !g.accepted).length;
  let cum = 0;
  const curve = (series ?? []).map((p) => ({
    t: new Date(p.computed_at).toLocaleDateString(undefined, { month: "short", day: "2-digit" }),
    equity: (cum += p.realized),
  }));
  const s = acct?.summary ?? {};
  const acctNum = (k: string) => (s[k] ? +s[k] : null);
  const marginUse = acctNum("NetLiquidation") && acctNum("InitMarginReq")
    ? (acctNum("InitMarginReq")! / acctNum("NetLiquidation")!) : null;

  const metrics: MetricDef[] = [
    { k: t("open_positions"), v: positions?.length ?? "—", tone: "accent",
      sub: t("bot_db_log"),
      detail: { rows: (positions ?? []).slice(0, 8).map((p) => ({
        k: `${expiry(p.expiry)} · ${p.dte} ${t("dte")}`, v: num(p.entry_credit) })),
        note: t("m_note_open_pos") } },

    { k: t("closed_trades"), v: pnl?.closed ?? "—",
      detail: { note: t("m_note_demo") } },

    { k: t("gate_rejects"), v: rejects, tone: rejects > 0 ? "neg" : "pos",
      ratio: gates?.length ? { win: gates.length - rejects, loss: rejects } : undefined,
      sub: gates?.length ? `${gates.length - rejects} ${t("f_pass")} · ${rejects} ${t("f_reject")}` : undefined,
      detail: {
        formula: <>{rejects} rejected of {gates?.length ?? 0} recent decisions</>,
        rows: topReasons(gates ?? []),
        note: t("m_note_gates") } },

    { k: t("net_liq"), v: acctNum("NetLiquidation") ? money(acctNum("NetLiquidation")!) : "—",
      tone: "accent",
      detail: { rows: [
        { k: t("avail_funds"), v: acctNum("AvailableFunds") ? money(acctNum("AvailableFunds")!) : "—" },
        { k: t("excess_liq"), v: acctNum("ExcessLiquidity") ? money(acctNum("ExcessLiquidity")!) : "—" },
      ], note: t("m_note_live_acct") } },

    { k: t("buying_power"), v: acctNum("BuyingPower") ? money(acctNum("BuyingPower")!) : "—",
      detail: { note: t("m_note_live_acct") } },

    { k: t("init_margin"), v: acctNum("InitMarginReq") ? money(acctNum("InitMarginReq")!) : "—",
      meter: marginUse ?? undefined,
      sub: marginUse != null ? `${num(marginUse * 100, 1)}% ${t("m_of_nav")}` : undefined,
      detail: {
        formula: marginUse != null
          ? <>{money(acctNum("InitMarginReq")!)} ÷ {money(acctNum("NetLiquidation")!)}</> : undefined,
        rows: [
          { k: t("maint_margin"), v: acctNum("MaintMarginReq") ? money(acctNum("MaintMarginReq")!) : "—" },
          { k: t("excess_liq"), v: acctNum("ExcessLiquidity") ? money(acctNum("ExcessLiquidity")!) : "—" },
        ], note: t("m_note_margin") } },
  ];


  return (
    <>
      <Cluster
        hero={{
          label: t("realized_pnl"), value: pnl?.total ?? null,
          curve: curve.map((c) => c.equity),
          sub: `${pnl?.closed ?? 0} ${t("closed_trades").toLowerCase()}`,
          detail: {
            formula: <>Σ realized P&amp;L over every closed bot trade</>,
            rows: [
              { k: t("closed_trades"), v: pnl?.closed ?? 0 },
              { k: t("open_positions"), v: positions?.length ?? 0 },
            ],
            note: t("m_note_demo"),
          },
        }}
        metrics={metrics} />

      <Panel title={t("equity_curve")}>
        {curve.length === 0 ? <Empty text={t("no_closed")} /> : (
          <div className="ltr" style={{ padding: "1rem", height: 300 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={curve} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
                <defs>
                  <linearGradient id="eq" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={ct.blue} stopOpacity={0.45} />
                    <stop offset="100%" stopColor={ct.blue} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke={ct.grid} vertical={false} />
                <XAxis dataKey="t" stroke={ct.axis} fontSize={12} tickLine={false} minTickGap={40} />
                <YAxis stroke={ct.axis} fontSize={12} tickLine={false} tickFormatter={(v) => `$${num(v, 0)}`} />
                <Tooltip contentStyle={CHART_TIP} formatter={(v: number) => money(v)} />
                <Area type="monotone" dataKey="equity" stroke={ct.blue} strokeWidth={2} fill="url(#eq)" isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </Panel>
    </>
  );
}
