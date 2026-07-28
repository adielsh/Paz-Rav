import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

// Classic Redux state (beyond RTK Query's server cache): client-side view preferences and filters.
export type TradeStatusFilter = "all" | "open" | "closed" | "stopped" | "expired";
export type GateFilter = "all" | "pass" | "reject";
export type Lang = "en" | "he";
export type Mode = "demo" | "real";
export type Theme = "dark" | "light";

interface UiState {
  tradeStatus: TradeStatusFilter;
  gateFilter: GateFilter;
  autoRefresh: boolean;
  lang: Lang;
  mode: Mode;
  theme: Theme;
}

const ls = (k: string) => (typeof localStorage !== "undefined" ? localStorage.getItem(k) : null);

// No stored preference → follow the OS. An explicit choice always wins afterwards.
const systemTheme = (): Theme =>
  typeof matchMedia !== "undefined" && matchMedia("(prefers-color-scheme: light)").matches
    ? "light" : "dark";

const initialState: UiState = {
  tradeStatus: "all", gateFilter: "all", autoRefresh: true,
  lang: (ls("lang") as Lang) ?? "en", mode: (ls("mode") as Mode) ?? "demo",
  theme: (ls("theme") as Theme) ?? systemTheme(),
};

const uiSlice = createSlice({
  name: "ui",
  initialState,
  reducers: {
    setTradeStatus: (s, a: PayloadAction<TradeStatusFilter>) => { s.tradeStatus = a.payload; },
    setGateFilter: (s, a: PayloadAction<GateFilter>) => { s.gateFilter = a.payload; },
    toggleAutoRefresh: (s) => { s.autoRefresh = !s.autoRefresh; },
    setLang: (s, a: PayloadAction<Lang>) => { s.lang = a.payload; },
    toggleLang: (s) => { s.lang = s.lang === "en" ? "he" : "en"; },
    setMode: (s, a: PayloadAction<Mode>) => { s.mode = a.payload; },
    setTheme: (s, a: PayloadAction<Theme>) => { s.theme = a.payload; },
    toggleTheme: (s) => { s.theme = s.theme === "dark" ? "light" : "dark"; },
  },
});

export const { setTradeStatus, setGateFilter, toggleAutoRefresh, setLang, toggleLang,
  setMode, setTheme, toggleTheme } = uiSlice.actions;
export default uiSlice.reducer;
