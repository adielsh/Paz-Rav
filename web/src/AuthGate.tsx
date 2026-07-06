import { useEffect, useState, type ReactNode } from "react";
import type { User } from "firebase/auth";
import { authedFetch } from "./api";
import { signInWithGoogle, signOutUser, watchAuthState } from "./auth";

function GoogleG() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.9c1.7-1.57 2.7-3.88 2.7-6.62z" />
      <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.9-2.26c-.8.54-1.84.86-3.06.86-2.35 0-4.34-1.59-5.05-3.72H.98v2.33A9 9 0 0 0 9 18z" />
      <path fill="#FBBC05" d="M3.95 10.7A5.4 5.4 0 0 1 3.67 9c0-.59.1-1.17.28-1.7V4.97H.98A9 9 0 0 0 0 9c0 1.45.35 2.83.98 4.03z" />
      <path fill="#EA4335" d="M9 3.58c1.32 0 2.51.46 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 0 0 .98 4.97L3.95 7.3C4.66 5.17 6.65 3.58 9 3.58z" />
    </svg>
  );
}

function LoginScreen({ onSignIn, error }: { onSignIn: () => void; error: string | null }) {
  const [busy, setBusy] = useState(false);
  const handleClick = async () => {
    setBusy(true);
    try {
      await onSignIn();
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="min-h-dvh grid place-items-center px-4">
      <div className="w-full max-w-sm rounded-2xl border border-line bg-panel/80 p-7 text-center shadow-elevated">
        <div
          className="w-11 h-11 mx-auto mb-4 rounded-xl grid place-items-center font-mono font-bold text-base"
          style={{ background: "linear-gradient(155deg, #E8C179, #B4863B)", color: "#1A1206" }}
          aria-hidden="true"
        >
          P
        </div>
        <h1 className="text-lg font-bold tracking-tight mb-1">Paz Rav</h1>
        <p className="text-sm text-ink-2 mb-6">Sign in to view the dashboard.</p>
        <button
          onClick={handleClick}
          disabled={busy}
          className="w-full inline-flex items-center justify-center gap-2.5 rounded-xl bg-white text-[#1F1F1F] font-medium text-sm py-2.5 px-4 hover:bg-white/90 transition disabled:opacity-60"
        >
          <GoogleG />
          {busy ? "Signing in…" : "Sign in with Google"}
        </button>
        {error && (
          <p role="alert" className="mt-4 text-xs text-bad">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}

function PendingScreen({ email }: { email: string | null }) {
  return (
    <div className="min-h-dvh grid place-items-center px-4">
      <div className="w-full max-w-sm rounded-2xl border border-warn/30 bg-panel/80 p-7 text-center shadow-elevated">
        <h1 className="text-lg font-bold tracking-tight mb-2 text-warn">Request sent</h1>
        <p className="text-sm text-ink-2 mb-6">
          {email ? <span className="font-mono">{email}</span> : "This account"} isn't approved yet.
          The owner was emailed a link — check back once it's approved.
        </p>
        <button
          onClick={() => signOutUser()}
          className="w-full rounded-xl border border-line text-sm py-2.5 px-4 hover:bg-panel2 transition"
        >
          Sign out
        </button>
      </div>
    </div>
  );
}

function UnauthorizedScreen({ email }: { email: string | null }) {
  return (
    <div className="min-h-dvh grid place-items-center px-4">
      <div className="w-full max-w-sm rounded-2xl border border-bad/30 bg-panel/80 p-7 text-center shadow-elevated">
        <h1 className="text-lg font-bold tracking-tight mb-2 text-bad">Not authorized</h1>
        <p className="text-sm text-ink-2 mb-6">
          {email ? <span className="font-mono">{email}</span> : "This account"} isn't allowed to
          access this dashboard.
        </p>
        <button
          onClick={() => signOutUser()}
          className="w-full rounded-xl border border-line text-sm py-2.5 px-4 hover:bg-panel2 transition"
        >
          Sign out and try another account
        </button>
      </div>
    </div>
  );
}

export function SignedInBar({ user }: { user: User }) {
  return (
    <div className="flex items-center gap-2.5 text-2xs text-ink-3 font-mono">
      {user.photoURL && (
        <img src={user.photoURL} alt="" className="w-5 h-5 rounded-full" referrerPolicy="no-referrer" />
      )}
      <span className="hidden sm:inline">{user.email}</span>
      <button
        onClick={() => signOutUser()}
        className="underline decoration-dotted underline-offset-2 hover:text-ink-2 transition"
      >
        sign out
      </button>
    </div>
  );
}

interface AuthConfig {
  required: boolean;
}

export default function AuthGate({ children }: { children: (user: User | null) => ReactNode }) {
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // null = still checking with the backend. Firebase itself will happily sign in ANY
  // Google account — only the backend decides ok / pending_approval / denied.
  const [status, setStatus] = useState<"ok" | "pending" | "denied" | null>(null);

  useEffect(() => {
    fetch("/auth-config")
      .then((r) => r.json())
      .then(setConfig)
      .catch(() => setConfig({ required: false })); // fail open to local/dev behavior
  }, []);

  useEffect(() => {
    if (!config?.required) return;
    return watchAuthState((u) => {
      setUser(u);
      setChecked(true);
      setStatus(null);
    });
  }, [config]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    authedFetch("/api/underlyings")
      .then(async (r) => {
        if (cancelled) return;
        if (r.ok) return setStatus("ok");
        const body = await r.json().catch(() => ({}));
        setStatus(body.detail === "pending_approval" ? "pending" : "denied");
      })
      .catch(() => {
        if (!cancelled) setStatus("denied");
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  if (config === null) return null;
  if (!config.required) return <>{children(null)}</>;
  if (!checked) return null;
  if (!user) {
    return (
      <LoginScreen
        error={error}
        onSignIn={async () => {
          setError(null);
          try {
            await signInWithGoogle();
          } catch {
            setError("Sign-in failed or was cancelled — try again.");
          }
        }}
      />
    );
  }
  if (status === null) return null;
  if (status === "pending") return <PendingScreen email={user.email} />;
  if (status === "denied") return <UnauthorizedScreen email={user.email} />;
  return <>{children(user)}</>;
}
