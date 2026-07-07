import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { paletteFor, type Palette, type ThemeName } from "./theme";

interface ThemeCtx {
  theme: ThemeName;
  colors: Palette;
  toggle: () => void;
  setTheme: (t: ThemeName) => void;
}

const Ctx = createContext<ThemeCtx | null>(null);
const STORAGE_KEY = "pazrav-theme";

/** Light by default (the user wants a bright app), but honour a saved choice or, on first
 * visit, the OS preference. The choice is applied to <html> as a `.dark` class so every
 * CSS-variable token flips at once. */
function initialTheme(): ThemeName {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "light" || saved === "dark") return saved;
    if (window.matchMedia?.("(prefers-color-scheme: dark)").matches) return "dark";
  } catch {
    /* localStorage/matchMedia unavailable — fall through to light */
  }
  return "light";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeName>(initialTheme);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", theme === "dark");
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      /* ignore persistence failures */
    }
  }, [theme]);

  const setTheme = useCallback((t: ThemeName) => setThemeState(t), []);
  const toggle = useCallback(() => setThemeState((t) => (t === "dark" ? "light" : "dark")), []);

  const value = useMemo<ThemeCtx>(
    () => ({ theme, colors: paletteFor(theme), toggle, setTheme }),
    [theme, toggle, setTheme],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useTheme(): ThemeCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}

/** Convenience: the concrete color palette for the active theme (Recharts / inline styles). */
export function useThemeColors(): Palette {
  return useTheme().colors;
}
