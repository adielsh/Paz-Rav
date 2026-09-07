import { useMemo, useState } from "react";
import type { ColDef } from "ag-grid-community";
import { useProposalsQuery, useDecideProposalMutation } from "../store/api";
import { Panel, Empty, Pill } from "../components/ui";
import DataGrid, { numCol, dateCol, asDate, fmtDateTime } from "../components/DataGrid";
import { useT } from "../i18n/useT";
import { num, expiry as fmtExpiry } from "../lib/format";
import type { TradeProposal, ProposalStatus } from "../store/types";

const TONE: Record<ProposalStatus, "ok" | "bad" | "warn" | "info" | "mut"> = {
  pending: "warn", approved: "info", placed: "ok",
  rejected: "mut", failed: "bad", expired: "mut",
};

export default function Proposals() {
  const { t } = useT();
  const { data, isLoading } = useProposalsQuery(100, { pollingInterval: 10000 });
  const rows = data ?? [];
  const pending = rows.filter((p) => p.status === "pending");
  const history = rows.filter((p) => p.status !== "pending");

  const cols = useMemo<ColDef<TradeProposal>[]>(() => [
    { headerName: t("col_status"), field: "status", width: 120, flex: 0,
      cellRenderer: (p: { value?: ProposalStatus }) =>
        <Pill kind={TONE[p.value ?? "pending"]}>{t(`ps_${p.value}` as never)}</Pill> },
    dateCol<TradeProposal>({ headerName: t("prop_raised"), colId: "ts",
      value: (r) => asDate(r.created_at),
      valueFormatter: (p) => (p.value instanceof Date ? fmtDateTime(p.value) : "—"),
      width: 160, flex: 0, sort: "desc", sortIndex: 0 }),
    dateCol<TradeProposal>({ headerName: t("prop_decided"), colId: "dts",
      value: (r) => asDate(r.decided_at),
      valueFormatter: (p) => (p.value instanceof Date ? fmtDateTime(p.value) : "—"),
      width: 160, flex: 0 }),
    dateCol<TradeProposal>({ headerName: t("expiry"), colId: "exp",
      value: (r) => asDate(r.expiry), width: 128, flex: 0 }),
    numCol<TradeProposal>({ headerName: t("credit"), field: "combo_mid", width: 106, flex: 0,
      valueFormatter: (p) => num(p.value), cellClass: "g-num g-pos" }),
    numCol<TradeProposal>({ headerName: t("prop_filled_credit"), field: "placed_credit",
      width: 120, flex: 0, valueFormatter: (p) => (p.value == null ? "—" : num(p.value)) }),
    numCol<TradeProposal>({ headerName: t("vix"), field: "vix_avg", width: 84, flex: 0,
      valueFormatter: (p) => num(p.value, 1) }),
    { headerName: t("reason"), colId: "why", minWidth: 260, flex: 2, cellClass: "g-mut g-ltr",
      valueGetter: (p) => p.data?.error ?? p.data?.note ?? "—",
      tooltipValueGetter: (p) => String(p.value ?? "") },
    { headerName: t("prop_by"), field: "decided_by", width: 110, flex: 0 },
  ], [t]);

  if (isLoading) return <Empty text={t("loading")} />;

  return (
    <>
      {/* When a decision is waiting it gets the whole stage. The explainer only shows when
          there is nothing to decide — mid-decision it is noise. */}
      {pending.length === 0 ? (
        <>
          <Panel title={t("prop_pending")}><Empty text={t("prop_none")} /></Panel>
          <div className="note">{t("prop_explain")}</div>
        </>
      ) : pending.map((p) => <ProposalCard key={p.id} p={p} />)}

      <Panel title={t("prop_history")} count={history.length}>
        <DataGrid<TradeProposal> rows={history} columns={cols} exportName="proposals"
          getRowId={(r) => String(r.id)} emptyText={t("prop_no_history")} maxHeight={460}
          rowClass={(r) => r.status === "placed" ? "row-win"
            : r.status === "failed" ? "row-loss" : ""} />
      </Panel>
    </>
  );
}

const MAX_LOTS = 20;
const usd0 = (v: number) => "$" + num(v, 0);

/**
 * The decision surface. Deliberately narrow: what you sell, what you collect, what you can
 * lose, and how many. Diagnostics (VIX, spread, deltas) sit in one muted footer line —
 * they inform the decision but shouldn't compete with it.
 */
function ProposalCard({ p }: { p: TradeProposal }) {
  const { t } = useT();
  const [decide, { isLoading }] = useDecideProposalMutation();
  const [qty, setQty] = useState(Math.max(1, p.quantity || 1));
  const [note, setNote] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const act = async (decision: "approve" | "reject") => {
    setErr(null);
    try {
      await decide({ id: p.id, decision, note: note.trim() || undefined,
        quantity: decision === "approve" ? qty : undefined }).unwrap();
    } catch (e) {
      const msg = (e as { data?: { detail?: string } })?.data?.detail;
      setErr(msg ?? t("prop_error"));
    }
  };

  const credit = p.combo_mid ?? 0;
  const width = p.put_short_strike - p.put_long_strike;
  const creditTotal = credit * 100 * qty;
  const maxLossTotal = (width - credit) * 100 * qty;
  const bump = (d: number) => setQty((q) => Math.min(MAX_LOTS, Math.max(1, q + d)));

  return (
    <div className="propcard">
      <div className="propcard-hd">
        <div>
          <h2>SPX Iron Condor</h2>
          <div className="sub">
            {fmtExpiry(p.expiry)} · {p.dte} {t("dte")}
          </div>
        </div>
        <div className="row"><Expires at={p.expires_at} /></div>
      </div>

      <Ladder p={p} />

      {/* The two numbers the decision actually turns on. */}
      <div className="propnums">
        <div className="pn win">
          <div className="k">{t("prop_you_collect")}</div>
          <div className="v">+{usd0(creditTotal)}</div>
          <div className="sub">{num(credit)} × 100 × {qty}</div>
        </div>
        <div className="pn lose">
          <div className="k">{t("prop_you_risk")}</div>
          <div className="v">−{usd0(maxLossTotal)}</div>
          <div className="sub">{t("prop_width")} {num(width, 0)}</div>
        </div>
      </div>

      <div className="propbuy">
        <div className="qty">
          <span className="lbl">{t("prop_copies")}</span>
          <div className="stepper">
            <button onClick={() => bump(-1)} disabled={qty <= 1} aria-label="-">−</button>
            <input type="number" min={1} max={MAX_LOTS} value={qty}
              onChange={(e) => setQty(Math.min(MAX_LOTS, Math.max(1, +e.target.value || 1)))} />
            <button onClick={() => bump(1)} disabled={qty >= MAX_LOTS} aria-label="+">+</button>
          </div>
        </div>
        <button className="bigbuy" disabled={isLoading} onClick={() => act("approve")}>
          {t("prop_approve")} · {qty} {qty === 1 ? t("prop_lot") : t("prop_lots")}
        </button>
        <button className="ghost bigreject" disabled={isLoading} onClick={() => act("reject")}>
          {t("prop_reject")}
        </button>
      </div>

      {err && <div className="properr">{err}</div>}

      <div className="propfoot">
        <input className="input" value={note} placeholder={t("prop_note")}
          onChange={(e) => setNote(e.target.value)} />
        <div className="diag">
          <span>{t("vix")} {num(p.vix_avg, 1)}</span>
          <span>Δ {num(p.target_put_delta, 2)}/{num(p.target_call_delta, 2)}</span>
          <span>{t("prop_spread")} {p.combo_spread == null ? "—" : num(p.combo_spread)}</span>
        </div>
      </div>
    </div>
  );
}

/** Strike ladder: the profit zone is the gap between the two short strikes. */
function Ladder({ p }: { p: TradeProposal }) {
  const { t } = useT();
  const lo = p.put_long_strike, hi = p.call_long_strike;
  const span = hi - lo || 1;
  const at = (s: number) => ((s - lo) / span) * 100;
  const zoneL = at(p.put_short_strike), zoneR = at(p.call_short_strike);

  return (
    <div className="ladder ltr">
      <div className="track">
        <div className="zone" style={{ left: `${zoneL}%`, width: `${zoneR - zoneL}%` }} />
        <div className="wing" style={{ left: 0, width: `${zoneL}%` }} />
        <div className="wing" style={{ left: `${zoneR}%`, width: `${100 - zoneR}%` }} />
        {[p.put_long_strike, p.put_short_strike, p.call_short_strike, p.call_long_strike]
          .map((s, i) => (
            <div key={i} className={`mk ${i === 1 || i === 2 ? "short" : "long"}`}
              style={{ left: `${at(s)}%` }}>
              <span className="dot" /><span className="lbl">{num(s, 0)}</span>
            </div>
          ))}
      </div>
      <div className="ladlegend">
        <span className="sell">■ {t("prop_sell")}</span>
        <span className="zonekey">■ {t("prop_zone")}</span>
        <span className="buy">■ {t("prop_buy")}</span>
      </div>
    </div>
  );
}

/** Live countdown — a proposal that ages out stops being actionable. */
function Expires({ at }: { at: string | null }) {
  const { t } = useT();
  if (!at) return null;
  const ms = new Date(at).getTime() - Date.now();
  if (ms <= 0) return <Pill kind="bad">{t("ps_expired")}</Pill>;
  const mins = Math.floor(ms / 60000);
  const label = mins >= 60 ? `${Math.floor(mins / 60)}h ${mins % 60}m` : `${mins}m`;
  return <Pill kind={mins < 15 ? "bad" : "mut"}>{t("prop_expires_in")} {label}</Pill>;
}
