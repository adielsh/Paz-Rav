import { colors } from "./theme";
import type { Candidate, Leg } from "./types";

export function strategyLabel(name: string): string {
  switch (name) {
    case "iron_condor":
      return "Iron Condor";
    case "dacs":
      return "DACS 1.0";
    default:
      return name;
  }
}

// Each strategy gets its own hue so the two never get confused at a glance — condor
// keeps the brand gold (its "home" identity), DACS uses info-blue. Verdict tiers
// (take/caution/pass) use a separate good/warn/bad scale so a strategy's identity color
// and the committee's judgment are never the same hue.
export function strategyColor(name: string): string {
  return name === "iron_condor" ? colors.accent : colors.info;
}

export function shortStrikes(c: { legs: Leg[] }): string {
  const s = c.legs
    .filter((l) => l.side === "sell")
    .map((l) => l.strike)
    .sort((a, b) => a - b);
  return s.join(" / ");
}

export function num(meta: Candidate["meta"], key: string): number | undefined {
  const v = meta?.[key];
  return typeof v === "number" ? v : undefined;
}

export function frontExpiry(c: Candidate): string {
  const dates = c.legs.map((l) => l.expiry).filter((e): e is string => !!e).sort();
  return dates[0] ?? `${c.dte}d`;
}

export function closeReasonLabel(reason: string | null): string {
  switch (reason) {
    case "profit_target":
      return "יעד רווח";
    case "stop_loss":
      return "סטופ";
    case "time_stop":
      return "עצירת זמן";
    case "expired":
      return "פקיעה";
    case "manual":
      return "ידני";
    default:
      return reason ?? "";
  }
}

