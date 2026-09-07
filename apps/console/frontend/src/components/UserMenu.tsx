import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, useMeQuery } from "../store/api";
import { useAppDispatch } from "../store/hooks";
import { useT } from "../i18n/useT";

/** Initials from the display name, falling back to the email. */
function initials(name: string | null, email: string): string {
  const src = (name || email.split("@")[0] || "?").trim();
  const parts = src.split(/[\s._-]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || src[0].toUpperCase();
}

/** Who is signed in, and the way out. Sits in the header on every page. */
export default function UserMenu() {
  const { t } = useT();
  const nav = useNavigate();
  const dispatch = useAppDispatch();
  const { data: me } = useMeQuery();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", away); document.removeEventListener("keydown", esc); };
  });

  if (!me) return null;

  const signOut = async () => {
    await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
    // Drop every cached response — it belongs to the session that just ended.
    dispatch(api.util.resetApiState());
    window.location.replace("/");
  };

  const go = (path: string) => { setOpen(false); nav(path); };

  return (
    <div className="usermenu" ref={box}>
      <button className={`uavatar${open ? " on" : ""}`} onClick={() => setOpen(!open)}
        aria-haspopup="menu" aria-expanded={open} title={me.email}>
        <span className="ini">{initials(me.display_name, me.email)}</span>
        <span className="who">
          <b>{me.display_name || me.email.split("@")[0]}</b>
          <i>{me.role}</i>
        </span>
        <span className="caret" aria-hidden>▾</span>
      </button>

      {open && (
        <div className="upop" role="menu">
          <div className="uhead">
            <span className="ini big">{initials(me.display_name, me.email)}</span>
            <div>
              <b>{me.display_name || "—"}</b>
              <span className="mono ltr">{me.email}</span>
            </div>
          </div>

          <div className="ustatus">
            <span className={me.has_flex ? "ok" : "off"}>
              ● {me.has_flex ? t("um_flex_on") : t("um_flex_off")}
            </span>
          </div>

          <button role="menuitem" onClick={() => go("/settings")}>
            <span className="ic">⚙</span>{t("um_profile")}
          </button>
          <button role="menuitem" className="danger" onClick={signOut}>
            <span className="ic">⏻</span>{t("auth_signout")}
          </button>
        </div>
      )}
    </div>
  );
}
