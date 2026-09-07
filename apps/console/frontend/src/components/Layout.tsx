import { useEffect } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useIbStatusQuery, useProposalsQuery } from "../store/api";
import { useAppDispatch, useAppSelector } from "../store/hooks";
import { toggleLang, setMode, toggleTheme, type Mode } from "../store/uiSlice";
import { useT } from "../i18n/useT";
import type { TKey } from "../i18n/translations";
import KillSwitch from "./KillSwitch";
import UserMenu from "./UserMenu";
import ChatBot from "./ChatBot";

type NavItem = { to: string; key: TKey; ic: string; end?: boolean };
// One menu for both modes: the sidebar is navigation, not a mode-dependent surface. Hiding
// items in "real" mode meant switching modes silently moved the goalposts.
const NAV: NavItem[] = [
  { to: "/overview", key: "nav_overview", ic: "◧" },
  { to: "/real", key: "nav_real", ic: "◪" },
  // The strategy engine sits before approvals because that is the order of the work:
  // an idea is found, then a trade is approved. It feeds nothing automatically yet.
  { to: "/ideas", key: "nav_ideas", ic: "◆" },
  { to: "/approvals", key: "nav_proposals", ic: "✓" },
  { to: "/analytics", key: "nav_analytics", ic: "▤" },
  { to: "/account", key: "nav_account", ic: "◈" },
  { to: "/positions", key: "nav_positions", ic: "▣" },
  { to: "/trades", key: "nav_trades", ic: "≣" },
  { to: "/gates", key: "nav_gates", ic: "⚑" },
  { to: "/settings", key: "nav_settings", ic: "⚙" },
];
const DEFAULT_ROUTE: Record<Mode, string> = { real: "/real", demo: "/overview" };

const TITLE: Record<string, TKey> = {
  "/overview": "title_overview", "/real": "title_real", "/analytics": "title_analytics",
  "/account": "title_account", "/positions": "title_positions",
  "/trades": "title_trades", "/gates": "title_gates", "/approvals": "title_proposals",
  "/ideas": "title_ideas",
  "/settings": "title_settings",
};

/* Inline so the icons never depend on a symbol font being installed. */
const SunIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" aria-hidden>
    <circle cx="12" cy="12" r="4.2" />
    <path d="M12 2v2.4M12 19.6V22M22 12h-2.4M4.4 12H2M18.4 5.6l-1.7 1.7M7.3 16.7l-1.7 1.7M18.4 18.4l-1.7-1.7M7.3 7.3 5.6 5.6" />
  </svg>
);
const MoonIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d="M20.5 14.6A8.6 8.6 0 0 1 9.4 3.5a8.6 8.6 0 1 0 11.1 11.1Z" />
  </svg>
);

export default function Layout() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { t } = useT();
  const dispatch = useAppDispatch();
  const mode = useAppSelector((s) => s.ui.mode);
  const theme = useAppSelector((s) => s.ui.theme);
  const { data: ib } = useIbStatusQuery(undefined, { pollingInterval: 20000 });
  const { data: proposals } = useProposalsQuery(100, { pollingInterval: 15000 });
  const awaiting = (proposals ?? []).filter((p) => p.status === "pending").length;

  const switchMode = (m: Mode) => {
    dispatch(setMode(m));
    try { localStorage.setItem("mode", m); } catch { /* ignore */ }
    navigate(DEFAULT_ROUTE[m]);
  };

  // The URL is authoritative: keep the mode in sync with the current route (so deep links work).
  useEffect(() => {
    const shouldBe: Mode = pathname === "/real" ? "real" : "demo";
    if (mode !== shouldBe) {
      dispatch(setMode(shouldBe));
      try { localStorage.setItem("mode", shouldBe); } catch { /* ignore */ }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="dot" />
          <div><b>SPX Condor</b><span>ops console</span></div>
        </div>
        <nav className="nav">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end}
              className={({ isActive }) => (isActive ? "active" : "")}>
              <span className="ic">{n.ic}</span>{t(n.key)}
              {n.to === "/approvals" && awaiting > 0 && <span className="badge">{awaiting}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="spacer" />
        <div className="foot">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span>{t("gateway")}</span>
            {ib?.connected ? <span className="online">● {t("connected")}</span>
                           : <span className="offline">● {t("offline")}</span>}
          </div>
          <div className="acct">{ib?.account ?? "paper"}</div>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div>
            <h1>{t(TITLE[pathname] ?? "title_overview")}</h1>
            <div className="sub">{t("subtitle")}</div>
          </div>
          <div className="row">
            <div className="seg modeswitch">
              <button className={mode === "demo" ? "on" : ""} onClick={() => switchMode("demo")}>{t("mode_demo")}</button>
              <button className={mode === "real" ? "on" : ""} onClick={() => switchMode("real")}>{t("mode_real")}</button>
            </div>
            <button className="iconbtn" onClick={() => dispatch(toggleTheme())}
              title={theme === "dark" ? t("theme_light") : t("theme_dark")}
              aria-label={theme === "dark" ? t("theme_light") : t("theme_dark")}>
              {theme === "dark" ? <SunIcon /> : <MoonIcon />}</button>
            <button className="langbtn" onClick={() => dispatch(toggleLang())}>{t("lang_button")}</button>
            <KillSwitch />
            <UserMenu />
          </div>
        </header>
        <div className="content"><Outlet /></div>
      </div>
      {/* Floats above every routed page — the question is usually about what is on screen. */}
      <ChatBot />
    </div>
  );
}
