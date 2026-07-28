import { useEffect, useState } from "react";
import { useT } from "../i18n/useT";
import { useAppDispatch } from "../store/hooks";
import { toggleLang } from "../store/uiSlice";
import { api } from "../store/api";

/**
 * Sign-in / first-run setup.
 *
 * Split layout: the strategy's own payoff profile on the left, the form on the right. The
 * first account created becomes the owner; whether further accounts can be opened is a
 * server decision (ALLOW_SIGNUP), so this screen asks rather than guessing.
 */
export default function Login() {
  const { t } = useT();
  const dispatch = useAppDispatch();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [reveal, setReveal] = useState(false);
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
        const d = body?.detail;
        setErr(typeof d === "string" ? d
          : Array.isArray(d) ? d[0]?.msg ?? t("auth_failed") : t("auth_failed"));
        return;
      }
      // Anything cached under a previous session belongs to a different user.
      dispatch(api.util.resetApiState());
      window.location.replace("/");
    } catch {
      setErr(t("auth_unreachable"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth">
      {/* ---------------------------------------------------------- brand -- */}
      <section className="auth-brand">
        <div className="auth-glow" aria-hidden />
        <header className="auth-mark">
          <span className="dot" />
          <span className="wm">SPX&nbsp;Condor</span>
        </header>

        <div className="auth-pitch">
          <h1>{t("auth_pitch_1")}<br /><em>{t("auth_pitch_2")}</em></h1>
          <p className="auth-sub">{t("auth_sub_1")}<br />{t("auth_sub_2")}</p>
        </div>

        <Payoff />

        <footer className="auth-specs">
          <span className="lbl">{t("auth_specs")}</span>
          <ul>
            <li><b>40</b><i>DTE</i></li>
            <li><b>Δ.30/.20</b><i>{t("auth_spec_delta")}</i></li>
            <li><b>50</b><i>{t("auth_spec_wing")}</i></li>
            <li><b>25</b><i>{t("auth_spec_stop")}</i></li>
          </ul>
        </footer>
      </section>

      {/* ----------------------------------------------------------- form -- */}
      <section className="auth-panel">
        <button className="langbtn auth-lang" onClick={() => dispatch(toggleLang())}>
          {t("lang_button")}
        </button>

        <form className="auth-form" onSubmit={submit}>
          {firstRun ? (
            <div className="auth-first">
              <h2>{t("auth_setup_title")}</h2>
              <p>{t("auth_setup_lead")}</p>
            </div>
          ) : (
            <div className="auth-tabs" role="tablist">
              <button type="button" role="tab" aria-selected={mode === "login"}
                className={mode === "login" ? "on" : ""}
                onClick={() => { setMode("login"); setErr(null); }}>
                {t("auth_signin")}
              </button>
              {signupOpen && (
                <button type="button" role="tab" aria-selected={mode === "register"}
                  className={mode === "register" ? "on" : ""}
                  onClick={() => { setMode("register"); setErr(null); }}>
                  {t("auth_create")}
                </button>
              )}
            </div>
          )}

          {mode === "register" && (
            <label className="auth-field">
              <span>{t("auth_name")}</span>
              <input value={name} autoComplete="name"
                onChange={(e) => setName(e.target.value)} placeholder={t("auth_name_ph")} />
            </label>
          )}

          <label className="auth-field">
            <span>{t("auth_email")}</span>
            <input type="email" required value={email} autoComplete="email" dir="ltr"
              onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
          </label>

          <label className="auth-field">
            <span>{t("auth_password")}</span>
            <div className="auth-pw">
              <input type={reveal ? "text" : "password"} required value={password} dir="ltr"
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={mode === "register" ? t("auth_password_rule") : ""} />
              <button type="button" onClick={() => setReveal(!reveal)}
                aria-label={reveal ? t("auth_hide") : t("auth_show")}>
                {reveal ? <EyeOff /> : <Eye />}
              </button>
            </div>
          </label>

          {err && <div className="auth-err" role="alert">{err}</div>}

          <button className="auth-go" type="submit" disabled={busy}>
            {busy ? t("auth_working") : mode === "login" ? t("auth_signin") : t("auth_create")}
          </button>

          <p className="auth-note">{t("auth_privacy")}</p>
        </form>
      </section>
    </div>
  );
}

/* --------------------------------------------------------------- payoff -- */

/**
 * The strategy's payoff profile at expiry, drawn from the real structure rather than
 * sketched: flat max profit between the short strikes, sloping through each spread, capped
 * loss beyond the long wings. It is the most characteristic shape in this product's world,
 * so it earns the hero slot.
 */
function Payoff() {
  const W = 560, H = 190, zero = 118;          // baseline y
  const [pl, ps, cs, cl] = [90, 190, 370, 470]; // strike x positions
  const top = 74;                               // y of max profit
  const bot = 176;                              // y of max loss
  const line = `M0,${bot} L${pl},${bot} L${ps},${top} L${cs},${top} L${cl},${bot} L${W},${bot}`;

  return (
    <div className="auth-payoff" aria-hidden>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
        <defs>
          <linearGradient id="pf-win" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--profit)" stopOpacity=".38" />
            <stop offset="100%" stopColor="var(--profit)" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="pf-lose" x1="0" y1="1" x2="0" y2="0">
            <stop offset="0%" stopColor="var(--loss)" stopOpacity=".30" />
            <stop offset="100%" stopColor="var(--loss)" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="pf-stroke" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="var(--loss)" />
            <stop offset="22%" stopColor="var(--loss)" />
            <stop offset="36%" stopColor="var(--profit)" />
            <stop offset="64%" stopColor="var(--profit)" />
            <stop offset="78%" stopColor="var(--loss)" />
            <stop offset="100%" stopColor="var(--loss)" />
          </linearGradient>
        </defs>

        {/* profit area sits above the baseline, loss below — the sign is the geometry */}
        <path d={`M${pl},${zero} L${ps},${top} L${cs},${top} L${cl},${zero} Z`} fill="url(#pf-win)" />
        <path d={`M0,${zero} L0,${bot} L${pl},${bot} L${pl},${zero} Z`} fill="url(#pf-lose)" />
        <path d={`M${cl},${zero} L${cl},${bot} L${W},${bot} L${W},${zero} Z`} fill="url(#pf-lose)" />

        <line className="pf-zero" x1="0" y1={zero} x2={W} y2={zero} />
        {[pl, ps, cs, cl].map((x, i) => (
          <line key={i} className={`pf-strike ${i === 1 || i === 2 ? "short" : "long"}`}
            x1={x} y1={top - 12} x2={x} y2={bot + 8} />
        ))}
        <path className="pf-line" d={line} />
        {[[ps, top], [cs, top]].map(([x, y], i) => (
          <circle key={i} className="pf-node" cx={x} cy={y} r="4" />
        ))}
      </svg>
      <div className="auth-zone"><span>{/* label rendered by CSS content in both langs */}</span></div>
    </div>
  );
}

const Eye = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
    <path d="M1.6 12S5.5 5 12 5s10.4 7 10.4 7-3.9 7-10.4 7S1.6 12 1.6 12Z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
);
const EyeOff = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9.9 5.2A9.9 9.9 0 0 1 12 5c6.5 0 10.4 7 10.4 7a18 18 0 0 1-3.4 4.2M6.2 6.7A18 18 0 0 0 1.6 12s3.9 7 10.4 7a9.7 9.7 0 0 0 4.2-.9" />
    <path d="m2 2 20 20" />
  </svg>
);
