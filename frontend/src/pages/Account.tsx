import { useMemo } from "react";
import type { ColDef } from "ag-grid-community";
import {
  useIbAccountQuery, useIbPositionsQuery, useIbExecutionsQuery, useIbOrdersQuery,
  useIbPnlQuery, useIbNavSeriesQuery,
} from "../store/api";
import { Panel, Empty, Tile, PnLTile, StatusPill, Pill } from "../components/ui";
import DataGrid, { numCol, dateCol, pnlCol, asDate, fmtDateTime } from "../components/DataGrid";
import { useT } from "../i18n/useT";
import { money, num, dt } from "../lib/format";
import { useChartTheme, CHART_TIP } from "../lib/chartTheme";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
} from "recharts";
import type { IbPosition, IbExecution, IbOrder } from "../store/types";

export default function Account() {
  const { t } = useT();
  const C = useChartTheme();
  const { data: acct } = useIbAccountQuery(undefined, { pollingInterval: 20000 });
  const { data: pos } = useIbPositionsQuery(undefined, { pollingInterval: 20000 });
  const { data: exe } = useIbExecutionsQuery(undefined, { pollingInterval: 20000 });
  const { data: ord } = useIbOrdersQuery(undefined, { pollingInterval: 20000 });
  const { data: pnl } = useIbPnlQuery(undefined, { pollingInterval: 30000 });
  const { data: navs } = useIbNavSeriesQuery(undefined, { pollingInterval: 60000 });

  const posCols = useMemo<ColDef<IbPosition>[]>(() => [
    { headerName: t("symbol"), field: "symbol", minWidth: 130, cellClass: "g-strong" },
    { headerName: t("type"), field: "secType", width: 100, flex: 0 },
    { headerName: t("right"), field: "right", width: 90, flex: 0,
      valueFormatter: (p) => (p.value === "P" ? "Put" : p.value === "C" ? "Call" : p.value || "—") },
    numCol<IbPosition>({ headerName: t("strike"), field: "strike",
      valueFormatter: (p) => (p.value ? num(p.value, 0) : "—") }),
    dateCol<IbPosition>({ headerName: t("expiry"), colId: "exp", value: (r) => asDate(r.expiry),
      width: 130, flex: 0 }),
    numCol<IbPosition>({ headerName: t("position"), field: "position", width: 110, flex: 0,
      cellClass: (p) => ["g-num", p.value > 0 ? "g-pos" : p.value < 0 ? "g-neg" : "g-mut"] }),
    numCol<IbPosition>({ headerName: t("avg_cost"), field: "avgCost",
      valueFormatter: (p) => num(p.value) }),
  ], [t]);

  const exeCols = useMemo<ColDef<IbExecution>[]>(() => [
    dateCol<IbExecution>({ headerName: t("time"), colId: "ts", value: (r) => asDate(r.time),
      valueFormatter: (p) => (p.value instanceof Date ? fmtDateTime(p.value) : "—"),
      width: 165, flex: 0, sort: "desc", sortIndex: 0 }),
    { headerName: t("symbol"), field: "symbol", minWidth: 130, cellClass: "g-strong" },
    { headerName: t("right"), field: "right", width: 90, flex: 0,
      valueFormatter: (p) => (p.value === "P" ? "Put" : p.value === "C" ? "Call" : p.value || "—") },
    numCol<IbExecution>({ headerName: t("strike"), field: "strike",
      valueFormatter: (p) => (p.value ? num(p.value, 0) : "—") }),
    { headerName: t("side"), field: "side", width: 92, flex: 0,
      cellRenderer: (p: { value?: string }) =>
        <Pill kind={p.value === "BOT" || p.value === "BUY" ? "info" : "mut"} plain>{p.value}</Pill> },
    numCol<IbExecution>({ headerName: t("qty"), field: "shares", width: 84, flex: 0 }),
    numCol<IbExecution>({ headerName: t("price"), field: "price",
      valueFormatter: (p) => num(p.value) }),
    numCol<IbExecution>({ headerName: t("commission"), field: "commission",
      valueFormatter: (p) => (p.value == null ? "—" : num(p.value)), cellClass: "g-num g-mut" }),
    pnlCol<IbExecution>({ headerName: t("realized"), colId: "r", minWidth: 140,
      value: (r) => r.realizedPNL }),
  ], [t]);

  const ordCols = useMemo<ColDef<IbOrder>[]>(() => [
    { headerName: "Action", field: "action", width: 96, flex: 0 },
    { headerName: t("type"), field: "orderType", width: 96, flex: 0 },
    { headerName: "TIF", field: "tif", width: 80, flex: 0 },
    numCol<IbOrder>({ headerName: t("price"), field: "lmtPrice", valueFormatter: (p) => num(p.value) }),
    numCol<IbOrder>({ headerName: t("qty"), field: "totalQuantity", width: 86, flex: 0 }),
    { headerName: t("status"), field: "status", width: 124, flex: 0,
      cellRenderer: (p: { value?: string }) => <StatusPill status={p.value ?? ""} /> },
  ], [t]);

  const doneCols = useMemo<ColDef<IbOrder>[]>(() => [
    { headerName: "Action", field: "action", width: 96, flex: 0 },
    { headerName: t("type"), field: "orderType", width: 96, flex: 0 },
    numCol<IbOrder>({ headerName: "Filled", field: "filled", width: 90, flex: 0 }),
    numCol<IbOrder>({ headerName: t("price"), field: "avgFillPrice", valueFormatter: (p) => num(p.value) }),
    { headerName: t("status"), field: "status", width: 124, flex: 0,
      cellRenderer: (p: { value?: string }) => <StatusPill status={p.value ?? ""} /> },
  ], [t]);

  if (acct && !acct.connected) return <Empty text={t("acct_offline")} />;
  const s = acct?.summary ?? {};
  const curve = (navs?.series ?? []).map((p) => ({ t: dt(p.ts), nav: p.net_liq }));

  return (
    <>
      <div className="row" style={{ justifyContent: "flex-end" }}>
        <Pill kind="ok">{t("tws_badge")}</Pill>
      </div>
      <div className="tiles">
        <Tile k={t("net_liq")} cls="kpi small" tone="accent">
          {s.NetLiquidation ? money(+s.NetLiquidation) : "—"}</Tile>
        <PnLTile k={t("perf_today")} value={pnl?.daily ?? null} small />
        <PnLTile k={t("perf_unrealized")} value={pnl?.unrealized ?? null} small />
        <Tile k={t("buying_power")} cls="kpi small" tone="flat">
          {s.BuyingPower ? money(+s.BuyingPower) : "—"}</Tile>
      </div>

      <Panel title={t("perf_nav_curve")} right={<span className="muted">{navs?.series?.length ?? 0} pts</span>}>
        {curve.length < 2 ? <div className="empty">{t("perf_history_note")}</div> : (
          <div className="chartbox ltr" style={{ height: 260 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={curve} margin={{ top: 8, right: 12, bottom: 0, left: 8 }}>
                <defs><linearGradient id="anv" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={C.blue} stopOpacity={0.45} />
                  <stop offset="100%" stopColor={C.blue} stopOpacity={0} /></linearGradient></defs>
                <CartesianGrid stroke={C.grid} vertical={false} />
                <XAxis dataKey="t" stroke={C.axis} fontSize={12} tickLine={false} minTickGap={40} />
                <YAxis stroke={C.axis} fontSize={12} tickLine={false} domain={["auto", "auto"]}
                  tickFormatter={(v) => `$${num(v, 0)}`} />
                <Tooltip contentStyle={CHART_TIP} formatter={(v: number) => money(v)} />
                <Area type="monotone" dataKey="nav" stroke={C.blue} strokeWidth={2} fill="url(#anv)" isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </Panel>

      <Panel title={t("live_positions")} count={pos?.items.length ?? 0}
        right={<span className="muted ltr mono" style={{ fontSize: 11 }}>{t("req_positions")}</span>}>
        <DataGrid<IbPosition> rows={pos?.items ?? []} columns={posCols} exportName="ib-positions"
          emptyText={t("no_open_pos")} maxHeight={420} />
      </Panel>

      <Panel title={t("executions")} count={exe?.items.length ?? 0}
        right={<span className="muted ltr mono" style={{ fontSize: 11 }}>{t("req_exec")}</span>}>
        <DataGrid<IbExecution> rows={exe?.items ?? []} columns={exeCols} exportName="ib-executions"
          emptyText={t("no_exec")} maxHeight={460}
          rowClass={(r) => r.realizedPNL == null ? "" : r.realizedPNL >= 0 ? "row-win" : "row-loss"} />
      </Panel>

      <div className="grid2">
        <Panel title={t("open_orders")} count={ord?.open.length ?? 0}>
          <DataGrid<IbOrder> rows={ord?.open ?? []} columns={ordCols}
            emptyText={t("no_open_ord")} maxHeight={340} />
        </Panel>
        <Panel title={t("completed_orders")} count={ord?.completed.length ?? 0}>
          <DataGrid<IbOrder> rows={ord?.completed ?? []} columns={doneCols}
            emptyText={t("no_comp_ord")} maxHeight={340} />
        </Panel>
      </div>
    </>
  );
}
