import { useEffect, useState } from "react";
import { useT } from "../i18n/useT";
import { useAppDispatch } from "../store/hooks";
import { toggleLang } from "../store/uiSlice";
import { api } from "../store/api";

/**
 * Sign-in / first-run setup.
 *
 * The very first account created becomes the owner; after that, whether new accounts can be
 * opened is a server decision (ALLOW_SIGNUP), so this screen asks the server rather than
 * guessing.
 */
export default function Login() {
  const { t, lang } = useT();
  const dispatch = useAppDispatch();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [firstRun, setFirstRun] = useState(false);
  const [signupOpen, setSignupOpen] = useState(true);

  useEffect(() => {
    fetch("/api/auth/status", { credentials: "include" })
      .then((r) => r.json())
      .then((s) => {
        setFirstRun(s.users === 0);
        setSignupOpen(!!s.signup_open);
        if (s.users === 0) setMode("register");
      })
      .catch(() => { /* server unreachable — the submit will report it */ });
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null); setBusy(true);
    try {
      const r = await fetch(`/api/auth/${mode}`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(mode === "register"
          ? { email, password, display_name: name || null }
          : { email, password }),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        const detail = body?.detail;
        setErr(typeof detail === "string" ? detail
          : Array.isArray(detail) ? detail[0]?.msg ?? t("auth_failed") : t("auth_failed"));
        return;
      }
      // Everything cached under the previous session belongs to a different user.
      dispatch(api.util.resetApiState());
      window.location.replace("/");
    } catch {
      setErr(t("auth_unreachable"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="loginwrap">
      <button className="langbtn loginlang" onClick={() => dispatch(toggleLang())}>
        {t("lang_button")}
      </button>

      <form className="logincard" onSubmit={submit}>
        <div className="brand">
          <span className="dot" />
          <div><b>SPX Condor</b><span>ops console</span></div>
        </div>

        <h1>{firstRun ? t("auth_setup_title") : mode === "login" ? t("auth_signin") : t("auth_create")}</h1>
        <p className="lead">
          {firstRun ? t("auth_setup_lead")
            : mode === "login" ? t("auth_signin_lead") : t("auth_create_lead")}
        </p>

        {mode === "register" && (
          <label>
            <span>{t("auth_name")}</span>
            <input className="input" value={name} autoComplete="name"
              onChange={(e) => setName(e.target.value)} placeholder={t("auth_name_ph")} />
          </label>
        )}

        <label>
          <span>{t("auth_email")}</span>
          <input className="input" type="email" required value={email} autoComplete="email"
            dir="ltr" onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
        </label>

        <label>
          <span>{t("auth_password")}</span>
          <input className="input" type="password" required value={password} dir="ltr"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={mode === "register" ? t("auth_password_rule") : ""} />
        </label>

        {err && <div className="loginerr">{err}</div>}

        <button className="primary loginbtn" type="submit" disabled={busy}>
          {busy ? t("auth_working")
            : mode === "login" ? t("auth_signin") : t("auth_create")}
        </button>

        {!firstRun && signupOpen && (
          <button type="button" className="link loginswap"
            onClick={() => { setMode(mode === "login" ? "register" : "login"); setErr(null); }}>
            {mode === "login" ? t("auth_need_account") : t("auth_have_account")}
          </button>
        )}

        <p className="loginfoot" dir={lang === "he" ? "rtl" : "ltr"}>{t("auth_privacy")}</p>
      </form>
    </div>
  );
}
