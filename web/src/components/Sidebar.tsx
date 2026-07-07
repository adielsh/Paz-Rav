import type { ReactNode } from "react";
import { IconBook, IconBox, IconClock, IconGauge, IconSitemap, IconX } from "./Icon";

export type ViewId = "dashboard" | "condor" | "dacs" | "insights" | "dacsGuide" | "how";

interface NavItem {
  id: ViewId;
  label: string;
  sub: string;
  icon: ReactNode;
}

const NAV: NavItem[] = [
  { id: "dashboard", label: "לוח מסחר", sub: "מבט-על ופוזיציות", icon: <IconGauge width={18} height={18} /> },
  { id: "condor", label: "Iron Condor", sub: "הצעות מכירת פרמיה", icon: <IconBox width={18} height={18} /> },
  { id: "dacs", label: "DACS 1.0", sub: "קלנדר דיאגונלי", icon: <IconClock width={18} height={18} /> },
  { id: "insights", label: "תובנות אסטרטגיה", sub: "רפלקציה על העסקאות", icon: <IconBrainSmall /> },
  { id: "dacsGuide", label: "מדריך DACS", sub: "האסטרטגיה שלב-שלב", icon: <IconBook width={18} height={18} /> },
  { id: "how", label: "איך המערכת בנויה", sub: "ארכיטקטורה ו-AI", icon: <IconSitemap width={18} height={18} /> },
];

// tiny inline brain (avoids a circular Icon import name clash with the panel)
function IconBrainSmall() {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M9.5 3A2.5 2.5 0 0 1 12 5.5v13a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.5-2.5 2.5 2.5 0 0 1-.5-3.5 2.5 2.5 0 0 1 .5-4 2.5 2.5 0 0 1 2-3.44A2.5 2.5 0 0 1 9.5 3Z" />
      <path d="M14.5 3A2.5 2.5 0 0 0 12 5.5v13a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.5-2.5 2.5 2.5 0 0 0 .5-3.5 2.5 2.5 0 0 0-.5-4 2.5 2.5 0 0 0-2-3.44A2.5 2.5 0 0 0 14.5 3Z" />
    </svg>
  );
}

function Logo() {
  return (
    <div className="flex items-center gap-3">
      <div className="relative shrink-0">
        <div className="absolute inset-0 rounded-2xl bg-primary/30 blur-lg" aria-hidden="true" />
        <div
          className="relative w-10 h-10 rounded-2xl grid place-items-center font-mono font-bold text-lg text-white shadow-elevated"
          style={{ background: "linear-gradient(150deg, #14B8A6, #0369A1)" }}
          aria-hidden="true"
        >
          P
        </div>
      </div>
      <div>
        <div className="font-bold tracking-tight leading-none text-ink">Paz Rav</div>
        <div className="text-2xs uppercase tracking-wider text-ink-3 font-mono mt-1">
          Options Engine
        </div>
      </div>
    </div>
  );
}

/** Left navigation rail. On desktop it's persistent; on mobile it slides in over a scrim
 * (controlled by `open`/`onClose`). Uses icon + label (never icon-only) and highlights the
 * active view — the two nav rules that matter most for discoverability. */
export default function Sidebar({
  view,
  onSelect,
  open,
  onClose,
}: {
  view: ViewId;
  onSelect: (v: ViewId) => void;
  open: boolean;
  onClose: () => void;
}) {
  const nav = (
    <nav className="flex flex-col gap-1.5" aria-label="ניווט ראשי">
      {NAV.map((item) => {
        const active = item.id === view;
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => {
              onSelect(item.id);
              onClose();
            }}
            aria-current={active ? "page" : undefined}
            className={`group flex items-center gap-3 rounded-xl px-3 py-2.5 text-right transition ${
              active
                ? "bg-primary/10 border border-primary/30 text-primary shadow-card"
                : "border border-transparent text-ink-2 hover:bg-panel2 hover:text-ink"
            }`}
          >
            <span
              className={`shrink-0 ${active ? "text-primary" : "text-ink-3 group-hover:text-ink-2"}`}
            >
              {item.icon}
            </span>
            <span className="flex-1 min-w-0">
              <span className="block text-[14px] font-semibold leading-tight">{item.label}</span>
              <span className="block text-[11px] text-ink-3 leading-tight mt-0.5 truncate">
                {item.sub}
              </span>
            </span>
          </button>
        );
      })}
    </nav>
  );

  return (
    <>
      {/* desktop rail */}
      <aside className="hidden lg:flex lg:flex-col w-64 shrink-0 gap-6 border-l border-line bg-panel/70 backdrop-blur px-4 py-6 sticky top-0 h-screen">
        <div className="px-1">
          <Logo />
        </div>
        {nav}
        <div className="mt-auto text-[10px] font-mono text-ink-3 px-1 leading-relaxed">
          Iron Condor · DACS 1.0
          <br />
          כל מספר דטרמיניסטי · AI רק שוקל
        </div>
      </aside>

      {/* mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-[90] lg:hidden" role="dialog" aria-modal="true" aria-label="תפריט">
          <div className="absolute inset-0 bg-[rgb(2_10_9_/_0.5)]" onClick={onClose} aria-hidden="true" />
          <aside className="animate-modal absolute right-0 top-0 h-full w-72 max-w-[85vw] border-l border-line bg-panel px-4 py-5 flex flex-col gap-6 shadow-elevated">
            <div className="flex items-center justify-between">
              <Logo />
              <button
                type="button"
                onClick={onClose}
                aria-label="סגור תפריט"
                className="inline-flex items-center justify-center w-8 h-8 rounded-lg text-ink-2 hover:text-ink hover:bg-panel2"
              >
                <IconX width={18} height={18} />
              </button>
            </div>
            {nav}
          </aside>
        </div>
      )}
    </>
  );
}
