import { colors, type Palette } from "./theme";
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

// Each strategy gets its own hue so the two never get confused at a glance — condor takes
// the brand teal (primary), DACS the accent blue. Pass the active theme's palette so the
// hue reads correctly in both light and dark; falls back to the light palette if omitted.
export function strategyColor(name: string, palette: Palette = colors): string {
  return name === "iron_condor" ? palette.primary : palette.accent;
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

