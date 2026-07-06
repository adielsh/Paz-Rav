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
}

export interface PayoffPoint {
  price: number;
  pnl: number;
}
