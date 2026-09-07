import { useMemo } from "react";
import type { ColDef } from "ag-grid-community";
import { useGateDecisionsQuery } from "../store/api";
import { useAppDispatch, useAppSelector } from "../store/hooks";
import { setGateFilter, type GateFilter } from "../store/uiSlice";
import { Panel, Empty, Pill } from "../components/ui";
import DataGrid, { numCol, dateCol, asDate, fmtDateTime } from "../components/DataGrid";
import { useT } from "../i18n/useT";
import type { TKey } from "../i18n/translations";
import { num } from "../lib/format";
import type { GateDecision } from "../store/types";

const FILTERS: { f: GateFilter; key: TKey }[] = [
  { f: "all", key: "f_all" }, { f: "pass", key: "f_pass" }, { f: "reject", key: "f_reject" },
];

export default function Gates() {
  const { t } = useT();
  const { data } = useGateDecisionsQuery(200, { pollingInterval: 20000 });
  const filter = useAppSelector((s) => s.ui.gateFilter);    // Redux client state
  const dispatch = useAppDispatch();
  const rows = (data ?? []).filter((g) =>
    filter === "all" || (filter === "pass" ? g.accepted : !g.accepted));

  const cols = useMemo<ColDef<GateDecision>[]>(() => [
    dateCol<GateDecision>({
      headerName: t("time"), colId: "ts", value: (r) => asDate(r.created_at),
      valueFormatter: (p) => (p.value instanceof Date ? fmtDateTime(p.value) : "—"),
      width: 165, minWidth: 150, flex: 0, sort: "desc", sortIndex: 0,
    }),
    numCol<GateDecision>({ headerName: t("vix"), field: "vix", width: 90, flex: 0,
      valueFormatter: (p) => (p.value == null ? "—" : num(p.value, 1)) }),
    { headerName: t("result"), colId: "res", width: 116, minWidth: 100, flex: 0,
      valueGetter: (p) => (p.data?.accepted ? "PASS" : "REJECT"),
      cellRenderer: (p: { value?: string }) =>
        <Pill kind={p.value === "PASS" ? "ok" : "bad"}>{p.value}</Pill> },
    { headerName: t("reason"), field: "reason", minWidth: 220, cellClass: "g-strong" },
    { headerName: t("details"), colId: "det", minWidth: 260, cellClass: "g-num g-mut g-ltr",
      valueGetter: (p) => (p.data?.details ? JSON.stringify(p.data.details) : "—"),
      tooltipValueGetter: (p) => String(p.value ?? "") },
  ], [t]);

  if (!data) return <Empty text={t("loading")} />;

  return (
    <Panel title={t("preflight")} count={rows.length}
      right={
        <div className="seg">
          {FILTERS.map((x) => (
            <button key={x.f} className={filter === x.f ? "on" : ""}
              onClick={() => dispatch(setGateFilter(x.f))}>{t(x.key)}</button>
          ))}
        </div>
      }>
      <DataGrid<GateDecision> rows={rows} columns={cols} exportName="gate-decisions"
        getRowId={(r) => String(r.id)} emptyText={t("no_gates")} maxHeight={640}
        rowClass={(r) => (r.accepted ? "row-win" : "row-loss")} />
    </Panel>
  );
}
