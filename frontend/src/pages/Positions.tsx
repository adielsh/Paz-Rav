import { useMemo } from "react";
import type { ColDef } from "ag-grid-community";
import { usePositionsQuery } from "../store/api";
import { Panel, Empty, StatusPill } from "../components/ui";
import DataGrid, { numCol, dateCol, asDate, fmtDateTime } from "../components/DataGrid";
import { useT } from "../i18n/useT";
import { num } from "../lib/format";
import type { Trade } from "../store/types";

export default function Positions() {
  const { t } = useT();
  const { data, isLoading } = usePositionsQuery(undefined, { pollingInterval: 15000 });
  const rows = data ?? [];

  const cols = useMemo<ColDef<Trade>[]>(() => [
    dateCol<Trade>({
      headerName: t("opened"), colId: "opened", value: (r) => asDate(r.created_at),
      valueFormatter: (p) => (p.value instanceof Date ? fmtDateTime(p.value) : "—"),
      width: 160, minWidth: 150, flex: 0, sort: "desc", sortIndex: 0,
    }),
    dateCol<Trade>({ headerName: t("expiry"), colId: "exp", value: (r) => asDate(r.expiry),
      width: 130, minWidth: 120, flex: 0 }),
    numCol<Trade>({ headerName: t("dte"), field: "dte", width: 84, flex: 0 }),
    numCol<Trade>({ headerName: t("vix"), field: "vix_avg", width: 88, flex: 0,
      valueFormatter: (p) => num(p.value, 1) }),
    numCol<Trade>({ headerName: t("p_long"), field: "put_long_strike",
      valueFormatter: (p) => num(p.value, 0) }),
    numCol<Trade>({ headerName: t("p_short"), field: "put_short_strike",
      valueFormatter: (p) => num(p.value, 0) }),
    numCol<Trade>({ headerName: t("c_short"), field: "call_short_strike",
      valueFormatter: (p) => num(p.value, 0) }),
    numCol<Trade>({ headerName: t("c_long"), field: "call_long_strike",
      valueFormatter: (p) => num(p.value, 0) }),
    numCol<Trade>({ headerName: t("credit"), field: "entry_credit", width: 106, flex: 0,
      valueFormatter: (p) => num(p.value), cellClass: "g-num g-pos" }),
    numCol<Trade>({ headerName: t("qty"), field: "quantity", width: 80, flex: 0 }),
    { headerName: t("status"), field: "status", width: 124, minWidth: 110, flex: 0,
      cellRenderer: (p: { value?: string }) => <StatusPill status={p.value ?? ""} /> },
  ], [t]);

  if (isLoading) return <Empty text={t("loading")} />;

  return (
    <Panel title={t("open_condors")} count={rows.length}
      right={<span className="muted" style={{ fontSize: 11 }}>{t("bot_db_log")}</span>}>
      <DataGrid<Trade> rows={rows} columns={cols} exportName="open-positions"
        getRowId={(r) => String(r.id)} emptyText={t("no_open_pos")} maxHeight={600}
        rowClass={() => "row-open"} />
    </Panel>
  );
}
