import type { Candidate } from "../types";

function shorts(c: Candidate): string {
  const s = c.legs
    .filter((l) => l.side === "sell")
    .map((l) => l.strike)
    .sort((a, b) => a - b);
  return `${s[0]} / ${s[1]}`;
}

export default function CandidatesTable({
  candidates,
  selectedIdx,
  onSelect,
}: {
  candidates: Candidate[];
  selectedIdx: number;
  onSelect: (i: number) => void;
}) {
  if (candidates.length === 0) {
    return <div className="text-slate-500 text-sm">No candidates passed the filters.</div>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="text-left text-[10px] uppercase tracking-wider text-slate-400 font-mono">
            <th className="py-2 pr-3">#</th>
            <th className="py-2 pr-3">short put / call</th>
            <th className="py-2 pr-3 text-right">width</th>
            <th className="py-2 pr-3 text-right">credit</th>
            <th className="py-2 pr-3 text-right">max loss</th>
            <th className="py-2 pr-3 text-right">POP</th>
            <th className="py-2 pr-3 text-right">score</th>
          </tr>
        </thead>
        <tbody className="font-mono tabular-nums">
          {candidates.map((c, i) => (
            <tr
              key={i}
              onClick={() => onSelect(i)}
              className={`cursor-pointer border-t border-line/60 ${
                i === selectedIdx ? "bg-accent/10" : "hover:bg-white/5"
              }`}
            >
              <td className="py-2 pr-3 text-slate-500">{i + 1}</td>
              <td className="py-2 pr-3">{shorts(c)}</td>
              <td className="py-2 pr-3 text-right">{c.width.toFixed(0)}</td>
              <td className="py-2 pr-3 text-right text-good">{c.credit.toFixed(2)}</td>
              <td className="py-2 pr-3 text-right text-bad">{c.max_loss.toFixed(2)}</td>
              <td className="py-2 pr-3 text-right">{(c.pop * 100).toFixed(1)}%</td>
              <td className="py-2 pr-3 text-right text-accent">{c.score.toFixed(4)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
