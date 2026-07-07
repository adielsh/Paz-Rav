import type { User } from "firebase/auth";
import { SignedInBar } from "../AuthGate";
import ThemeToggle from "./ThemeToggle";
import { IconMenu } from "./Icon";

function ConnectionBadge({ connected }: { connected: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs font-mono font-medium px-2.5 py-1.5 rounded-full border ${
        connected ? "border-good/35 text-good bg-good/10" : "border-bad/35 text-bad bg-bad/10"
      }`}
      role="status"
      aria-live="polite"
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${connected ? "bg-good" : "bg-bad animate-pulse-soft"}`}
      />
      <span className="hidden sm:inline">{connected ? "Live" : "Reconnecting…"}</span>
    </span>
  );
}

/** Sticky top bar: mobile menu button + page title on the right, live status / theme / user
 * on the left. One primary region for orientation, consistent across every page. */
export default function Topbar({
  title,
  subtitle,
  connected,
  user,
  onMenu,
}: {
  title: string;
  subtitle: string;
  connected: boolean;
  user: User | null;
  onMenu: () => void;
}) {
  return (
    <header className="sticky top-0 z-40 -mx-4 sm:-mx-6 px-4 sm:px-6 py-3 mb-6 bg-bg/80 backdrop-blur border-b border-line">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onMenu}
          aria-label="פתח תפריט"
          className="lg:hidden inline-flex items-center justify-center w-9 h-9 rounded-xl border border-line bg-panel text-ink-2 hover:text-ink"
        >
          <IconMenu width={18} height={18} />
        </button>
        <div className="min-w-0">
          <h1 className="text-lg sm:text-xl font-bold tracking-tight text-ink leading-none truncate">
            {title}
          </h1>
          <p className="text-2xs uppercase tracking-wider text-ink-3 font-mono mt-1 truncate">
            {subtitle}
          </p>
        </div>
        <div className="flex items-center gap-2.5 ml-auto">
          <ConnectionBadge connected={connected} />
          <ThemeToggle />
          {user && (
            <div className="hidden sm:block pr-1 border-r border-line">
              <span className="pr-2.5">
                <SignedInBar user={user} />
              </span>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
