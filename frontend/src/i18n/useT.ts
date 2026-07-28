import { useAppSelector } from "../store/hooks";
import { dict, type TKey } from "./translations";

// Translation hook: t(key) resolves against the current Redux language.
export function useT() {
  const lang = useAppSelector((s) => s.ui.lang);
  const table = dict[lang];
  const t = (k: TKey) => table[k] ?? dict.en[k] ?? k;
  return { t, lang, rtl: lang === "he" };
}
