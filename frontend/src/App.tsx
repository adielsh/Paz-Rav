import { useEffect } from "react";
import { Routes, Route } from "react-router-dom";
import { useAppSelector } from "./store/hooks";
import { useMeQuery } from "./store/api";
import Layout from "./components/Layout";
import Overview from "./pages/Overview";
import Positions from "./pages/Positions";
import Trades from "./pages/Trades";
import Gates from "./pages/Gates";
import Account from "./pages/Account";
import Analytics from "./pages/Analytics";
import RealAccount from "./pages/RealAccount";
import Proposals from "./pages/Proposals";
import Login from "./pages/Login";
import Settings from "./pages/Settings";

export default function App() {
  const lang = useAppSelector((s) => s.ui.lang);
  const theme = useAppSelector((s) => s.ui.theme);
  // Drive document direction + lang from Redux; persist the choice.
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "he" ? "rtl" : "ltr";
    try { localStorage.setItem("lang", lang); } catch { /* ignore */ }
  }, [lang]);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("theme", theme); } catch { /* ignore */ }
  }, [theme]);

  // One gate for the whole app: until /auth/me succeeds nothing else is rendered, so no
  // page can flash another user's cached data before the session is known.
  const { data: me, isLoading, isError } = useMeQuery();
  if (isLoading) return <div className="bootwait">…</div>;
  if (isError || !me) return <Login />;

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Overview />} />
        <Route path="approvals" element={<Proposals />} />
        <Route path="settings" element={<Settings />} />
        <Route path="real" element={<RealAccount />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="positions" element={<Positions />} />
        <Route path="trades" element={<Trades />} />
        <Route path="gates" element={<Gates />} />
        <Route path="account" element={<Account />} />
      </Route>
    </Routes>
  );
}
