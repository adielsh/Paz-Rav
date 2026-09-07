export interface Trade {
  id: number; created_at: string; expiry: string; dte: number; vix_avg: number;
  put_short_strike: number; put_long_strike: number; call_short_strike: number; call_long_strike: number;
  target_put_delta: number; target_call_delta: number; entry_credit: number; quantity: number;
  status: string; ib_perm_id: number | null; leg_conids: number[] | null; closed_at: string | null;
  realized?: number | null;
}
export interface GateDecision {
  id: number; created_at: string; vix: number | null; accepted: boolean; reason: string;
  details: Record<string, unknown> | null;
}
export type ProposalStatus =
  "pending" | "approved" | "rejected" | "placed" | "failed" | "expired";

export interface TradeProposal {
  id: number; created_at: string; status: ProposalStatus;
  expiry: string; dte: number; vix_avg: number;
  put_short_strike: number; put_long_strike: number;
  call_short_strike: number; call_long_strike: number;
  target_put_delta: number; target_call_delta: number; quantity: number;
  combo_bid: number | null; combo_ask: number | null;
  combo_mid: number | null; combo_spread: number | null;
  leg_conids: number[] | null; gate_details: Record<string, unknown> | null;
  expires_at: string | null; decided_at: string | null;
  decided_by: string | null; note: string | null;
  trade_id: number | null; error: string | null; placed_credit: number | null;
}

export interface Control {
  id: number; trading_enabled: boolean; notes: string | null; updated_by: string | null; updated_at: string;
  // false when this account has no daemon of its own (see GET /control).
  available?: boolean;
}
export interface PnlSummary { total: number; closed: number; }
export interface PnlPoint { computed_at: string; realized: number; }

export interface IbStatus { connected: boolean; account: string | null; host: string; port: number; }
export interface IbAccount { connected: boolean; account?: string; summary: Record<string, string>; }
export interface IbPosition {
  account: string; symbol: string; secType: string; right: string; strike: number | null;
  expiry: string; tradingClass: string; position: number; avgCost: number;
}
export interface IbExecution {
  time: string | null; symbol: string; secType: string; right: string; strike: number | null;
  expiry: string; side: string; shares: number; price: number; permId: number; orderId: number;
  commission: number | null; realizedPNL: number | null;
}
export interface IbOrder {
  permId: number; action: string; orderType: string; tif: string; lmtPrice: number;
  totalQuantity: number; symbol: string; secType: string; status: string; filled: number;
  remaining: number; avgFillPrice: number;
}
export interface IbOrders { connected: boolean; open: IbOrder[]; completed: IbOrder[]; }
export interface IbList<T> { connected: boolean; items: T[]; }

export interface FlexTrade {
  date: string; dateTime: string; symbol: string; underlying: string; assetCategory: string;
  putCall: string; strike: number | null; expiry: string; buySell: string; quantity: number | null;
  price: number | null; proceeds: number | null; commission: number | null;
  realized: number | null; description: string;
  openClose?: string; orderId?: string; orderRef?: string; level?: string;
}
export interface FlexNav { start: number; end: number; realized: number; mtm: number;
  deposits: number; commissions: number; }
/** One IBKR ChangeInNAV block = one trading day. `date` is yyyymmdd. */
export interface FlexNavDay {
  date: string; start: number; end: number;
  deposits: number; mtm: number; commissions: number;
}
export interface FlexData {
  configured: boolean; ok?: boolean; error?: string; account?: string;
  from?: string; to?: string; nav?: FlexNav | null; navDays?: FlexNavDay[];
  trades: FlexTrade[];
}

export interface IbPnl {
  connected: boolean; net_liq?: number | null; daily?: number | null;
  unrealized?: number | null; realized?: number | null; account?: string;
}
export interface NavPoint { ts: string; net_liq: number | null; daily_pnl: number | null; unrealized: number | null; }
export interface IbNavSeries { connected: boolean; live: IbPnl; series: NavPoint[]; }

/* ---------------------------------------------------------------------------
 * The Paz Rav strategy engine (src/paz_rav/), reached through /api/engine/*.
 *
 * Advisory only: the engine ranks candidates, it never places an order. These
 * mirror src/paz_rav/store/serialize.py::candidate_to_dict plus the two keys
 * /api/top adds on top of it (u_idx, verdict).
 *
 * Every engine response carries `available` — stamped by the proxy, false when
 * the engine is down. Branch on it before reading anything else.
 * ------------------------------------------------------------------------ */

export interface EngineOffline { available: false; error: string }

export interface EngineHealth {
  available: true;
  status: string;
  version: string;
  underlyings: string[];
  strategies: string[];
  /** "yfinance" = ~15-min delayed. "fixture" = the offline sample chain. */
  data_source: string;
}

export interface EngineLeg {
  side: "buy" | "sell";
  option_type: "call" | "put";
  strike: number;
  quantity: number;
  /** Set only by multi-expiry structures (DACS); null means the structure's own expiry. */
  expiry?: string | null;
  iv?: number | null;
  delta?: number | null;
}

/** Every dollar figure here is PER SHARE. A US contract is x100 — see usdContract(). */
export interface EngineCandidate {
  underlying: string;
  strategy: string;
  dte: number;
  legs: EngineLeg[];
  credit: number;
  width: number;
  max_profit: number;
  max_loss: number;
  breakevens: number[];
  /** Probability of profit, 0..1. */
  pop: number;
  score: number;
  meta?: Record<string, number | string>;
  /** Rank within its own underlying — the handle for /engine/payoff and /engine/explain. */
  u_idx?: number;
  /** The deterministic committee's call. "pass" is filtered out server-side. */
  verdict?: "take" | "caution";
}

export interface EngineTopGroup { strategy: string; trades: EngineCandidate[] }
export interface EngineTopOk { available: true; groups: EngineTopGroup[] }
export type EngineTop = EngineTopOk | EngineOffline;
export type EngineHealthResp = EngineHealth | EngineOffline;
