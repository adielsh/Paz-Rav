export interface Feature {
  underlying: string;
  spot: number;
  iv_rank: number;
  term_slope: number;
  expected_move: number;
  regime: string;
  ts: string;
}

export interface Leg {
  side: "buy" | "sell";
  option_type: "call" | "put";
  strike: number;
  quantity: number;
  expiry?: string | null;
  iv?: number | null;
}

export interface Candidate {
  underlying: string;
  strategy: string;
  dte: number;
  legs: Leg[];
  credit: number;
  width: number;
  max_profit: number;
  max_loss: number;
  breakevens: number[];
  pop: number;
  score: number;
  meta?: Record<string, number | string>;
  u_idx?: number;
  verdict?: "take" | "caution" | "pass";
}

export interface PayoffPoint {
  price: number;
  pnl: number;
}

export interface Review {
  verdict?: "take" | "caution" | "pass";
  rationale?: string;
  objection?: string;
  explanation?: string;
  engine?: string;
  revisions?: number;
  context?: { regime: string; iv_rank: number; rsi: number | null };
}

export type CloseReason = "profit_target" | "stop_loss" | "time_stop" | "expired" | "manual";

export interface Position {
  id: string;
  underlying: string;
  strategy: string;
  legs: Leg[];
  entry_credit: number;
  opened_at: string;
  status: "open" | "closed";
  close_reason: CloseReason | null;
  closed_at: string | null;
  realized_pnl: number | null;
  unrealized_pnl?: number;
  meta?: Record<string, number | string>;
  langfuse_trace_id?: string | null;
}
