/**
 * Design tokens — single source of truth for colors used outside Tailwind classes
 * (Recharts SVG props, dynamic inline styles). MUST stay in sync with the literal
 * values in tailwind.config.js `theme.extend.colors` — Tailwind's config can't import
 * a TS module directly, so the palette is intentionally duplicated in exactly two
 * places, both commented with this note.
 */
export const colors = {
  bg: "#05070C",
  panel: "#0E121B",
  panel2: "#141A26",
  line: "#232B3A",
  lineStrong: "#2E3849",
  ink: "#EAEFF7",
  ink2: "#97A2B8",
  ink3: "#5C6579",
  accent: "#D9AE5B",
  good: "#34C795",
  bad: "#F0615A",
  warn: "#E8A23D",
  info: "#5B9EE8",
  ring: "#7DB0FF",
} as const;
