import { useEffect, useState } from "react";
import { useT } from "../i18n/useT";
import { useAppDispatch } from "../store/hooks";
import { toggleLang } from "../store/uiSlice";
import { api } from "../store/api";

type Mode = "login" | "register" | "forgot" | "reset";

/** A reset link is just `/?reset=<token>` — read it once, before anything renders. */
export function resetTokenFromUrl(): string | null {
  try {
    return new URLSearchParams(window.location.search).get("reset");
  } catch {
    return null;
  }
}

/**
 * Sign-in / first-run setup, plus the two password-recovery steps.
 *
 * Split layout: the strategy's own payoff profile on the left, the form on the right. The
 * first account created becomes the owner; whether further accounts can be opened is a
 * server decision (ALLOW_SIGNUP), so this screen asks rather than guessing.
 *
 * Recovery lives here rather than on its own route because App only ever renders this
 * component when there is no session — a separate route would be unreachable.
 */
export default function Login() {
  const { t } = useT();
  const dispatch = useAppDispatch();
  const token = resetTokenFromUrl();
  const [mode, setMode] = useState<Mode>(token ? "reset" : "login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [name, setName] = useState("");
  const [reveal, setReveal] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [firstRun, setFirstRun] = useState(false);
  const [signupOpen, setSignupOpen] = useState(true);
  const [sent, setSent] = useState(false);
  // null = still checking the token; the reset form waits rather than flashing a field
  // that may be attached to a dead link.
  const [linkFor, setLinkFor] = useState<{ valid: boolean; email: string | null } | null>(null);

  useEffect(() => {
    fetch("/api/auth/status", { credentials: "include" })
      .then((r) => r.json())
      .then((s) => {
        setFirstRun(s.users === 0);
        setSignupOpen(!!s.signup_open);
        if (s.users === 0 && !token) setMode("register");
      })
      .catch(() => { /* server unreachable — the submit will report it */ });
  }, [token]);

  useEffect(() => {
    if (!token) return;
    fetch(`/api/auth/reset?token=${encodeURIComponent(token)}`, { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setLinkFor({ valid: !!d.valid, email: d.email ?? null }))
      .catch(() => setLinkFor({ valid: false, email: null }));
  }, [token]);

  const go = (next: Mode) => { setMode(next); setErr(null); setSent(false); };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null); setBusy(true);
    try {
      if (mode === "forgot") {
        // The server answers the same whether or not the address is registered, so the
        // screen must not imply a lookup happened either.
        await fetch("/api/auth/forgot", {
          method: "POST", credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email }),
        });
        setSent(true);
        return;
      }
      if (mode === "reset" && password !== confirm) {
        setErr(t("auth_reset_mismatch"));
        return;
      }

      const url = mode === "reset" ? "/api/auth/reset" : `/api/auth/${mode}`;
      const payload =
        mode === "reset" ? { token, new_password: password }
        : mode === "register" ? { email, password, display_name: name || null }
        : { email, password };

      const r = await fetch(url, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
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
      // Drop the token from the address bar: it is spent, and it should not survive in
      // history or get pasted somewhere with the rest of the URL.
      window.location.replace("/");
    } catch {
      setErr(t("auth_unreachable"));
    } finally {
      setBusy(false);
    }
  };

  const deadLink = mode === "reset" && linkFor !== null && !linkFor.valid;

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
            <li><b>IBKR</b><i>{t("auth_spec_broker")}</i></li>
            <li><b>SPXW</b><i>{t("auth_spec_instrument")}</i></li>
            <li><b>{t("auth_spec_manual_v")}</b><i>{t("auth_spec_manual")}</i></li>
            <li><b>{t("auth_spec_log_v")}</b><i>{t("auth_spec_log")}</i></li>
          </ul>
        </footer>
      </section>

      {/* ----------------------------------------------------------- form -- */}
      <section className="auth-panel">
        <button className="langbtn auth-lang" onClick={() => dispatch(toggleLang())}>
          {t("lang_button")}
        </button>

        <form className="auth-form" onSubmit={submit}>
          {/* Sign in is always reachable. Hiding it on a fresh install produced a dead
              end: anyone who already had an account saw only "Create account". */}
          {(mode === "login" || mode === "register") && (
            <div className="auth-tabs" role="tablist">
              <button type="button" role="tab" aria-selected={mode === "login"}
                className={mode === "login" ? "on" : ""}
                onClick={() => go("login")}>
                {t("auth_signin")}
              </button>
              {signupOpen && (
                <button type="button" role="tab" aria-selected={mode === "register"}
                  className={mode === "register" ? "on" : ""}
                  onClick={() => go("register")}>
                  {t("auth_create")}
                </button>
              )}
            </div>
          )}

          {(mode === "forgot" || mode === "reset") && (
            <div className="auth-tabs" role="tablist">
              <button type="button" role="tab" aria-selected className="on">
                {mode === "forgot" ? t("auth_forgot_title") : t("auth_reset_title")}
              </button>
            </div>
          )}

          {firstRun && mode === "register" && (
            <p className="auth-first-note">{t("auth_setup_lead")}</p>
          )}

          {mode === "forgot" && !sent && (
            <p className="auth-first-note">{t("auth_forgot_lead")}</p>
          )}

          {/* Link created. There is no mailbox to point at, so point at the log. */}
          {mode === "forgot" && sent && (
            <div className="auth-ok" role="status">
              <p>{t("auth_forgot_sent")}</p>
              <p className="auth-where">{t("auth_forgot_where")}</p>
              <code dir="ltr">docker compose logs api | grep "PASSWORD RESET LINK"</code>
            </div>
          )}

          {mode === "reset" && linkFor === null && (
            <p className="auth-first-note">{t("auth_reset_checking")}</p>
          )}
          {deadLink && <div className="auth-err" role="alert">{t("auth_reset_bad")}</div>}
          {mode === "reset" && linkFor?.valid && (
            <p className="auth-first-note">
              {t("auth_reset_for")} <b dir="ltr">{linkFor.email}</b>
            </p>
          )}

          {mode === "register" && (
            <label className="auth-field">
              <span>{t("auth_name")}</span>
              <input value={name} autoComplete="name"
                onChange={(e) => setName(e.target.value)} placeholder={t("auth_name_ph")} />
            </label>
          )}

          {mode !== "reset" && !(mode === "forgot" && sent) && (
            <label className="auth-field">
              <span>{t("auth_email")}</span>
              <input type="email" required value={email} autoComplete="email" dir="ltr"
                onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
            </label>
          )}

          {mode !== "forgot" && !deadLink && (mode !== "reset" || linkFor?.valid) && (
            <label className="auth-field">
              <span>{mode === "reset" ? t("auth_reset_new") : t("auth_password")}</span>
              <div className="auth-pw">
                <input type={reveal ? "text" : "password"} required value={password} dir="ltr"
                  autoComplete={mode === "login" ? "current-password" : "new-password"}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={mode === "login" ? "" : t("auth_password_rule")} />
                <button type="button" onClick={() => setReveal(!reveal)}
                  aria-label={reveal ? t("auth_hide") : t("auth_show")}>
                  {reveal ? <EyeOff /> : <Eye />}
                </button>
              </div>
            </label>
          )}

          {mode === "reset" && linkFor?.valid && (
            <label className="auth-field">
              <span>{t("auth_reset_confirm")}</span>
              <input type={reveal ? "text" : "password"} required value={confirm} dir="ltr"
                autoComplete="new-password" onChange={(e) => setConfirm(e.target.value)} />
            </label>
          )}

          {mode === "login" && (
            <button type="button" className="auth-link" onClick={() => go("forgot")}>
              {t("auth_forgot_link")}
            </button>
          )}

          {err && <div className="auth-err" role="alert">{err}</div>}

          {!(mode === "forgot" && sent) && !deadLink && (mode !== "reset" || linkFor?.valid) && (
            <button className="auth-go" type="submit" disabled={busy}>
              {busy ? t("auth_working")
                : mode === "login" ? t("auth_signin")
                : mode === "register" ? t("auth_create")
                : mode === "forgot" ? t("auth_forgot_go")
                : t("auth_reset_go")}
            </button>
          )}

          {(mode === "forgot" || mode === "reset") && (
            <button type="button" className="auth-link"
              onClick={() => {
                // A spent or dead token in the URL would drop us straight back here.
                if (token) window.location.replace("/");
                else go("login");
              }}>
              {t("auth_back_signin")}
            </button>
          )}

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
