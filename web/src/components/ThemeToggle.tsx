import { useTheme } from "../theme-context";
import { IconMoon, IconSun } from "./Icon";

/** Light/dark switch — a pill that shows the icon of the theme you'd switch TO. */
export default function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const toDark = theme === "light";
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={toDark ? "עבור למצב כהה" : "עבור למצב בהיר"}
      title={toDark ? "מצב כהה" : "מצב בהיר"}
      className="inline-flex items-center justify-center w-9 h-9 rounded-xl border border-line bg-panel text-ink-2 hover:text-ink hover:border-lineStrong shadow-card"
    >
      {toDark ? <IconMoon width={17} height={17} /> : <IconSun width={17} height={17} />}
    </button>
  );
}
