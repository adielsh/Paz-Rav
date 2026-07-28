import {
  usePositionsQuery, usePnlQuery, usePnlSeriesQuery, useGateDecisionsQuery, useIbAccountQuery,
} from "../store/api";
import { Tile, PnLTile, Panel, Empty } from "../components/ui";
import { useT } from "../i18n/useT";
import { money, num } from "../lib/format";
import { useChartTheme, CHART_TIP } from "../lib/chartTheme";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";

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

  return (
    <>
      <div className="tiles">
        <Tile k={t("open_positions")} cls="kpi" tone="accent">{positions?.length ?? "—"}</Tile>
        <PnLTile k={t("realized_pnl")} value={pnl?.total ?? null} />
        <Tile k={t("closed_trades")} cls="kpi" tone="flat">{pnl?.closed ?? "—"}</Tile>
        <Tile k={t("gate_rejects")} cls="kpi" tone={rejects > 0 ? "warn" : "flat"}>{rejects}</Tile>
      </div>

      <div className="tiles">
        <Tile k={t("net_liq")} cls="kpi small" tone="accent">
          {s.NetLiquidation ? money(+s.NetLiquidation) : "—"}</Tile>
        <Tile k={t("buying_power")} cls="kpi small" tone="flat">
          {s.BuyingPower ? money(+s.BuyingPower) : "—"}</Tile>
        <Tile k={t("init_margin")} cls="kpi small" tone="flat">
          {s.InitMarginReq ? money(+s.InitMarginReq) : "—"}</Tile>
        <Tile k={t("excess_liq")} cls="kpi small" tone="flat">
          {s.ExcessLiquidity ? money(+s.ExcessLiquidity) : "—"}</Tile>
      </div>

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
