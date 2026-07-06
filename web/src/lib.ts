import type { Candidate } from "./types";

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

export function strategyColor(name: string): string {
  return name === "iron_condor" ? "#d6a854" : "#6da3da";
}

export function shortStrikes(c: Candidate): string {
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

