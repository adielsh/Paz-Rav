import { useCallback, useMemo, useRef, useState } from "react";
import { AgGridReact } from "ag-grid-react";
import {
  AllCommunityModule, ModuleRegistry, themeQuartz,
  type ColDef, type GridApi, type GridReadyEvent, type GridOptions,
} from "ag-grid-community";
import { useAppSelector } from "../store/hooks";
import { useT } from "../i18n/useT";

ModuleRegistry.registerModules([AllCommunityModule]);

/* AG Grid can't read CSS custom properties for its own theme params, so the two
   palettes are mirrored from index.css here. Keep them in sync with :root. */
const DARK = {
  backgroundColor: "#101622", foregroundColor: "#eaf1fa", chromeBackgroundColor: "#171f2e",
  headerBackgroundColor: "#171f2e", headerTextColor: "#7b8aa0", borderColor: "#1f2836",
  accentColor: "#5c9bff", rowHoverColor: "#171f2e", oddRowBackgroundColor: "#12192600",
  menuBackgroundColor: "#0c1018", menuTextColor: "#eaf1fa", panelBackgroundColor: "#0c1018",
  panelTitleBarBackgroundColor: "#171f2e", subtleTextColor: "#7b8aa0", iconColor: "#7b8aa0",
  tooltipBackgroundColor: "#0c1018", tooltipTextColor: "#eaf1fa", invalidColor: "#ff5a52",
  browserColorScheme: "dark" as const,
};
const LIGHT = {
  backgroundColor: "#ffffff", foregroundColor: "#0d1725", chromeBackgroundColor: "#f3f6fb",
  headerBackgroundColor: "#f3f6fb", headerTextColor: "#5d6f85", borderColor: "#dfe6f0",
  accentColor: "#2563eb", rowHoverColor: "#f3f6fb", oddRowBackgroundColor: "#ffffff00",
  menuBackgroundColor: "#ffffff", menuTextColor: "#0d1725", panelBackgroundColor: "#ffffff",
  panelTitleBarBackgroundColor: "#f3f6fb", subtleTextColor: "#5d6f85", iconColor: "#5d6f85",
  tooltipBackgroundColor: "#0d1725", tooltipTextColor: "#ffffff", invalidColor: "#d0342c",
  browserColorScheme: "light" as const,
};
const SHAPE = {
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  cellFontFamily: 'ui-monospace, "SF Mono", "Cascadia Mono", Consolas, monospace',
  fontSize: 13, headerFontSize: 10.5, headerFontWeight: 700, headerHeight: 38,
  rowHeight: 38, spacing: 6, borderRadius: 8, wrapperBorder: false, wrapperBorderRadius: 0,
  cellHorizontalPadding: 14, columnBorder: false, headerColumnBorder: false,
};

export interface DataGridProps<T> {
  rows: T[];
  columns: ColDef<T>[];
  /** Row height in px (default 38). */
  rowHeight?: number;
  /** Grid body height. Number = px; "auto" sizes to content up to `maxHeight`. */
  height?: number | "auto";
  maxHeight?: number;
  /** Extra controls rendered in the toolbar, before the search box. */
  toolbar?: React.ReactNode;
  /** Per-row class names — used for win/loss tinting. */
  rowClass?: (row: T) => string | undefined;
  /** Basename for the CSV export file. Omit to hide the export button. */
  exportName?: string;
  /** Detail renderer for expandable rows (e.g. option legs). */
  getRowId?: (row: T) => string;
  emptyText?: string;
  onRowClicked?: (row: T) => void;
  gridOptions?: GridOptions<T>;
}

export default function DataGrid<T>({
  rows, columns, rowHeight = 38, height = "auto", maxHeight = 620,
  toolbar, rowClass, exportName, getRowId, emptyText, onRowClicked, gridOptions,
}: DataGridProps<T>) {
  const { t, rtl } = useT();
  const theme = useAppSelector((s) => s.ui.theme);
  const [quick, setQuick] = useState("");
  const [visible, setVisible] = useState(rows.length);
  const api = useRef<GridApi<T> | null>(null);

  const gridTheme = useMemo(
    () => themeQuartz.withParams({ ...SHAPE, ...(theme === "light" ? LIGHT : DARK) }),
    [theme]);

  const defaultColDef = useMemo<ColDef<T>>(() => ({
    sortable: true,
    filter: true,
    floatingFilter: false,
    resizable: true,
    minWidth: 90,
    flex: 1,
    suppressHeaderMenuButton: false,
  }), []);

  const onGridReady = useCallback((e: GridReadyEvent<T>) => {
    api.current = e.api;
    setVisible(e.api.getDisplayedRowCount());
  }, []);

  const refreshCount = useCallback(() => {
    if (api.current) setVisible(api.current.getDisplayedRowCount());
  }, []);

  const clearFilters = () => { api.current?.setFilterModel(null); setQuick(""); };
  const exportCsv = () => api.current?.exportDataAsCsv({
    fileName: `${exportName}-${new Date().toISOString().slice(0, 10)}.csv`,
  });

  const bodyHeight = height === "auto"
    ? Math.min(maxHeight, 38 + Math.max(rows.length, 1) * rowHeight + 4)
    : height;

  return (
    <div className="gridwrap">
      <div className="gridtoolbar">
        {toolbar}
        <div className="searchwrap">
          <span className="mag" aria-hidden>⌕</span>
          <input className="search" value={quick} placeholder={t("grid_search")}
            onChange={(e) => setQuick(e.target.value)} />
          {quick && <button className="clr" onClick={() => setQuick("")} aria-label={t("grid_clear")}>✕</button>}
        </div>
        <button className="ghost" onClick={clearFilters}>{t("grid_reset")}</button>
        {exportName && <button className="ghost" onClick={exportCsv}>{t("grid_export")}</button>}
        <div className="spacer" />
        <span className="rowcount"><b>{visible}</b> / {rows.length} {t("grid_rows")}</span>
      </div>

      <div className="ag-theme-condor" style={{ height: bodyHeight, width: "100%" }}>
        <AgGridReact<T>
          theme={gridTheme}
          rowData={rows}
          columnDefs={columns}
          defaultColDef={defaultColDef}
          quickFilterText={quick}
          enableRtl={rtl}
          rowHeight={rowHeight}
          headerHeight={38}
          animateRows={false}
          suppressCellFocus
          getRowId={getRowId ? (p) => getRowId(p.data) : undefined}
          getRowClass={rowClass ? (p) => (p.data ? rowClass(p.data) : undefined) : undefined}
          onGridReady={onGridReady}
          onFilterChanged={refreshCount}
          onModelUpdated={refreshCount}
          onRowClicked={onRowClicked ? (e) => e.data && onRowClicked(e.data) : undefined}
          overlayNoRowsTemplate={`<span class="ag-overlay-no-rows-center" style="color:var(--muted)">${
            escapeHtml(emptyText ?? t("grid_empty"))}</span>`}
          {...gridOptions}
        />
      </div>
    </div>
  );
}

const escapeHtml = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

/* ------------------------------------------------------------ column kit -- */

/** Numeric column: mono font, right-aligned, numeric filter, numeric sort. */
export function numCol<T>(c: ColDef<T>): ColDef<T> {
  return {
    filter: "agNumberColumnFilter",
    type: "numericColumn",
    cellClass: "g-num",
    headerClass: "num",
    ...c,
  };
}

/**
 * Date column. `value` must return a `yyyymmdd`, ISO string or Date — it is
 * normalised to a real Date so sorting and the date filter are chronological,
 * never lexicographic.
 */
export function dateCol<T>(c: ColDef<T> & { value: (row: T) => string | Date | null | undefined }): ColDef<T> {
  const { value, ...rest } = c;
  return {
    filter: "agDateColumnFilter",
    filterParams: { browserDatePicker: true, comparator: dateFilterComparator },
    valueGetter: (p) => (p.data ? asDate(value(p.data)) : null),
    valueFormatter: (p) => (p.value instanceof Date ? fmtDate(p.value) : "—"),
    cellClass: "g-num",
    comparator: (a: Date | null, b: Date | null) =>
      (a ? a.getTime() : 0) - (b ? b.getTime() : 0),
    ...rest,
  };
}

/** P&L column: signed, colored, with an arrow — the sign is never ambiguous. */
export function pnlCol<T>(c: ColDef<T> & { value: (row: T) => number | null | undefined }): ColDef<T> {
  const { value, ...rest } = c;
  return numCol<T>({
    valueGetter: (p) => (p.data ? value(p.data) ?? null : null),
    cellClass: (p) => ["g-num", p.value == null ? "g-mut" : p.value > 0 ? "g-pos" : p.value < 0 ? "g-neg" : "g-mut"],
    valueFormatter: (p) => {
      const v = p.value as number | null;
      if (v == null) return "—";
      const arrow = v > 0 ? "▲ " : v < 0 ? "▼ " : "";
      return arrow + (v > 0 ? "+" : "") + v.toLocaleString(undefined,
        { style: "currency", currency: "USD", maximumFractionDigits: 2 });
    },
    ...rest,
  });
}

export function asDate(v: string | Date | null | undefined): Date | null {
  if (!v) return null;
  if (v instanceof Date) return isNaN(v.getTime()) ? null : v;
  const s = String(v);
  if (/^\d{8}$/.test(s)) return new Date(+s.slice(0, 4), +s.slice(4, 6) - 1, +s.slice(6, 8));
  if (/^\d{8}[;T ]/.test(s)) {                                   // IBKR Flex: 20250131;143000
    const d = new Date(+s.slice(0, 4), +s.slice(4, 6) - 1, +s.slice(6, 8));
    const hh = s.slice(9, 11), mm = s.slice(11, 13);
    if (hh && mm) { d.setHours(+hh, +mm); }
    return d;
  }
  const d = new Date(s);
  return isNaN(d.getTime()) ? null : d;
}

const p2 = (n: number) => String(n).padStart(2, "0");
export const fmtDate = (d: Date) =>
  `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}`;
export const fmtDateTime = (d: Date) =>
  `${fmtDate(d)} ${p2(d.getHours())}:${p2(d.getMinutes())}`;

/** AG Grid's date filter hands us a midnight Date to compare against the cell. */
function dateFilterComparator(filterDate: Date, cellValue: unknown): number {
  const d = cellValue instanceof Date ? cellValue : asDate(cellValue as string);
  if (!d) return -1;
  const day = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  return day.getTime() - filterDate.getTime() === 0 ? 0 : day < filterDate ? -1 : 1;
}
