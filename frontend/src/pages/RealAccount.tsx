import { useEffect, useMemo, useState } from "react";
import {
  ResponsiveContainer, AreaChart, Area, BarChart, Bar, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine,
} from "recharts";
import type { ColDef } from "ag-grid-community";
import { useFlexDataQuery } from "../store/api";
import { Tile, PnLTile, Panel, Empty, Pill, PnL } from "../components/ui";
import DataGrid, { numCol, dateCol, pnlCol, asDate } from "../components/DataGrid";
import DateRangePicker, { type DateRange } from "../components/DateRangePicker";
import { useT } from "../i18n/useT";
import { money, num, expiry } from "../lib/format";
import { useChartTheme, CHART_TIP } from "../lib/chartTheme";
import type { FlexTrade, FlexNavDay } from "../store/types";

type StatusFilter = "all" | "open" | "closed";
/** A grid row: either a position, or the synthetic full-width row holding its legs. */
type Row = Position & { __detail?: boolean; parent?: Position };
const pct = (v: number) => (v >= 0 ? "+" : "") + num(v, 1) + "%";
const ymd8ToInput = (s: string) => (s.length === 8 ? `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}` : "");
const inputMs = (s: string) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d).getTime(); };

export default function RealAccount() {
  const { t } = useT();
  const C = useChartTheme();
  const tip = CHART_TIP;
  const ax = { stroke: C.axis, fontSize: 12, tickLine: false } as const;
  const { data, isFetching } = useFlexDataQuery();
  const [status, setStatus] = useState<StatusFilter>("all");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const toggleRow = (k: string) => setExpanded((prev) => {
    const n = new Set(prev); n.has(k) ? n.delete(k) : n.add(k); return n;
  });

  const bounds = useMemo(() => {
    const ds = (data?.trades ?? []).map((x) => x.date).filter(Boolean).sort();
    return { min: ds[0] ?? "", max: ds[ds.length - 1] ?? "" };
  }, [data]);
  const [range, setRange] = useState<DateRange>({ from: "", to: "" });
  useEffect(() => {                          // default to the full data range once loaded
    if (bounds.max && (!range.from || !range.to)) {
      setRange({ from: ymd8ToInput(bounds.min), to: ymd8ToInput(bounds.max) });
    }
  }, [bounds]); // eslint-disable-line react-hooks/exhaustive-deps

  const fromMs = range.from ? inputMs(range.from) : -Infinity;
  const toMs = range.to ? inputMs(range.to) : Infinity;

  const allPositions = useMemo(() => buildPositions(data?.trades ?? []), [data]);

  // The window means "P&L booked in here", so decided positions are matched on their CLOSE
  // date — the day the money was actually realized. Filtering on the OPEN date instead made
  // the page disagree with IBKR: for 27 Jul it showed $125 (opened that day) where IBKR
  // reported $474 (closed that day). Still-open positions have booked nothing yet, so they
  // are current state rather than period P&L and stay visible regardless of the range.
  const decided = useMemo(() => allPositions.filter((po) => {
    if (po.status === "open") return false;
    const d = ymd(po.closeDate || po.openDate);
    return isNaN(d) ? true : d >= fromMs && d <= toMs;
  }), [allPositions, fromMs, toMs]);

  const openNow = useMemo(
    () => allPositions.filter((po) => po.status === "open"), [allPositions]);

  const inRange = useMemo(() => [...decided, ...openNow], [decided, openNow]);

  const a = useMemo(() => build(inRange, fromMs, toMs), [inRange, fromMs, toMs]);

  // Commissions come per fill, so they can be scoped to the range properly instead of
  // showing the whole-statement total under a "(period)" label.
  const periodCommissions = useMemo(() => {
    const rows = (data?.trades ?? []).filter((r) => {
      const d = ymd(r.date);
      return isNaN(d) ? false : d >= fromMs && d <= toMs;
    });
    return rows.length ? rows.reduce((s, r) => s + (r.commission ?? 0), 0) : null;
  }, [data, fromMs, toMs]);

  // True period return from the daily NAV blocks (see navReturn below).
  const navPeriod = useMemo(
    () => navReturn(data?.navDays ?? [], range.from, range.to),
    [data, range.from, range.to]);

  const positions = useMemo(() => mergeCopies(     // collapse identical rows + copies count
    inRange.filter((po) => status === "all"
      || (status === "open" ? po.status === "open" : po.status !== "open"))),
    [inRange, status]);

  // Expanded positions get a synthetic full-width row injected right beneath them, which is
  // how AG Grid Community does inline detail (master/detail proper is an Enterprise feature).
  const gridRows = useMemo<Row[]>(() => positions.flatMap((po) =>
    expanded.has(po.key)
      ? [po as Row, { ...po, key: `${po.key}__d`, __detail: true, parent: po } as Row]
      : [po as Row]),
    [positions, expanded]);

  const gridOptions = useMemo(() => ({
    isFullWidthRow: (p: { rowNode: { data?: Row } }) => !!p.rowNode.data?.__detail,
    fullWidthCellRenderer: LegsDetail,
    getRowHeight: (p: { data?: Row }) =>
      p.data?.__detail ? 46 + (p.data.parent?.legView.length ?? 0) * 30 : 38,
  }), []);

  const cols = useMemo<ColDef<Row>[]>(() => [
    {
      headerName: "", colId: "exp", width: 42, minWidth: 42, flex: 0,
      sortable: false, filter: false, resizable: false,
      cellClass: "expandcell",
      cellRenderer: (p: { data?: Row }) => p.data && !p.data.__detail
        ? <span className="expander">{expanded.has(p.data.key) ? "▾" : "▸"}</span> : null,
    },
    {
      headerName: t("col_status"), field: "status", width: 118, minWidth: 110, flex: 0,
      cellRenderer: (p: { data?: Row }) => p.data ? <StatusCell po={p.data} /> : null,
    },
    dateCol<Row>({
      headerName: t("col_opened"), colId: "opened", value: (r) => asDate(r.openTime || r.openDate),
      valueFormatter: (p) => (p.value instanceof Date ? fmtDT(p.value) : "—"),
      width: 152, minWidth: 140, flex: 0, sort: "desc", sortIndex: 0,
    }),
    dateCol<Row>({
      headerName: t("col_closed_date"), colId: "closed", value: (r) => asDate(r.closeDate),
      width: 130, minWidth: 120, flex: 0,
    }),
    dateCol<Row>({
      headerName: t("col_expiry_date"), colId: "expiry",
      value: (r) => asDate(r.expiries[r.expiries.length - 1]),
      width: 130, minWidth: 120, flex: 0,
    }),
    { headerName: t("underlying"), field: "underlying", width: 110, minWidth: 90, flex: 0,
      cellClass: "g-strong" },
    { headerName: t("col_strategy"), field: "type", minWidth: 150,
      cellRenderer: (p: { value?: string }) => {
        const v = p.value ?? "";
        const kind = v.includes("Condor") ? "ok"
          : v.includes("Calendar") || v.includes("Diagonal") ? "warn" : "mut";
        return <Pill kind={kind} plain>{v}</Pill>;
      } },
    numCol<Row>({ headerName: t("col_legs"), field: "legCount", width: 86, flex: 0 }),
    numCol<Row>({ headerName: t("col_copies"), field: "copies", width: 96, flex: 0,
      valueFormatter: (p) => (p.value > 1 ? `×${p.value}` : "1") }),
    numCol<Row>({ headerName: t("col_open_net"), field: "openNet", minWidth: 130,
      valueFormatter: (p) => (p.value ? money(p.value) : "—"),
      cellClass: (p) => ["g-num", p.value > 0 ? "g-pos" : p.value < 0 ? "g-neg" : "g-mut"] }),
    numCol<Row>({ headerName: t("col_close_net"), field: "closeNet", minWidth: 130,
      valueFormatter: (p) => (p.value != null ? money(p.value) : "—"),
      cellClass: (p) => ["g-num", p.value == null ? "g-mut" : p.value > 0 ? "g-pos" : "g-neg"] }),
    pnlCol<Row>({ headerName: t("realized"), colId: "realized", minWidth: 150,
      value: (r) => (r.status === "open" ? null : r.realized) }),
  ], [t, expanded]);

  if (data && !data.configured) {
    return (
      <Panel title={t("nav_real")}>
        <div className="empty">
          <p style={{ fontSize: "1rem", color: "var(--fg)" }}>{t("flex_not_configured")}</p>
          <p className="muted" style={{ maxWidth: 640, margin: "0 auto" }}>{t("flex_setup")}</p>
        </div>
      </Panel>
    );
  }
  if (data && data.ok === false) return <Empty text={`${t("flex_error")}: ${data.error ?? ""}`} />;
  if (!data && isFetching) return <Empty text={t("flex_loading")} />;

  const pf = a.grossLoss > 0 ? a.grossWin / a.grossLoss : Infinity;
  const nav = data?.nav;
  const navEnd = nav?.end ?? 0;
  // Return has to be measured against money actually put in — dividing by the
  // *ending* NAV produced nonsense like −101.5% on an account that lost half.
  const capital = (nav?.start ?? 0) + (nav?.deposits ?? 0);
  const retPct = capital > 0 ? (a.total / capital) * 100 : 0;

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <DateRangePicker value={range} onChange={setRange}
          min={ymd8ToInput(bounds.min)} max={ymd8ToInput(bounds.max)} />
        <div className="row">
          <Legend />
          <span className="muted ltr mono">{data?.account}</span>
          <Pill kind="ok">{t("flex_badge")}</Pill>
        </div>
      </div>

      <div className="tiles">
        <PnLTile k={t("perf_realized")} value={a.total}
          hint={`${t("perf_from")} ${a.decided} ${t("perf_decided")}`} />
        {/* Time-weighted, deposit-adjusted return over exactly the selected window. */}
        <PnLTile k={t("perf_return_period")} value={navPeriod?.pct ?? null} format={pct}
          hint={navPeriod
            ? `NAV ${money(navPeriod.startNav)} → ${money(navPeriod.endNav)}`
            : t("perf_no_nav")} />
        <Tile k={t("a_win_rate")} cls="kpi" tone={a.winRate >= 0.5 ? "pos" : "neg"}
          hint={`${a.wins} W / ${a.losses} L`}>
          {a.decided ? num(a.winRate * 100, 1) + "%" : "—"}</Tile>
        <Tile k={t("a_profit_factor")} cls="kpi" tone={pf >= 1 ? "pos" : "neg"}
          hint={`${money(a.grossWin)} / ${money(-a.grossLoss)}`}>
          {pf === Infinity ? "∞" : num(pf, 2)}</Tile>
        {/* The headline count is trades that BOOKED in the window; open positions are
            current state and are called out separately rather than folded in. */}
        <Tile k={t("perf_trades")} cls="kpi" tone="accent"
          hint={`+ ${a.openCount} ${t("perf_open_now")}`}>{a.decided}</Tile>
      </div>
      <div className="tiles">
        <PnLTile k={t("a_avg_win")} value={a.avgWin} small />
        <PnLTile k={t("a_avg_loss")} value={a.avgLoss} small />
        <PnLTile k={t("a_best")} value={a.best} small />
        <PnLTile k={t("a_worst")} value={a.worst} small />
        <PnLTile k={t("perf_commissions")} value={periodCommissions} small />
        <PnLTile k={t("perf_nav_change_period")} value={navPeriod?.pnl ?? null} small
          hint={navPeriod ? `${navPeriod.days} ${t("perf_days")}` : undefined} />
      </div>

      {/* These three come from the Flex statement header and describe the WHOLE statement.
          They cannot be recomputed per range, so they are separated and labelled as such
          rather than sitting next to period figures pretending to follow the picker. */}
      <div className="tiles stmt">
        <PnLTile k={t("perf_mtm")} value={nav?.mtm ?? null} small hint={t("perf_whole_stmt")} />
        <Tile k={t("perf_nav_end")} cls="kpi small" tone="flat"
          hint={t("perf_whole_stmt")}>{money(navEnd)}</Tile>
        <Tile k={t("perf_capital")} cls="kpi small" tone="flat"
          hint={t("perf_whole_stmt")}>{money(capital)}</Tile>
      </div>

      <div className="note">{t("perf_scope")}</div>

      <Panel title={t("perf_booked")}
        right={<span className="muted mono ltr">{range.from} → {range.to}</span>}>
        {a.equity.length < 2 ? <Empty text={t("perf_no_trades")} /> : (
          <div className="chartbox ltr" style={{ height: 300 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={a.equity} margin={{ top: 8, right: 12, bottom: 0, left: 8 }}>
                <defs>
                  <linearGradient id="re-up" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={C.green} stopOpacity={0.45} />
                    <stop offset="100%" stopColor={C.green} stopOpacity={0} /></linearGradient>
                  <linearGradient id="re-dn" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={C.red} stopOpacity={0.45} />
                    <stop offset="100%" stopColor={C.red} stopOpacity={0} /></linearGradient>
                </defs>
                <CartesianGrid stroke={C.grid} vertical={false} />
                <XAxis dataKey="label" {...ax} minTickGap={40} />
                <YAxis {...ax} width={70} tickFormatter={(v) => `$${num(v, 0)}`} />
                <Tooltip contentStyle={tip} formatter={(v: number) => money(v)} />
                <ReferenceLine y={0} stroke={C.muted} strokeDasharray="3 3" />
                <Area type="monotone" dataKey="equity" isAnimationActive={false}
                  stroke={a.total >= 0 ? C.green : C.red} strokeWidth={2}
                  fill={a.total >= 0 ? "url(#re-up)" : "url(#re-dn)"} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </Panel>

      {/* Real account equity, straight from IBKR's daily NAV blocks — not sampled snapshots. */}
      {navPeriod && navPeriod.curve.length > 1 && (
        <Panel title={t("perf_nav_curve_real")}
          right={<span className="muted mono ltr">{navPeriod.days} {t("perf_days")}</span>}>
          <div className="chartbox ltr" style={{ height: 260 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={navPeriod.curve} margin={{ top: 8, right: 12, bottom: 0, left: 8 }}>
                <defs><linearGradient id="navd" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={navPeriod.pnl >= 0 ? C.green : C.red} stopOpacity={0.4} />
                  <stop offset="100%" stopColor={navPeriod.pnl >= 0 ? C.green : C.red} stopOpacity={0} />
                </linearGradient></defs>
                <CartesianGrid stroke={C.grid} vertical={false} />
                <XAxis dataKey="label" {...ax} minTickGap={40} />
                <YAxis {...ax} width={70} domain={["auto", "auto"]} tickFormatter={(v) => `$${num(v, 0)}`} />
                <Tooltip contentStyle={tip} formatter={(v: number) => money(v)} />
                <Area type="monotone" dataKey="nav" isAnimationActive={false}
                  stroke={navPeriod.pnl >= 0 ? C.green : C.red} strokeWidth={2} fill="url(#navd)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      )}

      <div className="chartgrid">
        <Panel title={t("perf_by_bucket")}>
          {a.buckets.length === 0 ? <Empty text={t("perf_no_trades")} /> : (
            <div className="chartbox ltr">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={a.buckets} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
                  <CartesianGrid stroke={C.grid} vertical={false} />
                  <XAxis dataKey="label" {...ax} /><YAxis {...ax} width={70} tickFormatter={(v) => `$${num(v, 0)}`} />
                  <Tooltip contentStyle={tip} formatter={(v: number) => money(v)} />
                  <ReferenceLine y={0} stroke={C.muted} />
                  <Bar dataKey="pnl" radius={[3, 3, 0, 0]} isAnimationActive={false}>
                    {a.buckets.map((d, i) => <Cell key={i} fill={d.pnl >= 0 ? C.green : C.red} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>
        <Panel title={t("a_pnl_dist")}>
          {a.hist.every((h) => h.count === 0) ? <Empty text={t("perf_no_trades")} /> : (
            <div className="chartbox ltr">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={a.hist} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
                  <CartesianGrid stroke={C.grid} vertical={false} />
                  <XAxis dataKey="bucket" {...ax} /><YAxis {...ax} allowDecimals={false} />
                  <Tooltip contentStyle={tip} />
                  <Bar dataKey="count" radius={[3, 3, 0, 0]} isAnimationActive={false}>
                    {a.hist.map((d, i) => <Cell key={i} fill={d.mid >= 0 ? C.green : C.red} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>
      </div>

      <Panel title={t("perf_positions")} count={positions.length}
        right={<span className="muted" style={{ fontSize: 11 }}>{t("grid_hint")}</span>}>
        <DataGrid<Row>
          rows={gridRows} columns={cols} exportName="positions"
          getRowId={(r) => r.key} emptyText={t("perf_no_trades")}
          onRowClicked={(r) => { if (!r.__detail) toggleRow(r.key); }}
          rowClass={(r) => r.__detail ? "detailrow"
            : r.status === "open" ? "row-open" : r.realized >= 0 ? "row-win" : "row-loss"}
          maxHeight={620} gridOptions={gridOptions}
          toolbar={
            <div className="seg">
              {(["all", "open", "closed"] as StatusFilter[]).map((s) => (
                <button key={s} className={status === s ? "on" : ""} onClick={() => setStatus(s)}>
                  {t(s === "all" ? "filt_all" : s === "open" ? "filt_open" : "filt_closed")}</button>
              ))}
            </div>
          }
        />
      </Panel>

    </>
  );
}

/* ------------------------------------------------------------ sub-views -- */

function Legend() {
  const { t } = useT();
  return (
    <div className="row" style={{ gap: ".4rem" }}>
      <Pill kind="ok">{t("legend_profit")}</Pill>
      <Pill kind="bad">{t("legend_loss")}</Pill>
      <Pill kind="warn">{t("legend_open")}</Pill>
    </div>
  );
}

function StatusCell({ po }: { po: Position }) {
  const { t } = useT();
  if (po.status === "open") return <Pill kind="warn">{t("pos_open")}</Pill>;
  if (po.status === "expired") return <Pill kind="ok">{t("pos_expired")}</Pill>;
  return <Pill kind={po.realized >= 0 ? "ok" : "bad"}>{t("pos_closed")}</Pill>;
}

/**
 * Inline leg breakdown, rendered as an AG Grid full-width row directly under its position.
 * Plain markup rather than a nested grid: a grid inside a grid row fights the outer one for
 * scroll and sizing, and four legs need no sorting.
 */
function LegsDetail(p: { data?: Row }) {
  const { t } = useT();
  const po = p.data?.parent;
  if (!po) return null;
  return (
    <div className="legsdetail">
      <div className="lhead">
        <span className="ttl">{po.underlying} · {po.type}</span>
        <span className="muted mono ltr">{po.expiries.map(expiry).join(", ")}</span>
        {po.status !== "open" && <PnL value={po.realized} chip />}
      </div>
      <table className="legstable ltr">
        <thead><tr>
          <th>{t("side")}</th><th>{t("right")}</th><th className="num">{t("strike")}</th>
          <th>{t("expiry")}</th><th className="num">{t("qty")}</th>
          <th className="num">{t("col_open_px")}</th><th className="num">{t("col_close_px")}</th>
          <th className="num">{t("realized")}</th>
        </tr></thead>
        <tbody>{po.legView.map((l, i) => (
          <tr key={i} className={l.realized > 0 ? "win" : l.realized < 0 ? "loss" : ""}>
            <td><Pill kind={l.side === "BUY" ? "info" : "mut"} plain>{l.side}</Pill></td>
            <td>{l.right === "P" ? "Put" : l.right === "C" ? "Call" : l.right || "—"}</td>
            <td className="num">{l.strike ? num(l.strike, 0) : "—"}</td>
            <td className="num">{expiry(l.expiry)}</td>
            <td className="num">{Math.abs(l.qty)}</td>
            <td className="num">{l.openPx != null ? num(l.openPx) : "—"}</td>
            <td className="num">{l.closePx != null ? num(l.closePx) : "—"}</td>
            <td className="num">{l.realized ? <PnL value={l.realized} /> : "—"}</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function fmtDT(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

const ymd = (s: string) => {
  const d = (s || "").slice(0, 8);
  return d.length === 8 ? new Date(+d.slice(0, 4), +d.slice(4, 6) - 1, +d.slice(6, 8)).getTime() : NaN;
};

function aggregate(fills: FlexTrade[]): FlexTrade[] {
  const m = new Map<string, FlexTrade>();
  for (const f of fills) {
    const key = `${f.dateTime}|${f.symbol}|${f.buySell}|${f.price}|${f.openClose}`;
    const cur = m.get(key);
    if (!cur) { m.set(key, { ...f }); continue; }
    cur.quantity = (cur.quantity ?? 0) + (f.quantity ?? 0);
    cur.realized = (cur.realized ?? 0) + (f.realized ?? 0);
    cur.commission = (cur.commission ?? 0) + (f.commission ?? 0);
    cur.proceeds = (cur.proceeds ?? 0) + (f.proceeds ?? 0);
  }
  return [...m.values()];
}

/**
 * True period return from IBKR's daily NAV blocks.
 *
 * Chained (time-weighted) rather than (end-start)/start, because deposits landing mid-window
 * would otherwise be counted as performance. Each day contributes its own P&L over the capital
 * actually at work that day, and the daily factors are compounded. Over the full statement the
 * naive formula returns -474,054% (NAV opened at $5.36); this returns -42.6%.
 */
function navReturn(days: FlexNavDay[], from: string, to: string) {
  const f = from.replace(/-/g, ""), tt = to.replace(/-/g, "");
  const win = days.filter((d) => (!f || d.date >= f) && (!tt || d.date <= tt));
  if (!win.length) return null;
  let factor = 1, pnl = 0, deposits = 0;
  for (const d of win) {
    const base = d.start + d.deposits;              // capital at work that day
    const gain = d.end - d.start - d.deposits;      // pure P&L, deposits removed
    pnl += gain; deposits += d.deposits;
    if (base > 0) factor *= 1 + gain / base;
  }
  return {
    days: win.length, startNav: win[0].start, endNav: win[win.length - 1].end,
    deposits, pnl, pct: (factor - 1) * 100,
    curve: win.map((d) => ({ label: `${d.date.slice(4, 6)}/${d.date.slice(6, 8)}`, nav: +d.end.toFixed(2) })),
  };
}

// ---- KPIs / charts, computed PER POSITION ----
//
// This used to run over individual leg fills, which made every per-trade figure
// wrong: one leg of a January SPX spread reported +$72,840 as the "best trade"
// while the whole position actually netted −$2,129. A trade is a position — all
// its legs netted — so every statistic below is derived from `Position`, and
// P&L is attributed to the date the position was closed (when it was booked).
function build(positions: Position[], fromMs: number, toMs: number) {
  const monthlyBuckets = (toMs - fromMs) / 864e5 > 120;

  // `positions` already only contains decided rows inside the window plus the currently
  // open ones; the open ones have booked nothing, so they never enter the P&L maths.
  const decided = positions.filter((p) => p.status !== "open")
    .sort((a, b) => (a.closeDate || a.openDate).localeCompare(b.closeDate || b.openDate));
  const openCount = positions.length - decided.length;

  const R = decided.map((p) => p.realized);
  const wins = R.filter((r) => r > 0), losses = R.filter((r) => r < 0);
  const grossWin = wins.reduce((s, r) => s + r, 0);
  const grossLoss = Math.abs(losses.reduce((s, r) => s + r, 0));
  const total = R.reduce((s, r) => s + r, 0);

  let cum = 0;
  const equity = decided.map((p) => { cum += p.realized;
    const d = p.closeDate || p.openDate;
    return { label: `${d.slice(4, 6)}/${d.slice(6, 8)}`, equity: +cum.toFixed(2) }; });

  const bkey = (d: string) => monthlyBuckets
    ? `${d.slice(0, 4)}-${d.slice(4, 6)}` : `${d.slice(4, 6)}/${d.slice(6, 8)}`;
  const bm = new Map<string, number>();
  decided.forEach((p) => { const k = bkey(p.closeDate || p.openDate);
    bm.set(k, (bm.get(k) ?? 0) + p.realized); });
  const buckets = [...bm.entries()].sort().map(([label, pnl]) => ({ label, pnl: +pnl.toFixed(2) }))
    .filter((b) => b.pnl !== 0);

  const edges = [-1e9, -1000, -500, -250, -100, 0, 100, 250, 500, 1e9];
  const labels = ["<-1k", "-1k…-500", "-500…-250", "-250…-100", "-100…0",
                  "0…100", "100…250", "250…500", ">500"];
  const hist = labels.map((bucket, i) => ({ bucket, mid: (edges[i] + edges[i + 1]) / 2,
    count: R.filter((v) => v >= edges[i] && v < edges[i + 1]).length }));

  return {
    count: positions.length, decided: decided.length, openCount, total,
    winRate: decided.length ? wins.length / decided.length : 0,
    wins: wins.length, losses: losses.length,
    grossWin, grossLoss, avgWin: wins.length ? grossWin / wins.length : 0,
    avgLoss: losses.length ? -grossLoss / losses.length : 0,
    best: R.length ? Math.max(...R) : 0, worst: R.length ? Math.min(...R) : 0,
    equity, buckets, hist,
  };
}

// ---- Position tracking: match opens to closes, classify strategy ----
export interface LegView {
  right: string; strike: number | null; expiry: string; side: string; qty: number;
  openPx: number | null; closePx: number | null; realized: number;
}
export interface Position {
  key: string; underlying: string; type: string; status: "open" | "closed" | "expired";
  openDate: string; openTime: string; sortDate: number; expiries: string[]; legCount: number;
  openNet: number; closeNet: number | null; realized: number; legView: LegView[]; copies: number;
  /** yyyymmdd the position was closed out (or expired) — when its P&L was booked. */
  closeDate: string;
}

// Signature of a position's structure (ignores price/time): same legs = "same position".
const legSig = (legs: LegView[]) =>
  legs.map((l) => `${l.side}${l.right}${l.strike}@${l.expiry}`).sort().join(",");

// Collapse structurally-identical positions of the same status into one row with a copies count.
function mergeCopies(list: Position[]): Position[] {
  const groups = new Map<string, Position[]>();
  for (const po of list) {
    const sig = `${po.underlying}|${po.status}|${legSig(po.legView)}`;
    const g = groups.get(sig) ?? []; g.push(po); groups.set(sig, g);
  }
  const avg = (xs: (number | null)[]) => {
    const v = xs.filter((x): x is number => x != null);
    return v.length ? +(v.reduce((s, x) => s + x, 0) / v.length).toFixed(2) : null;
  };
  const sum = (xs: (number | null)[]) => +xs.reduce((s: number, x) => s + (x ?? 0), 0).toFixed(2);
  return [...groups.values()].map((g) => {
    const base = g[0];
    if (g.length === 1) return base;
    const legView = base.legView.map((bl) => {
      const ms = g.map((p) => p.legView.find((v) =>
        v.right === bl.right && v.strike === bl.strike && v.expiry === bl.expiry && v.side === bl.side))
        .filter((m): m is LegView => !!m);
      return { ...bl, qty: ms.reduce((s, m) => s + m.qty, 0),
        openPx: avg(ms.map((m) => m.openPx)), closePx: avg(ms.map((m) => m.closePx)),
        realized: sum(ms.map((m) => m.realized)) };
    });
    const latest = g.reduce((a, b) => (b.openTime > a.openTime ? b : a));
    return {
      ...base, copies: g.length, openNet: sum(g.map((p) => p.openNet)),
      closeNet: g.every((p) => p.closeNet == null) ? null : sum(g.map((p) => p.closeNet)),
      realized: sum(g.map((p) => p.realized)),
      openTime: latest.openTime, openDate: latest.openDate, sortDate: latest.sortDate,
      closeDate: g.reduce((c, p) => (p.closeDate > c ? p.closeDate : c), ""), legView,
    };
  }).sort((a, b) => b.openTime.localeCompare(a.openTime));
}

function classify(legs: FlexTrade[]): string {
  const n = legs.length;
  const exps = new Set(legs.map((l) => l.expiry));
  const strikes = new Set(legs.map((l) => l.strike));
  const p = legs.filter((l) => l.putCall === "P").length;
  const c = legs.filter((l) => l.putCall === "C").length;
  const multiExp = exps.size > 1;
  const rn = (l: FlexTrade) => (l.putCall === "P" ? "Put" : l.putCall === "C" ? "Call" : "");
  if (n === 1) return "Single " + rn(legs[0]);
  if (n === 2) {
    if (multiExp && strikes.size === 1) return "Calendar";
    if (multiExp) return "Diagonal";
    if (p === 2) return "Put spread";
    if (c === 2) return "Call spread";
    return "Strangle / Straddle";
  }
  if (n === 4 && p === 2 && c === 2 && !multiExp) return "Iron Condor";
  if (n === 4 && multiExp) return "Double Diagonal";
  if (multiExp) return `${n}-leg (multi-exp)`;
  return `${n}-leg`;
}

const todayYmd = () => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime(); };

interface Lot { remaining: number; stratId: number; }
interface Strat {
  id: number; date: string; dateTime: string; underlying: string; openLegs: FlexTrade[];
  openQty: number; closedQty: number; realized: number; closeNet: number;
  closeTime: string; closeDate: string;
  closeByLeg: Map<string, { px: number | null; realized: number }>;
}

// Accurate position tracking via per-symbol FIFO lots + expiry handling.
// - A closing trade (openClose='C') consumes open lots FIFO and attaches close price + realized.
// - A strategy fully consumed by closes  -> CLOSED.
// - A strategy still holding lots but past its expiry -> EXPIRED (no closing trade exists; credit kept).
// - Otherwise (future expiry, lots remain) -> OPEN.  This is what fixes "old trades shown as open".
function buildPositions(fills: FlexTrade[]): Position[] {
  const legs = aggregate(fills);
  const evMap = new Map<string, FlexTrade[]>();
  for (const l of legs) {
    const k = `${l.dateTime}|${l.underlying}`;
    const arr = evMap.get(k) ?? []; arr.push(l); evMap.set(k, arr);
  }
  const events = [...evMap.values()].map((ls, i) => ({
    id: i, dateTime: ls[0].dateTime, date: ls[0].date, underlying: ls[0].underlying, legs: ls,
  })).sort((a, b) => a.dateTime.localeCompare(b.dateTime));

  const queues = new Map<string, Lot[]>();
  const strat = new Map<number, Strat>();

  const consumeClose = (l: FlexTrade) => {
    const q = queues.get(l.symbol); if (!q) return;
    let toClose = Math.abs(l.quantity ?? 0);
    const legQty = Math.abs(l.quantity ?? 0);
    while (toClose > 1e-9 && q.length) {
      const lot = q[0];
      const take = Math.min(lot.remaining, toClose);
      lot.remaining -= take; toClose -= take;
      const s = strat.get(lot.stratId);
      if (s) {
        const frac = legQty ? take / legQty : 0;
        s.closedQty += take;
        s.realized += (l.realized ?? 0) * frac;
        s.closeNet += (l.proceeds ?? 0) * frac;
        const prev = s.closeByLeg.get(l.symbol);
        s.closeByLeg.set(l.symbol, { px: l.price, realized: (prev?.realized ?? 0) + (l.realized ?? 0) * frac });
        if (l.dateTime > s.closeTime) { s.closeTime = l.dateTime; s.closeDate = l.date; }
      }
      if (lot.remaining <= 1e-9) q.shift();
    }
  };

  for (const ev of events) {
    const openLegs = ev.legs.filter((l) => l.openClose !== "C");
    const closeLegs = ev.legs.filter((l) => l.openClose === "C");
    if (openLegs.length) {
      strat.set(ev.id, {
        id: ev.id, date: ev.date, dateTime: ev.dateTime, underlying: ev.underlying, openLegs,
        openQty: openLegs.reduce((s, l) => s + Math.abs(l.quantity ?? 0), 0),
        closedQty: 0, realized: 0, closeNet: 0, closeTime: "", closeDate: "",
        closeByLeg: new Map(),
      });
      for (const l of openLegs) {
        const q = queues.get(l.symbol) ?? [];
        q.push({ remaining: Math.abs(l.quantity ?? 0), stratId: ev.id });
        queues.set(l.symbol, q);
      }
    }
    for (const l of closeLegs) consumeClose(l);
  }

  const today = todayYmd();
  const positions: Position[] = [];
  for (const s of strat.values()) {
    const expiries = [...new Set(s.openLegs.map((l) => l.expiry))].sort();
    const maxExp = expiries[expiries.length - 1];
    const maxExpMs = maxExp ? ymd(maxExp) : NaN;
    const openNet = sumBy(s.openLegs, "proceeds");
    const fullyClosed = s.closedQty >= s.openQty - 1e-6;

    let status: Position["status"], closeNet: number | null = null, realized = 0;
    let closeDate = s.closeDate;
    if (fullyClosed) { status = "closed"; closeNet = +s.closeNet.toFixed(2); realized = +s.realized.toFixed(2); }
    // Never closed and past expiry: the credit was kept, booked on the expiry date.
    else if (!isNaN(maxExpMs) && maxExpMs < today) { status = "expired"; realized = openNet; closeDate = maxExp; }
    else { status = "open"; closeDate = ""; }

    const legView: LegView[] = s.openLegs.map((l) => {
      const cl = s.closeByLeg.get(l.symbol);
      return { right: l.putCall, strike: l.strike, expiry: l.expiry, side: l.buySell,
        qty: l.quantity ?? 0, openPx: l.price, closePx: cl?.px ?? null, realized: +(cl?.realized ?? 0).toFixed(2) };
    });

    positions.push({
      key: `p${s.id}`, underlying: s.underlying, type: classify(s.openLegs), status,
      openDate: s.date, openTime: s.dateTime, sortDate: ymd(s.date), expiries,
      legCount: s.openLegs.length, openNet, closeNet, realized, legView, copies: 1, closeDate,
    });
  }
  return positions.sort((a, b) => b.openTime.localeCompare(a.openTime));
}

const sumBy = (legs: FlexTrade[], f: "proceeds" | "realized") =>
  +legs.reduce((s, l) => s + ((l[f] as number) ?? 0), 0).toFixed(2);
