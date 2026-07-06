/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "media",
  theme: {
    extend: {
      colors: {
        ink: "#0c111a",
        panel: "#131a26",
        line: "#212c3c",
        accent: "#d6a854",
        good: "#4fb187",
        bad: "#e06e60",
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Cascadia Code", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
