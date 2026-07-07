/** @type {import('tailwindcss').Config} */
// Colors are driven by CSS variables (space-separated RGB channels) defined in src/index.css,
// so Tailwind's `/<alpha-value>` opacity modifiers work AND the light/dark toggle flips every
// token at once. theme.ts mirrors the concrete hex values for the few inline (Recharts) uses.
const withAlpha = (v) => `rgb(var(--${v}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: withAlpha("bg"),
        panel: withAlpha("panel"),
        panel2: withAlpha("panel-2"),
        line: withAlpha("line"),
        lineStrong: withAlpha("line-strong"),
        ink: withAlpha("ink"),
        "ink-2": withAlpha("ink-2"),
        "ink-3": withAlpha("ink-3"),
        primary: withAlpha("primary"),
        accent: withAlpha("accent"),
        good: withAlpha("good"),
        bad: withAlpha("bad"),
        warn: withAlpha("warn"),
        info: withAlpha("info"),
        ring: withAlpha("ring"),
      },
      fontFamily: {
        sans: ["IBM Plex Sans", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Cascadia Code", "Consolas", "monospace"],
      },
      fontSize: {
        "2xs": ["10px", { lineHeight: "14px", letterSpacing: "0.03em" }],
      },
      boxShadow: {
        card: "0 1px 2px rgb(15 42 40 / 0.04), 0 6px 24px -8px rgb(15 42 40 / 0.10)",
        elevated: "0 4px 24px -6px rgb(15 42 40 / 0.18), 0 1px 2px rgb(15 42 40 / 0.08)",
        focus: "0 0 0 3px rgb(var(--ring) / 0.35)",
      },
      keyframes: {
        pulseSoft: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.45" },
        },
      },
      animation: {
        "pulse-soft": "pulseSoft 1.8s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
