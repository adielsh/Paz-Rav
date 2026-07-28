import { useEffect, useMemo, useState } from "react";
import type { ColDef } from "ag-grid-community";
import { useTradesQuery } from "../store/api";
import { useAppDispatch, useAppSelector } from "../store/hooks";
import { setTradeStatus, type TradeStatusFilter } from "../store/uiSlice";
import { Panel, Empty, StatusPill } from "../components/ui";
import DataGrid, { numCol, dateCol, pnlCol, asDate, fmtDateTime } from "../components/DataGrid";
import DateRangePicker, { toISO, type DateRange } from "../components/DateRangePicker";
import { useT } from "../i18n/useT";
import type { TKey } from "../i18n/translations";
import { num } from "../lib/format";
import type { Trade } from "../store/types";

const FILTERS: { f: TradeStatusFilter; key: TKey }[] = [
  { f: "all", key: "f_all" }, { f: "open", key: "st_open" }, { f: "closed", key: "st_closed" },
  { f: "stopped", key: "st_stopped" }, { f: "expired", key: "st_expired" },
];

export default function Trades() {
  const { t } = useT();
  const { data } = useTradesQuery(500, { pollingInterval: 20000 });
  const filter = useAppSelector((s) => s.ui.tradeStatus);   // Redux client state
  const dispatch = useAppDispatch();

  // Date bounds come from the data, so the picker can never offer an empty range.
  const bounds = useMemo(() => {
    const ds = (data ?? []).map((r) => asDate(r.created_at)).filter((d): d is Date => !!d)
      .sort((a, b) => a.getTime() - b.getTime());
    return { min: ds[0] ? toISO(ds[0]) : "", max: ds[ds.length - 1] ? toISO(ds[ds.length - 1]) : "" };
  }, [data]);
  const [range, setRange] = useState<DateRange>({ from: "", to: "" });
  useEffect(() => {
    if (bounds.max && (!range.from || !range.to)) setRange({ from: bounds.min, to: bounds.max });
  }, [bounds]); // eslint-disable-line react-hooks/exhaustive-deps

  const rows = useMemo(() => {
    const from = range.from ? new Date(range.from + "T00:00:00").getTime() : -Infinity;
    const to = range.to ? new Date(range.to + "T23:59:59").getTime() : Infinity;
    return (data ?? []).filter((r) => {
      if (filter !== "all" && r.status !== filter) return false;
      const d = asDate(r.created_at);
      return !d || (d.getTime() >= from && d.getTime() <= to);
    });
  }, [data, filter, range]);

  const cols = useMemo<ColDef<Trade>[]>(() => [
    dateCol<Trade>({
      headerName: t("opened"), colId: "opened", value: (r) => asDate(r.created_at),
      valueFormatter: (p) => (p.value instanceof Date ? fmtDateTime(p.value) : "—"),
      width: 160, minWidth: 150, flex: 0, sort: "desc", sortIndex: 0,
    }),
    dateCol<Trade>({
      headerName: t("closed"), colId: "closedAt", value: (r) => asDate(r.closed_at),
      valueFormatter: (p) => (p.value instanceof Date ? fmtDateTime(p.value) : "—"),
      width: 160, minWidth: 150, flex: 0,
    }),
    dateCol<Trade>({ headerName: t("expiry"), colId: "exp", value: (r) => asDate(r.expiry),
      width: 130, minWidth: 120, flex: 0 }),
    numCol<Trade>({ headerName: t("dte"), field: "dte", width: 84, flex: 0 }),
    numCol<Trade>({ headerName: t("vix"), field: "vix_avg", width: 90, flex: 0,
      valueFormatter: (p) => num(p.value, 1) }),
    numCol<Trade>({ headerName: "ΔP / ΔC", colId: "deltas", width: 116, flex: 0, filter: false,
      valueGetter: (p) => p.data ? `${num(p.data.target_put_delta, 2)}/${num(p.data.target_call_delta, 2)}` : "",
      cellClass: "g-num g-mut" }),
    numCol<Trade>({ headerName: t("credit"), field: "entry_credit", width: 110, flex: 0,
      valueFormatter: (p) => num(p.value) }),
    numCol<Trade>({ headerName: t("qty"), field: "quantity", width: 80, flex: 0 }),
    pnlCol<Trade>({ headerName: t("realized"), colId: "realized", minWidth: 150,
      value: (r) => r.realized ?? null }),
    { headerName: t("status"), field: "status", width: 130, minWidth: 110, flex: 0,
      cellRenderer: (p: { value?: string }) => <StatusPill status={p.value ?? ""} /> },
  ], [t]);

  if (!data) return <Empty text={t("loading")} />;

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <DateRangePicker value={range} onChange={setRange} min={bounds.min} max={bounds.max} />
        <div className="seg">
          {FILTERS.map((x) => (
            <button key={x.f} className={filter === x.f ? "on" : ""}
              onClick={() => dispatch(setTradeStatus(x.f))}>{t(x.key)}</button>
          ))}
        </div>
      </div>

      <Panel title={t("trade_history")} count={rows.length}
        right={<span className="muted" style={{ fontSize: 11 }}>{t("grid_hint")}</span>}>
        <DataGrid<Trade> rows={rows} columns={cols} exportName="trades"
          getRowId={(r) => String(r.id)} emptyText={t("no_trades")} maxHeight={640}
          rowClass={(r) => r.realized == null ? "row-open" : r.realized >= 0 ? "row-win" : "row-loss"} />
      </Panel>
    </>
  );
}
