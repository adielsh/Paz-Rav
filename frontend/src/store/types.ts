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
