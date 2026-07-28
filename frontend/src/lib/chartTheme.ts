import { useAppSelector } from "../store/hooks";

// Recharts needs concrete color values (SVG attributes don't resolve CSS vars), so keep a
// per-theme palette here, mirrored from index.css. Tooltip uses an inline style, which DOES
// resolve CSS vars — see CHART_TIP.
const DARK = {
  grid: "#232d3d", axis: "#7b8aa0", blue: "#5c9bff",
  green: "#2fd97f", red: "#ff5a52", amber: "#f5b43c", violet: "#a98bff", cyan: "#3fd0e0",
  muted: "#7b8aa0", fg: "#eaf1fa",
};
const LIGHT = {
  grid: "#e4eaf3", axis: "#5d6f85", blue: "#2563eb",
  green: "#067647", red: "#d0342c", amber: "#b54708", violet: "#6941c6", cyan: "#0e7090",
  muted: "#5d6f85", fg: "#0d1725",
};

export const CHART_TIP = {
  background: "var(--panel)", border: "1px solid var(--line-strong)", borderRadius: 10,
  color: "var(--fg)", boxShadow: "var(--shadow-lg)", fontSize: 12, padding: "8px 10px",
};

export const CHART_TIP_LABEL = { color: "var(--muted)", fontWeight: 600, marginBottom: 4 };

export function useChartTheme() {
  return useAppSelector((s) => s.ui.theme) === "light" ? LIGHT : DARK;
}
