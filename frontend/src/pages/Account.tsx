import { useMemo } from "react";
import type { ColDef } from "ag-grid-community";
import {
  useIbAccountQuery, useIbPositionsQuery, useIbExecutionsQuery, useIbOrdersQuery,
  useIbPnlQuery, useIbNavSeriesQuery,
} from "../store/api";
import { Panel, Empty, StatusPill, Pill } from "../components/ui";
import { Cluster, type MetricDef } from "../components/Metrics";
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

  const A = (k: string) => (s[k] ? +s[k] : null);
  const marginUse = A("NetLiquidation") && A("InitMarginReq")
    ? A("InitMarginReq")! / A("NetLiquidation")! : null;

  const metrics: MetricDef[] = [
    { k: t("perf_unrealized"), v: pnl?.unrealized != null ? money(pnl.unrealized) : "—",
      tone: (pnl?.unrealized ?? 0) >= 0 ? "pos" : "neg",
      detail: { note: t("m_note_unrealized") } },

    { k: t("buying_power"), v: A("BuyingPower") ? money(A("BuyingPower")!) : "—",
      detail: { note: t("m_note_live_acct") } },

    { k: t("init_margin"), v: A("InitMarginReq") ? money(A("InitMarginReq")!) : "—",
      meter: marginUse ?? undefined,
      sub: marginUse != null ? `${num(marginUse * 100, 1)}% ${t("m_of_nav")}` : undefined,
      detail: { rows: [
        { k: t("maint_margin"), v: A("MaintMarginReq") ? money(A("MaintMarginReq")!) : "—" },
        { k: t("net_liq"), v: A("NetLiquidation") ? money(A("NetLiquidation")!) : "—" },
      ], note: t("m_note_margin") } },

    { k: t("excess_liq"), v: A("ExcessLiquidity") ? money(A("ExcessLiquidity")!) : "—",
      tone: "accent", detail: { note: t("m_note_live_acct") } },

    { k: t("avail_funds"), v: A("AvailableFunds") ? money(A("AvailableFunds")!) : "—",
      detail: { note: t("m_note_live_acct") } },

    { k: t("live_positions"), v: pos?.items.length ?? 0, tone: "accent",
      detail: { rows: (pos?.items ?? []).slice(0, 8).map((p) => ({
        k: `${p.symbol} ${p.right || p.secType} ${p.strike ? num(p.strike, 0) : ""}`.trim(),
        v: p.position, tone: p.position >= 0 ? "pos" : "neg" })),
        note: t("req_positions") } },

    { k: t("open_orders"), v: ord?.open.length ?? 0,
      detail: { rows: (ord?.open ?? []).slice(0, 8).map((o) => ({
        k: `${o.action} ${o.orderType} ${o.tif}`, v: num(o.lmtPrice) })) } },

    { k: t("executions"), v: exe?.items.length ?? 0,
      sub: t("req_exec"),
      detail: { note: t("req_exec") } },
  ];


  return (
    <>
      <div className="row" style={{ justifyContent: "flex-end" }}>
        <Pill kind="ok">{t("tws_badge")}</Pill>
      </div>
      <Cluster
        hero={{
          label: t("perf_today"), value: pnl?.daily ?? null,
          curve: (navs?.series ?? []).map((p) => p.net_liq ?? 0).filter((n) => n > 0),
          sub: t("m_note_today"),
          right: (
            <>
              <div className="k">{t("net_liq")}</div>
              <div className="v" style={{ fontSize: "1.6rem" }}>
                {s.NetLiquidation ? money(+s.NetLiquidation) : "—"}
              </div>
              <div className="sub">{acct?.account ?? "—"}</div>
            </>
          ),
          detail: {
            rows: [
              { k: t("perf_unrealized"), v: pnl?.unrealized != null ? money(pnl.unrealized) : "—",
                tone: (pnl?.unrealized ?? 0) >= 0 ? "pos" : "neg" },
              { k: t("realized"), v: pnl?.realized != null ? money(pnl.realized) : "—" },
              { k: t("net_liq"), v: s.NetLiquidation ? money(+s.NetLiquidation) : "—" },
            ],
            note: t("m_note_today"),
          },
        }}
        metrics={metrics} />

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
