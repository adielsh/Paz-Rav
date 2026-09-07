import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { useT } from "../i18n/useT";

/**
 * The in-console assistant: a floating button that opens a panel for questions about the
 * data on screen.
 *
 * It is deliberately thin. The server builds an already-computed snapshot of this account
 * and instructs the model never to produce a number that is not in it, so there is nothing
 * to calculate or format here — the panel ships the question, the current page, and the
 * recent turns, and renders whatever comes back. The "reads only what is on screen" line
 * under the input is not decoration: it is the contract the backend enforces.
 */

type Turn = { role: "user" | "assistant"; content: string };

export default function ChatBot() {
  const { t } = useT();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Asked once, on first open — no point polling a key that only changes on restart.
  useEffect(() => {
    if (!open || configured !== null) return;
    fetch("/api/chat/status", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setConfigured(!!d.configured))
      .catch(() => setConfigured(false));
  }, [open, configured]);

  useEffect(() => {
    if (open) {
      endRef.current?.scrollIntoView({ block: "end" });
      inputRef.current?.focus();
    }
  }, [open, turns, busy]);

  // Escape closes, like every other overlay in this console.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const send = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const question = draft.trim();
    if (!question || busy) return;
    const history = turns.slice(-10);
    setTurns([...turns, { role: "user", content: question }]);
    setDraft("");
    setErr(null);
    setBusy(true);
    try {
      const r = await fetch("/api/chat", {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, page: pathname, history }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        setErr(typeof d?.detail === "string" ? d.detail : t("chat_failed"));
      } else if (d.answer) {
        setTurns((prev) => [...prev, { role: "assistant", content: d.answer }]);
      } else {
        setErr(d.error || t("chat_failed"));
        if (d.configured === false) setConfigured(false);
      }
    } catch {
      setErr(t("chat_unreachable"));
    } finally {
      setBusy(false);
    }
  };

  // Enter sends, Shift+Enter is a newline — questions are one-liners far more often than not.
  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(); }
  };

  return (
    <>
      <button className={`chat-fab${open ? " on" : ""}`} onClick={() => setOpen(!open)}
        aria-label={t("chat_title")} aria-expanded={open}>
        {open ? <CloseIcon /> : <BotIcon />}
      </button>

      {open && (
        <section className="chat-panel" role="dialog" aria-label={t("chat_title")}>
          <header className="chat-head">
            <span className="chat-mark"><BotIcon /></span>
            <div>
              <b>{t("chat_title")}</b>
              <small>{t("chat_sub")}</small>
            </div>
            <button className="chat-x" onClick={() => setOpen(false)}
              aria-label={t("chat_close")}><CloseIcon /></button>
          </header>

          <div className="chat-log">
            {configured === false && (
              <div className="chat-note" role="status">{t("chat_unconfigured")}</div>
            )}
            {turns.length === 0 && configured !== false && (
              <div className="chat-note">
                <p>{t("chat_intro")}</p>
                <ul>
                  <li>{t("chat_eg_1")}</li>
                  <li>{t("chat_eg_2")}</li>
                  <li>{t("chat_eg_3")}</li>
                </ul>
              </div>
            )}
            {turns.map((m, i) => (
              <div key={i} className={`chat-msg ${m.role}`}>{m.content}</div>
            ))}
            {busy && <div className="chat-msg assistant chat-wait">{t("chat_thinking")}</div>}
            {err && <div className="chat-err" role="alert">{err}</div>}
            <div ref={endRef} />
          </div>

          <form className="chat-input" onSubmit={send}>
            <textarea ref={inputRef} rows={2} value={draft} disabled={configured === false}
              onChange={(e) => setDraft(e.target.value)} onKeyDown={onKeyDown}
              placeholder={t("chat_placeholder")} />
            <button type="submit" disabled={busy || !draft.trim() || configured === false}
              aria-label={t("chat_send")}><SendIcon /></button>
          </form>
          <p className="chat-foot">{t("chat_grounded")}</p>
        </section>
      )}
    </>
  );
}

/* Inline SVG, like the rest of the console — no icon font, no emoji as structural icons. */
const BotIcon = () => (
  <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <rect x="3.5" y="7.5" width="17" height="12" rx="3.2" />
    <path d="M12 7.5V4M12 4h-1.6M12 4h1.6" />
    <circle cx="8.8" cy="13.2" r="1.15" fill="currentColor" stroke="none" />
    <circle cx="15.2" cy="13.2" r="1.15" fill="currentColor" stroke="none" />
    <path d="M9.6 16.6h4.8M1.6 11.6v3.6M22.4 11.6v3.6" />
  </svg>
);
const CloseIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" aria-hidden>
    <path d="m5 5 14 14M19 5 5 19" />
  </svg>
);
const SendIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d="M4 12 20 4l-8 16-2.2-6.2L4 12Z" />
  </svg>
);
