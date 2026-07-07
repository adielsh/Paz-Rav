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

export interface AdviceStance {
  stance: "hold" | "close" | "reduce";
  confidence?: number | null;
  reasons: string[];
}

export interface CloseAdvice {
  decision: "hold" | "close" | "reduce";
  confidence?: number | null;
  rationale: string;
  analyst: AdviceStance;
  critic: AdviceStance;
  situation: Record<string, number | string | number[] | null>;
  engine: "llm" | "deterministic";
  orchestration?: "langgraph" | "sequential" | "deterministic";
  revisions?: number;
  recalled?: RecalledCase[];
  computed_at: string;
  error?: string;
}

export interface RecalledCase {
  summary: string;
  similarity: number;
  won: boolean;
  realized_pnl: number;
}

export interface Reflection {
  created_at?: string;
  sample_size: number;
  stats?: Record<string, unknown>;
  summary: string;
  recommendations: string[];
  engine?: "llm" | "deterministic";
  enough_data: boolean;
}

export interface Position {
  id: string;
  underlying: string;
  strategy: string;
  legs: Leg[];
  entry_credit: number;
  opened_at: string;
  status: "open" | "closed";
  alert: CloseReason | null;
  close_reason: CloseReason | null;
  closed_at: string | null;
  exit_credit: number | null;
  realized_pnl: number | null;
  unrealized_pnl?: number;
  meta?: Record<string, number | string>;
  langfuse_trace_id?: string | null;
}
