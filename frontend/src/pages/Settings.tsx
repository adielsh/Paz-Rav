import { useEffect, useState } from "react";
import { Panel, Pill } from "../components/ui";
import { useT } from "../i18n/useT";
import { api, useMeQuery } from "../store/api";
import { useAppDispatch } from "../store/hooks";

interface CredStatus {
  flex_token_set: boolean; flex_query_id: string;
  ib_username_set: boolean; ib_account: string;
  updated_at: string | null;
}

/**
 * Broker credentials, per user.
 *
 * Secrets are write-only from the browser's point of view: the server reports whether each
 * one is set but never sends the value back, so a stored token cannot leak through the API
 * even to its owner.
 */
export default function Settings() {
  const { t } = useT();
  const dispatch = useAppDispatch();
  const { data: me } = useMeQuery();
  const [status, setStatus] = useState<CredStatus | null>(null);
  const [flexToken, setFlexToken] = useState("");
  const [flexQuery, setFlexQuery] = useState("");
  const [ibUser, setIbUser] = useState("");
  const [ibPass, setIbPass] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  // profile
  const [name, setName] = useState("");
  const [mail, setMail] = useState("");
  const [pmsg, setPmsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [pbusy, setPbusy] = useState(false);
  // password
  const [pwOld, setPwOld] = useState("");
  const [pwNew, setPwNew] = useState("");
  const [wmsg, setWmsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [wbusy, setWbusy] = useState(false);

  // Seed the profile fields once /auth/me lands.
  useEffect(() => {
    if (!me) return;
    setName(me.display_name ?? "");
    setMail(me.email);
  }, [me]);

  const dirtyProfile = !!me && (name !== (me.display_name ?? "") || mail !== me.email);

  const saveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setPbusy(true); setPmsg(null);
    const body: Record<string, string> = {};
    if (name !== (me?.display_name ?? "")) body.display_name = name;
    if (mail !== me?.email) body.email = mail;
    try {
      const r = await fetch("/api/auth/profile", {
        method: "PATCH", credentials: "include",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      if (!r.ok) {
        const d = (await r.json().catch(() => ({})))?.detail;
        throw new Error(typeof d === "string" ? d : "");
      }
      dispatch(api.util.invalidateTags(["Auth"]));
      setPmsg({ ok: true, text: t("set_saved") });
    } catch (err) {
      setPmsg({ ok: false, text: (err as Error).message || t("set_save_failed") });
    } finally { setPbusy(false); }
  };

  const changePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setWbusy(true); setWmsg(null);
    try {
      const r = await fetch("/api/auth/password", {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: pwOld, new_password: pwNew }),
      });
      if (!r.ok) {
        const d = (await r.json().catch(() => ({})))?.detail;
        throw new Error(typeof d === "string" ? d : "");
      }
      setPwOld(""); setPwNew("");
      setWmsg({ ok: true, text: t("set_pw_changed") });
    } catch (err) {
      setWmsg({ ok: false, text: (err as Error).message || t("set_save_failed") });
    } finally { setWbusy(false); }
  };

  const load = () => fetch("/api/auth/credentials", { credentials: "include" })
    .then((r) => (r.ok ? r.json() : null))
    .then((s: CredStatus | null) => { if (s) { setStatus(s); setFlexQuery(s.flex_query_id); } })
    .catch(() => setMsg({ ok: false, text: t("set_load_failed") }));

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setMsg(null);
    // Only send what was actually typed; omitted fields keep their stored value.
    const body: Record<string, string> = {};
    if (flexToken) body.flex_token = flexToken;
    if (flexQuery !== (status?.flex_query_id ?? "")) body.flex_query_id = flexQuery;
    if (ibUser) body.ib_username = ibUser;
    if (ibPass) body.ib_password = ibPass;
    if (Object.keys(body).length === 0) {
      setMsg({ ok: false, text: t("set_nothing") }); setBusy(false); return;
    }
    try {
      const r = await fetch("/api/auth/credentials", {
        method: "PUT", credentials: "include",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error();
      setStatus(await r.json());
      setFlexToken(""); setIbUser(""); setIbPass("");
      setMsg({ ok: true, text: t("set_saved") });
      dispatch(api.util.invalidateTags(["Auth", "Flex"]));
    } catch {
      setMsg({ ok: false, text: t("set_save_failed") });
    } finally { setBusy(false); }
  };

  return (
    <>
      <form onSubmit={saveProfile}>
        <Panel title={t("set_profile")}>
          <div className="setform">
            <label>
              <span>{t("auth_name")}</span>
              <input className="input" value={name} autoComplete="name"
                onChange={(e) => setName(e.target.value)} placeholder={t("auth_name_ph")} />
            </label>
            <label>
              <span>{t("auth_email")}</span>
              <input className="input" type="email" dir="ltr" value={mail}
                autoComplete="email" onChange={(e) => setMail(e.target.value)} />
            </label>
            <div className="setrow inline">
              <span className="k">{t("set_role")}</span>
              <Pill kind={me?.role === "owner" ? "info" : "mut"}>{me?.role ?? "—"}</Pill>
            </div>
            {pmsg && <div className={pmsg.ok ? "setok" : "loginerr"}>{pmsg.text}</div>}
            <div className="row">
              <button className="primary" type="submit" disabled={pbusy || !dirtyProfile}>
                {pbusy ? t("auth_working") : t("set_save")}
              </button>
            </div>
          </div>
        </Panel>
      </form>

      <form onSubmit={changePassword}>
        <Panel title={t("set_password")}>
          <div className="setform">
            <label>
              <span>{t("set_pw_current")}</span>
              <input className="input" type="password" dir="ltr" value={pwOld}
                autoComplete="current-password" onChange={(e) => setPwOld(e.target.value)} />
            </label>
            <label>
              <span>{t("set_pw_new")}</span>
              <input className="input" type="password" dir="ltr" value={pwNew}
                autoComplete="new-password" onChange={(e) => setPwNew(e.target.value)}
                placeholder={t("auth_password_rule")} />
            </label>
            {wmsg && <div className={wmsg.ok ? "setok" : "loginerr"}>{wmsg.text}</div>}
            <div className="row">
              <button className="primary" type="submit" disabled={wbusy || !pwOld || !pwNew}>
                {wbusy ? t("auth_working") : t("set_pw_change")}
              </button>
            </div>
          </div>
        </Panel>
      </form>

      <form onSubmit={save}>
        <Panel title={t("set_broker")}
          right={status?.updated_at
            ? <span className="muted" style={{ fontSize: 11 }}>
                {t("set_updated")} {new Date(status.updated_at).toLocaleString()}</span>
            : undefined}>
          <div className="setform">
            <p className="setlead">{t("set_flex_lead")}</p>

            <label>
              <span>
                {t("set_flex_token")}
                {status?.flex_token_set && <Pill kind="ok">{t("set_stored")}</Pill>}
              </span>
              <input className="input" type="password" dir="ltr" value={flexToken}
                autoComplete="off" onChange={(e) => setFlexToken(e.target.value)}
                placeholder={status?.flex_token_set ? t("set_replace_ph") : t("set_token_ph")} />
            </label>

            <label>
              <span>{t("set_flex_query")}</span>
              <input className="input" dir="ltr" value={flexQuery}
                onChange={(e) => setFlexQuery(e.target.value)} placeholder="1234567" />
            </label>

            <hr />

            <p className="setlead">
              {t("set_ib_lead")}
              <span className="setwarn">{t("set_ib_warn")}</span>
            </p>

            <label>
              <span>
                {t("set_ib_user")}
                {status?.ib_username_set && <Pill kind="ok">{t("set_stored")}</Pill>}
              </span>
              <input className="input" dir="ltr" value={ibUser} autoComplete="off"
                onChange={(e) => setIbUser(e.target.value)}
                placeholder={status?.ib_username_set ? t("set_replace_ph") : ""} />
            </label>

            <label>
              <span>{t("set_ib_pass")}</span>
              <input className="input" type="password" dir="ltr" value={ibPass}
                autoComplete="new-password" onChange={(e) => setIbPass(e.target.value)}
                placeholder={status?.ib_username_set ? t("set_replace_ph") : ""} />
            </label>

            {msg && <div className={msg.ok ? "setok" : "loginerr"}>{msg.text}</div>}

            <div className="row">
              <button className="primary" type="submit" disabled={busy}>
                {busy ? t("auth_working") : t("set_save")}
              </button>
              <span className="muted" style={{ fontSize: 11.5 }}>{t("set_encrypted")}</span>
            </div>
          </div>
        </Panel>
      </form>
    </>
  );
}
