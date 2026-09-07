import { useMemo, useState } from "react";
import type { ColDef } from "ag-grid-community";
import { useEngineHealthQuery, useEngineTopQuery } from "../store/api";
import type { EngineCandidate, EngineLeg, EngineTopGroup } from "../store/types";
import { Cluster, type MetricDef } from "../components/Metrics";
import DataGrid, { numCol, pnlCol } from "../components/DataGrid";
import { Panel, Empty, Pill, PnL } from "../components/ui";
import { money, num, expiry as fmtExpiry } from "../lib/format";
import { useT } from "../i18n/useT";

/**
 * The Paz Rav strategy engine's ranked candidates.
 *
 * This page is a window onto a different half of the system than the rest of the console.
 * Everything else here reports on the SPX daemon — a bot that actually trades. The engine
 * only ranks ideas across a universe of names: it holds no broker connection and the API
 * exposes no route that could act on one of these rows. The footer says so on every scan,
 * because a table of strikes next to an "approvals" tab is exactly where that could get
 * blurred.
 *
 * Every dollar figure the engine emits is PER SHARE; a US option contract is x100. That
 * multiplication happens here (`usd`), and it is applied to money only — strikes and
 * breakevens are price levels and are never multiplied.
 */

/** Per-share figure -> per-contract dollars. */
const usd = (v: number | null | undefined) => money((v ?? 0) * 100);

type Row = EngineCandidate & { __id: string; __detail?: boolean; parent?: EngineCandidate };

export default function Ideas() {
  const { t } = useT();
  const { data: health } = useEngineHealthQuery(undefined, { pollingInterval: 60000 });
  const { data, isLoading } = useEngineTopQuery(10, { pollingInterval: 30000 });
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const groups: EngineTopGroup[] = data?.available ? data.groups : [];
  const all = useMemo(() => groups.flatMap((g) => g.trades), [groups]);

  const stats = useMemo(() => {
    if (!all.length) return null;
    const underlyings = new Set(all.map((c) => c.underlying));
    const byStrategy = (s: string) => all.filter((c) => c.strategy === s).length;
    const best = all.reduce((a, b) => (b.credit > a.credit ? b : a));
    const riskiest = all.reduce((a, b) => (b.max_loss > a.max_loss ? b : a));
    const topScore = all.reduce((a, b) => (b.score > a.score ? b : a));
    return {
      count: all.length,
      underlyings: underlyings.size,
      condors: byStrategy("iron_condor"),
      dacs: byStrategy("dacs"),
      avgPop: all.reduce((s, c) => s + c.pop, 0) / all.length,
      avgDte: all.reduce((s, c) => s + c.dte, 0) / all.length,
      best, riskiest, topScore,
    };
  }, [all]);

  // The engine is a separate container and may simply not be running. That is a normal
  // state, not an error — say what it is and how to start it, and leave the rest alone.
  if (data && !data.available) {
    return (
      <Panel title={t("title_ideas")}>
        <Empty text={`${t("eng_offline")} ${t("eng_offline_hint")}`} />
      </Panel>
    );
  }
  if (isLoading && !data) return <Panel title={t("title_ideas")}><Empty text={t("loading")} /></Panel>;
  if (!stats) {
    return (
      <Panel title={t("title_ideas")} right={<SourcePill health={health} />}>
        <Empty text={t("eng_none")} />
      </Panel>
    );
  }

  const metrics: MetricDef[] = [
    {
      k: t("eng_ideas_found"), v: num(stats.count, 0), tone: "accent",
      sub: t("eng_across").replace("{n}", String(stats.underlyings)),
      detail: {
        formula: <>{stats.condors} {t("eng_condors")} + {stats.dacs} {t("eng_dacs")}</>,
        note: t("eng_note_scope"),
      },
    },
    {
      k: t("eng_condors"), v: num(stats.condors, 0),
      detail: { rows: [{ k: t("eng_across").replace("{n}", ""), v: String(stats.underlyings) }] },
    },
    { k: t("eng_dacs"), v: num(stats.dacs, 0) },
    {
      k: t("eng_avg_pop"), v: `${num(stats.avgPop * 100, 1)}%`, meter: stats.avgPop,
      detail: { formula: <>Σ pop ÷ {stats.count}</>, note: t("eng_f_pop") },
    },
    {
      k: t("eng_worst_risk"), v: usd(stats.riskiest.max_loss), tone: "neg",
      sub: `${stats.riskiest.underlying} · ${label(t, stats.riskiest.strategy)}`,
      detail: {
        formula: <>{num(stats.riskiest.max_loss)} × 100</>,
        rows: [
          { k: t("eng_credit"), v: usd(stats.riskiest.credit) },
          { k: t("eng_width"), v: num(stats.riskiest.width) },
        ],
        note: t("eng_f_perlot"),
      },
    },
    {
      k: t("eng_avg_dte"), v: num(stats.avgDte, 0),
      detail: { formula: <>Σ dte ÷ {stats.count}</> },
    },
  ];

  return (
    <>
      <Cluster
        hero={{
          label: t("eng_best_credit"),
          value: stats.best.credit * 100,
          sub: <>{stats.best.underlying} · {label(t, stats.best.strategy)} · {stats.best.dte}d</>,
          right: (
            <div className="row" style={{ gap: ".5rem" }}>
              <span className="muted">{t("eng_best_score")} {num(stats.topScore.score)}</span>
              <SourcePill health={health} />
            </div>
          ),
          detail: {
            formula: <>{num(stats.best.credit)} × 100</>,
            rows: [
              { k: t("eng_max_profit"), v: usd(stats.best.max_profit), tone: "pos" },
              { k: t("eng_max_loss"), v: usd(stats.best.max_loss), tone: "neg" },
              { k: t("eng_pop"), v: `${num(stats.best.pop * 100, 1)}%` },
              { k: t("eng_score"), v: num(stats.best.score) },
            ],
            // The largest credit is not automatically the best trade — it is usually the
            // one carrying the most risk. Saying so here is the point of the drill-down.
            note: t("eng_f_perlot"),
          },
        }}
        metrics={metrics}
      />

      {groups.map((g) => (
        <IdeaGrid key={g.strategy} group={g} expanded={expanded} setExpanded={setExpanded} />
      ))}

      <div className="note">{t("eng_advisory")}</div>
    </>
  );
}

/* ------------------------------------------------------------------ pieces -- */

function label(t: (k: never) => string, strategy: string): string {
  // Only two strategies are user-facing (FOCUS_STRATEGIES in the engine's registry);
  // anything else is shown raw rather than silently mislabelled.
  if (strategy === "iron_condor") return t("eng_condors" as never);
  if (strategy === "dacs") return t("eng_dacs" as never);
  return strategy;
}

function SourcePill({ health }: { health?: { available: boolean; data_source?: string } }) {
  const { t } = useT();
  if (!health?.available) return null;
  const src = health.data_source;
  const text = src === "fixture" ? t("eng_source_fixture")
    : src === "yfinance" ? t("eng_source_delayed") : src;
  // Warn tone deliberately: neither source is execution-grade, and this page sits one
  // click from a tab where trades are approved.
  return <Pill kind="warn">{t("eng_source")}: {text}</Pill>;
}

function IdeaGrid({ group, expanded, setExpanded }: {
  group: EngineTopGroup;
  expanded: Set<string>;
  setExpanded: (s: Set<string>) => void;
}) {
  const { t } = useT();

  const toggle = (id: string) => {
    const next = new Set(expanded);
    if (next.has(id)) next.delete(id); else next.add(id);
    setExpanded(next);
  };

  // Same synthetic full-width row the real-account grid uses: AG Grid Community has no
  // master/detail, so an expanded row gets a detail row injected right beneath it.
  const rows = useMemo<Row[]>(() => group.trades.flatMap((c, i) => {
    const id = `${group.strategy}:${c.underlying}:${c.u_idx ?? i}`;
    const base: Row = { ...c, __id: id };
    return expanded.has(id)
      ? [base, { ...base, __id: `${id}__d`, __detail: true, parent: c }]
      : [base];
  }), [group, expanded]);

  const gridOptions = useMemo(() => ({
    isFullWidthRow: (p: { rowNode: { data?: Row } }) => !!p.rowNode.data?.__detail,
    fullWidthCellRenderer: LegsDetail,
    getRowHeight: (p: { data?: Row }) =>
      p.data?.__detail ? 58 + (p.data.parent?.legs.length ?? 0) * 30 : 38,
  }), []);

  const cols = useMemo<ColDef<Row>[]>(() => [
    {
      headerName: "", colId: "exp", width: 42, minWidth: 42, flex: 0,
      sortable: false, filter: false, resizable: false, cellClass: "expandcell",
      cellRenderer: (p: { data?: Row }) => p.data && !p.data.__detail
        ? <span className="expander">{expanded.has(p.data.__id) ? "▾" : "▸"}</span> : null,
    },
    {
      headerName: t("symbol"), field: "underlying", width: 110, minWidth: 90, flex: 0,
      cellClass: "g-strong",
    },
    {
      headerName: t("eng_verdict"), colId: "verdict", width: 118, minWidth: 100, flex: 0,
      valueGetter: (p) => p.data?.verdict ?? "",
      cellRenderer: (p: { data?: Row }) => {
        if (!p.data || p.data.__detail || !p.data.verdict) return null;
        const take = p.data.verdict === "take";
        return <Pill kind={take ? "ok" : "warn"}>{t(take ? "eng_take" : "eng_caution")}</Pill>;
      },
    },
    numCol<Row>({ headerName: t("dte"), field: "dte", width: 84, minWidth: 70, flex: 0 }),
    numCol<Row>({
      headerName: t("eng_credit"), colId: "credit", width: 120, minWidth: 100, flex: 0,
      valueGetter: (p) => (p.data ? p.data.credit * 100 : null),
      valueFormatter: (p) => (p.value == null ? "—" : money(p.value)),
    }),
    numCol<Row>({
      headerName: t("eng_max_profit"), colId: "mp", width: 128, minWidth: 110, flex: 0,
      valueGetter: (p) => (p.data ? p.data.max_profit * 100 : null),
      valueFormatter: (p) => (p.value == null ? "—" : money(p.value)),
      cellClass: ["g-num", "g-pos"],
    }),
    // Negated so the sign is explicit: the engine reports max_loss as a magnitude, and a
    // risk figure rendered without its minus reads like a gain at a glance.
    pnlCol<Row>({
      headerName: t("eng_max_loss"), colId: "ml", width: 128, minWidth: 110, flex: 0,
      value: (r) => (r.__detail ? null : -r.max_loss * 100),
    }),
    numCol<Row>({
      headerName: t("eng_pop"), colId: "pop", width: 96, minWidth: 84, flex: 0,
      valueGetter: (p) => (p.data ? p.data.pop * 100 : null),
      valueFormatter: (p) => (p.value == null ? "—" : `${num(p.value, 1)}%`),
    }),
    numCol<Row>({
      headerName: t("eng_score"), colId: "score", width: 100, minWidth: 88, flex: 0,
      valueGetter: (p) => p.data?.score ?? null,
      valueFormatter: (p) => (p.value == null ? "—" : num(p.value)),
      sort: "desc", sortIndex: 0,
    }),
    numCol<Row>({
      headerName: t("eng_width"), colId: "width", minWidth: 90,
      valueGetter: (p) => p.data?.width ?? null,
      valueFormatter: (p) => (p.value == null ? "—" : num(p.value)),
    }),
  ], [t, expanded]);

  return (
    <Panel title={label(t, group.strategy)} count={group.trades.length} flush>
      <DataGrid<Row>
        rows={rows}
        columns={cols}
        getRowId={(r) => r.__id}
        gridOptions={gridOptions}
        rowClass={(r) => (r.__detail ? "detailrow" : r.verdict === "take" ? "win" : "")}
        onRowClicked={(r) => { if (!r.__detail) toggle(r.__id); }}
        exportName={`engine-${group.strategy}`}
        emptyText={t("eng_none")}
      />
    </Panel>
  );
}

function LegsDetail(p: { data?: Row }) {
  const { t } = useT();
  const c = p.data?.parent;
  if (!c) return null;
  return (
    <div className="legsdetail">
      <div className="lhead">
        <span className="ttl">{c.underlying} · {c.dte}d</span>
        <span className="muted mono ltr">
          {t("eng_breakevens")}: {c.breakevens.map((b) => num(b)).join(" / ")}
        </span>
        <PnL value={c.max_profit * 100} chip />
      </div>
      <table className="legstable ltr">
        <thead><tr>
          <th>{t("side")}</th><th>{t("right")}</th><th className="num">{t("strike")}</th>
          <th>{t("expiry")}</th><th className="num">{t("qty")}</th>
          <th className="num">IV</th><th className="num">Δ</th>
        </tr></thead>
        <tbody>{c.legs.map((l: EngineLeg, i: number) => (
          <tr key={i} className={l.side === "sell" ? "win" : ""}>
            <td><Pill kind={l.side === "buy" ? "info" : "mut"} plain>{l.side}</Pill></td>
            <td>{l.option_type === "put" ? "Put" : "Call"}</td>
            {/* A strike is a price level, never multiplied by the contract size. */}
            <td className="num">{num(l.strike, 2)}</td>
            <td className="num">{l.expiry ? fmtExpiry(l.expiry.replace(/-/g, "")) : "—"}</td>
            <td className="num">{Math.abs(l.quantity)}</td>
            <td className="num">{l.iv != null ? `${num(l.iv * 100, 1)}%` : "—"}</td>
            <td className="num">{l.delta != null ? num(l.delta, 3) : "—"}</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}
