"""Accounts, sessions and per-user broker credentials.

Multi-tenant model: every user owns their own IBKR credentials and sees only their own
data. Credentials are encrypted at rest with APP_SECRET_KEY and are never returned to the
client — the API only ever reports whether a credential is set.

Threat model this does cover: database dumps, log leakage, and one user reading another's
data. What it does NOT cover: an attacker who has both the database and APP_SECRET_KEY.
Keep the key out of the database host and out of version control.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text

log = logging.getLogger("auth")
router = APIRouter(prefix="/auth", tags=["auth"])

SECRET = os.getenv("APP_SECRET_KEY", "")
COOKIE = "condor_session"
SESSION_HOURS = int(os.getenv("SESSION_HOURS", "12"))
# Cookies are same-site by default; set COOKIE_SECURE=1 once served over HTTPS.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "0") == "1"
ALLOW_SIGNUP = os.getenv("ALLOW_SIGNUP", "1") == "1"

# Password reset. There is no mail server in this deployment, so the reset link is written
# to the API log instead of emailed: on a console bound to localhost, whoever can read the
# server's logs already owns the machine. The token is single-use and short-lived anyway,
# and only its hash is stored, so a database dump does not hand over a working link.
RESET_TTL_MINUTES = int(os.getenv("RESET_TTL_MINUTES", "30"))
RESET_THROTTLE_SECONDS = int(os.getenv("RESET_THROTTLE_SECONDS", "60"))
CONSOLE_URL = os.getenv("CONSOLE_URL", "http://127.0.0.1:8080").rstrip("/")

_ph = PasswordHasher()


def _require_secret() -> str:
    if not SECRET or len(SECRET) < 32:
        raise RuntimeError(
            "APP_SECRET_KEY must be set to at least 32 characters. "
            "Generate one with:  python -c \"import secrets;print(secrets.token_urlsafe(48))\"")
    return SECRET


def _fernet() -> Fernet:
    """Derive a stable Fernet key from APP_SECRET_KEY (which is human-chosen, not 32 raw bytes)."""
    digest = hashlib.sha256(_require_secret().encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(value: str | None) -> str | None:
    return _fernet().encrypt(value.encode()).decode() if value else None


def decrypt(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        # Wrong/rotated key — surface as "not configured" rather than a 500.
        log.error("Could not decrypt a stored credential: APP_SECRET_KEY may have changed")
        return None


# ---------------------------------------------------------------- schema ----

def ensure_tables(engine) -> None:
    with engine.begin() as c:
        c.execute(text(
            "CREATE TABLE IF NOT EXISTS users ("
            "id serial PRIMARY KEY, "
            "email varchar(255) UNIQUE NOT NULL, "
            "password_hash varchar(255) NOT NULL, "
            "display_name varchar(120), "
            "role varchar(16) NOT NULL DEFAULT 'user', "
            "is_active boolean NOT NULL DEFAULT true, "
            "created_at timestamptz NOT NULL DEFAULT now(), "
            "last_login_at timestamptz)"))
        c.execute(text(
            "CREATE TABLE IF NOT EXISTS user_credentials ("
            "user_id integer PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, "
            "flex_token_enc text, flex_query_id varchar(64), "
            "ib_username_enc text, ib_password_enc text, "
            "ib_account varchar(32), "
            "updated_at timestamptz NOT NULL DEFAULT now())"))
        # Per-user statement cache. Keyed by user so one tenant never serves another's data.
        c.execute(text(
            "CREATE TABLE IF NOT EXISTS flex_cache_user ("
            "user_id integer PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, "
            "fetched_at timestamptz NOT NULL DEFAULT now(), payload jsonb)"))
        # Password resets. Only the SHA-256 of the token is stored — the plaintext exists
        # once, in the log line handed to the operator, and never in the database.
        c.execute(text(
            "CREATE TABLE IF NOT EXISTS password_resets ("
            "id serial PRIMARY KEY, "
            "user_id integer NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
            "token_hash varchar(64) UNIQUE NOT NULL, "
            "created_at timestamptz NOT NULL DEFAULT now(), "
            "expires_at timestamptz NOT NULL, "
            "used_at timestamptz)"))
        c.execute(text(
            "CREATE INDEX IF NOT EXISTS password_resets_user_idx ON password_resets (user_id)"))


# ----------------------------------------------------------------- models ---

class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    display_name: str | None = Field(default=None, max_length=120)


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class BrokerCreds(BaseModel):
    """All fields optional: send only what you want to change. Empty string clears."""
    flex_token: str | None = None
    flex_query_id: str | None = None
    ib_username: str | None = None
    ib_password: str | None = None


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=200)


class ForgotBody(BaseModel):
    email: EmailStr


class PasswordReset(BaseModel):
    token: str = Field(min_length=16, max_length=200)
    new_password: str = Field(min_length=10, max_length=200)


class Me(BaseModel):
    id: int
    email: str
    display_name: str | None
    role: str
    has_flex: bool
    has_ib_login: bool


# ------------------------------------------------------------- helpers -----

def _check_password(pw: str) -> None:
    """The one place the password rule lives — register, change and reset all use it."""
    if not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        raise HTTPException(422, "password needs at least one letter and one number")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _mask_email(email: str) -> str:
    """Enough to confirm which account a reset link belongs to, not enough to harvest one."""
    name, _, domain = email.partition("@")
    shown = name[0] + "•" * max(len(name) - 2, 1) + (name[-1] if len(name) > 1 else "")
    return f"{shown}@{domain}"


# ------------------------------------------------------------- session -----

def _issue(resp: Response, user_id: int, email: str) -> None:
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": str(user_id), "email": email, "iat": now,
         "exp": now + timedelta(hours=SESSION_HOURS)},
        _require_secret(), algorithm="HS256")
    resp.set_cookie(COOKIE, token, httponly=True, samesite="lax",
                    secure=COOKIE_SECURE, max_age=SESSION_HOURS * 3600, path="/")


def _decode(token: str) -> dict:
    return jwt.decode(token, _require_secret(), algorithms=["HS256"])


def current_user_id(**_) -> int:      # replaced below; kept for import clarity
    raise NotImplementedError


def make_dependencies(engine):
    """Bind the auth dependencies to the app's engine (avoids a circular import)."""

    def _row(sql: str, **p):
        with engine.connect() as c:
            r = c.execute(text(sql), p).mappings().first()
            return dict(r) if r else None

    def user_id(condor_session: str | None = Cookie(default=None)) -> int:
        if not condor_session:
            raise HTTPException(401, "not signed in")
        try:
            claims = _decode(condor_session)
        except jwt.ExpiredSignatureError:
            raise HTTPException(401, "session expired")
        except jwt.PyJWTError:
            raise HTTPException(401, "invalid session")
        uid = int(claims["sub"])
        u = _row("SELECT id, is_active FROM users WHERE id = :id", id=uid)
        if not u or not u["is_active"]:
            raise HTTPException(401, "account unavailable")
        return uid

    def creds(uid: int = Depends(user_id)) -> dict:
        """Decrypted broker credentials for the signed-in user."""
        r = _row("SELECT * FROM user_credentials WHERE user_id = :id", id=uid) or {}
        return {
            "user_id": uid,
            "flex_token": decrypt(r.get("flex_token_enc")),
            "flex_query_id": r.get("flex_query_id"),
            "ib_username": decrypt(r.get("ib_username_enc")),
            "ib_password": decrypt(r.get("ib_password_enc")),
        }

    return user_id, creds


def build_router(engine, user_id_dep):
    r = APIRouter(prefix="/auth", tags=["auth"])

    def _row(sql: str, **p):
        with engine.connect() as c:
            row = c.execute(text(sql), p).mappings().first()
            return dict(row) if row else None

    def _me(uid: int) -> Me:
        u = _row("SELECT u.id, u.email, u.display_name, u.role, "
                 "c.flex_token_enc, c.flex_query_id, c.ib_username_enc "
                 "FROM users u LEFT JOIN user_credentials c ON c.user_id = u.id "
                 "WHERE u.id = :id", id=uid)
        if not u:
            raise HTTPException(401, "account unavailable")
        return Me(id=u["id"], email=u["email"], display_name=u["display_name"], role=u["role"],
                  has_flex=bool(u["flex_token_enc"] and u["flex_query_id"]),
                  has_ib_login=bool(u["ib_username_enc"]))

    @r.get("/status")
    def status() -> dict:
        """Public: lets the sign-in screen know whether this is a first-run setup."""
        with engine.connect() as c:
            n = c.execute(text("SELECT count(*) FROM users")).scalar() or 0
        return {"users": n, "signup_open": ALLOW_SIGNUP or n == 0}

    @r.post("/register")
    def register(body: Credentials, resp: Response) -> Me:
        with engine.connect() as c:
            n = c.execute(text("SELECT count(*) FROM users")).scalar() or 0
        # The very first account can always be created, otherwise honour ALLOW_SIGNUP.
        if n > 0 and not ALLOW_SIGNUP:
            raise HTTPException(403, "sign-up is closed")
        if _row("SELECT id FROM users WHERE lower(email) = lower(:e)", e=body.email):
            raise HTTPException(409, "that email is already registered")
        _check_password(body.password)
        with engine.begin() as c:
            uid = c.execute(text(
                "INSERT INTO users (email, password_hash, display_name, role) "
                "VALUES (:e, :p, :d, :r) RETURNING id"),
                {"e": str(body.email).lower(), "p": _ph.hash(body.password),
                 "d": body.display_name, "r": "owner" if n == 0 else "user"}).scalar()
        log.info("user registered", extra={"user_id": uid})
        _issue(resp, uid, str(body.email).lower())
        return _me(uid)

    @r.post("/login")
    def login(body: LoginBody, resp: Response) -> Me:
        u = _row("SELECT id, email, password_hash, is_active FROM users "
                 "WHERE lower(email) = lower(:e)", e=body.email)
        # Same message either way — never reveal whether an address is registered.
        bad = HTTPException(401, "email or password is incorrect")
        if not u or not u["is_active"]:
            _ph.hash(body.password)          # keep the timing comparable
            raise bad
        try:
            _ph.verify(u["password_hash"], body.password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            raise bad
        if _ph.check_needs_rehash(u["password_hash"]):
            with engine.begin() as c:
                c.execute(text("UPDATE users SET password_hash = :p WHERE id = :i"),
                          {"p": _ph.hash(body.password), "i": u["id"]})
        with engine.begin() as c:
            c.execute(text("UPDATE users SET last_login_at = now() WHERE id = :i"), {"i": u["id"]})
        _issue(resp, u["id"], u["email"])
        return _me(u["id"])

    @r.post("/logout")
    def logout(resp: Response) -> dict:
        resp.delete_cookie(COOKIE, path="/")
        return {"ok": True}

    @r.get("/me")
    def me(uid: int = Depends(user_id_dep)) -> Me:
        return _me(uid)

    @r.patch("/profile")
    def update_profile(body: ProfileUpdate, uid: int = Depends(user_id_dep)) -> Me:
        sets, params = [], {"i": uid}
        if body.display_name is not None:
            sets.append("display_name = :d")
            params["d"] = body.display_name.strip() or None
        if body.email is not None:
            new = str(body.email).lower()
            clash = _row("SELECT id FROM users WHERE lower(email) = :e AND id <> :i",
                         e=new, i=uid)
            if clash:
                raise HTTPException(409, "that email is already registered")
            sets.append("email = :e")
            params["e"] = new
        if not sets:
            raise HTTPException(422, "nothing to update")
        with engine.begin() as c:
            c.execute(text(f"UPDATE users SET {', '.join(sets)} WHERE id = :i"), params)
        log.info("profile updated", extra={"user_id": uid, "fields": len(sets)})
        return _me(uid)

    @r.post("/password")
    def change_password(body: PasswordChange, resp: Response,
                        uid: int = Depends(user_id_dep)) -> dict:
        """Requires the current password: a stolen session must not be enough to take
        over the account permanently."""
        u = _row("SELECT id, email, password_hash FROM users WHERE id = :i", i=uid)
        if not u:
            raise HTTPException(401, "account unavailable")
        try:
            _ph.verify(u["password_hash"], body.current_password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            raise HTTPException(403, "current password is incorrect")
        _check_password(body.new_password)
        with engine.begin() as c:
            c.execute(text("UPDATE users SET password_hash = :p WHERE id = :i"),
                      {"p": _ph.hash(body.new_password), "i": uid})
            # A password the owner just set deliberately outranks any reset link still in
            # flight — burn them rather than leave a second way in.
            c.execute(text("UPDATE password_resets SET used_at = now() "
                           "WHERE user_id = :i AND used_at IS NULL"), {"i": uid})
        # Re-issue so the current tab stays signed in with a token minted after the change.
        _issue(resp, uid, u["email"])
        log.info("password changed", extra={"user_id": uid})
        return {"ok": True}

    # ------------------------------------------------------- password reset ---
    # No mail server exists here, so the link is delivered through the API log. The
    # endpoints below are deliberately silent about whether an address is registered:
    # /forgot answers identically either way.

    @r.post("/forgot")
    def forgot_password(body: ForgotBody) -> dict:
        """Issue a single-use reset link. Always reports success."""
        answer = {"ok": True, "delivery": "server-log", "ttl_minutes": RESET_TTL_MINUTES}
        u = _row("SELECT id, email, is_active FROM users WHERE lower(email) = lower(:e)",
                 e=body.email)
        if not u or not u["is_active"]:
            log.info("password reset requested for an unknown address")
            return answer
        recent = _row(
            "SELECT id FROM password_resets WHERE user_id = :i AND used_at IS NULL "
            "AND created_at > now() - make_interval(secs => :s) LIMIT 1",
            i=u["id"], s=RESET_THROTTLE_SECONDS)
        if recent:
            # Someone is hammering the form (or double-clicked). Don't mint a second live
            # token, and don't say so either.
            return answer
        token = secrets.token_urlsafe(32)
        with engine.begin() as c:
            c.execute(text(
                "INSERT INTO password_resets (user_id, token_hash, expires_at) "
                "VALUES (:u, :h, now() + make_interval(mins => :m))"),
                {"u": u["id"], "h": _hash_token(token), "m": RESET_TTL_MINUTES})
        # WARNING, not INFO: this must survive a default log configuration, because it is
        # the only copy of the link that will ever exist.
        log.warning(
            "PASSWORD RESET LINK for %s (valid %d minutes, single use): %s/?reset=%s",
            u["email"], RESET_TTL_MINUTES, CONSOLE_URL, token)
        return answer

    def _live_reset(token: str) -> dict | None:
        return _row(
            "SELECT p.id, p.user_id, u.email FROM password_resets p "
            "JOIN users u ON u.id = p.user_id "
            "WHERE p.token_hash = :h AND p.used_at IS NULL AND p.expires_at > now() "
            "AND u.is_active",
            h=_hash_token(token))

    @r.get("/reset")
    def check_reset(token: str) -> dict:
        """Lets the reset screen show a form or a dead-link message before asking for a
        password. Never 404s — a valid/invalid answer is all the caller gets."""
        hit = _live_reset(token)
        if not hit:
            return {"valid": False, "email": None}
        return {"valid": True, "email": _mask_email(hit["email"])}

    @r.post("/reset")
    def perform_reset(body: PasswordReset, resp: Response) -> Me:
        hit = _live_reset(body.token)
        if not hit:
            raise HTTPException(400, "this reset link is invalid or has expired")
        _check_password(body.new_password)
        with engine.begin() as c:
            c.execute(text("UPDATE users SET password_hash = :p WHERE id = :i"),
                      {"p": _ph.hash(body.new_password), "i": hit["user_id"]})
            # Single use, and every sibling link dies with it.
            c.execute(text("UPDATE password_resets SET used_at = now() "
                           "WHERE user_id = :i AND used_at IS NULL"), {"i": hit["user_id"]})
        log.warning("password reset completed", extra={"user_id": hit["user_id"]})
        # Sign them straight in: they have just proved control of the link and set the
        # password, so a second trip through the login form buys nothing.
        _issue(resp, hit["user_id"], hit["email"])
        return _me(hit["user_id"])

    @r.get("/credentials")
    def get_credentials(uid: int = Depends(user_id_dep)) -> dict:
        """Reports only whether each credential is set — secrets never leave the server."""
        c = _row("SELECT flex_token_enc, flex_query_id, ib_username_enc, ib_account, updated_at "
                 "FROM user_credentials WHERE user_id = :i", i=uid) or {}
        return {
            "flex_token_set": bool(c.get("flex_token_enc")),
            "flex_query_id": c.get("flex_query_id") or "",
            "ib_username_set": bool(c.get("ib_username_enc")),
            "ib_account": c.get("ib_account") or "",
            "updated_at": c.get("updated_at"),
        }

    @r.put("/credentials")
    def set_credentials(body: BrokerCreds, uid: int = Depends(user_id_dep)) -> dict:
        sets, params = [], {"i": uid}
        for field, col, enc in (("flex_token", "flex_token_enc", True),
                                ("flex_query_id", "flex_query_id", False),
                                ("ib_username", "ib_username_enc", True),
                                ("ib_password", "ib_password_enc", True)):
            v = getattr(body, field)
            if v is None:
                continue                                   # omitted = leave unchanged
            params[col] = encrypt(v) if (enc and v) else (v or None)
            sets.append(f"{col} = :{col}")
        if not sets:
            raise HTTPException(422, "nothing to update")
        with engine.begin() as c:
            c.execute(text("INSERT INTO user_credentials (user_id) VALUES (:i) "
                           "ON CONFLICT (user_id) DO NOTHING"), {"i": uid})
            c.execute(text(f"UPDATE user_credentials SET {', '.join(sets)}, updated_at = now() "
                           "WHERE user_id = :i"), params)
        log.info("credentials updated", extra={"user_id": uid, "fields": len(sets)})
        return get_credentials(uid)

    return r
