/** @type {import('tailwindcss').Config} */
// Color values must stay in sync with src/theme.ts (see the note there) — Tailwind's
// config loader can't import the TS module directly, so it's duplicated deliberately.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "media",
  theme: {
    extend: {
      colors: {
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
      },
      fontFamily: {
        sans: ["IBM Plex Sans", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Cascadia Code", "Consolas", "monospace"],
      },
      fontSize: {
        "2xs": ["10px", { lineHeight: "14px", letterSpacing: "0.03em" }],
      },
      boxShadow: {
        elevated: "0 4px 24px -6px rgba(0,0,0,0.45), 0 1px 2px rgba(0,0,0,0.3)",
        focus: "0 0 0 3px rgba(125,176,255,0.35)",
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
