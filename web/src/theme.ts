/**
 * Concrete color values for the few places that can't use Tailwind classes — Recharts SVG
 * props and dynamic inline styles. These MUST stay in sync with the CSS-variable channels in
 * src/index.css (and the Tailwind mapping in tailwind.config.js). Light + dark are kept as
 * separate palettes so charts/rails read correctly in both themes via useThemeColors().
 */
export interface Palette {
  bg: string;
  panel: string;
  panel2: string;
  line: string;
  lineStrong: string;
  ink: string;
  ink2: string;
  ink3: string;
  primary: string;
  accent: string;
  good: string;
  bad: string;
  warn: string;
  info: string;
  ring: string;
}

export const lightColors: Palette = {
  bg: "#F4FAF9",
  panel: "#FFFFFF",
  panel2: "#F0F7F6",
  line: "#E0EAE8",
  lineStrong: "#CAD9D6",
  ink: "#0F2A28",
  ink2: "#4A5F5C",
  ink3: "#7C8D8A",
  primary: "#0D9488",
  accent: "#0369A1",
  good: "#0D945E",
  bad: "#DC2626",
  warn: "#B0760B",
  info: "#0369A1",
  ring: "#0D9488",
};

export const darkColors: Palette = {
  bg: "#061210",
  panel: "#0E1C1A",
  panel2: "#142523",
  line: "#23322F",
  lineStrong: "#2E403C",
  ink: "#EAF4F2",
  ink2: "#9DB3AF",
  ink3: "#5F736F",
  primary: "#2DD4BF",
  accent: "#38BDF8",
  good: "#34D399",
  bad: "#F87171",
  warn: "#FBBF24",
  info: "#38BDF8",
  ring: "#2DD4BF",
};

/** Backwards-compatible default (light). Prefer useThemeColors() in components so charts
 * and inline-styled colors follow the active theme. */
export const colors: Palette = lightColors;

export type ThemeName = "light" | "dark";
export const paletteFor = (t: ThemeName): Palette => (t === "dark" ? darkColors : lightColors);
