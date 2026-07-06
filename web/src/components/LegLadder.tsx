import type { Leg } from "../types";

/** One clear, scannable row showing every leg — the direct fix for "not clear what each
 * leg's strike is": color-coded by side (red=sell, green=buy), action spelled out in
 * Hebrew, type and strike prominent. No clicking required to see the full structure. */
export default function LegLadder({ legs, compact }: { legs: Leg[]; compact?: boolean }) {
  return (
    <div className={`flex flex-wrap gap-2 ${compact ? "" : "my-2"}`}>
      {legs.map((leg, i) => {
        const sell = leg.side === "sell";
        return (
          <span
            key={i}
            className={`inline-flex items-center gap-1.5 text-xs font-mono px-2.5 py-1.5 rounded-lg border ${
              sell ? "border-bad/35 bg-bad/10 text-bad" : "border-good/35 bg-good/10 text-good"
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full shrink-0 ${sell ? "bg-bad" : "bg-good"}`}
              aria-hidden="true"
            />
            <span className="font-semibold">{sell ? "מכר" : "קנה"}</span>
            <span className="uppercase text-ink-2">{leg.option_type}</span>
            <span className="text-ink font-semibold tabular-nums">{leg.strike}</span>
          </span>
        );
      })}
    </div>
  );
}
