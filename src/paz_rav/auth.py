"""Firebase ID-token verification + the owner-approval gate.

Google's Sign-In popup (client-side) produces the token; this module verifies it (via
PyJWT against Google's public keys — no firebase-admin SDK needed, since we never issue
tokens ourselves), then decides who gets in:

- The configured ``ALLOWED_EMAIL`` (the owner) always gets in.
- Any other verified email gets a pending ``AccessRequest`` created (once) and the owner
  is emailed a one-click approval link (``notify.py``) — the request stays pending until
  that link is opened (``/admin/approve``, in ``api/app.py``).

Auth is OFF by default (``ALLOWED_EMAIL`` unset) — that's the local/dev/Docker-Compose
case, where locking yourself out would be actively unhelpful.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import jwt
from fastapi import HTTPException, Request, WebSocket
from jwt import PyJWKClient

from paz_rav.access_requests import AccessRequestRepository
from paz_rav.config import get_settings
from paz_rav.notify import notify_access_request

log = logging.getLogger("paz_rav.auth")

_GOOGLE_JWKS_URL = (
    "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"
)


@lru_cache
def _jwk_client() -> PyJWKClient:
    return PyJWKClient(_GOOGLE_JWKS_URL, cache_keys=True)


def verify_firebase_token(token: str, project_id: str) -> dict:
    """Verify a Firebase ID token's signature, issuer, audience, and expiry.

    Raises a ``jwt`` exception (caught by callers) on any failure — never returns a
    claims dict for a token that didn't fully verify. ``leeway`` tolerates a bit of
    clock drift between this container and Google's token timestamp (real and enough to
    matter on Docker/Pi hosts — without it, a token can be rejected as "not yet valid"
    or "expired" by a couple of seconds of skew alone).
    """
    signing_key = _jwk_client().get_signing_key_from_jwt(token)
    return jwt.decode(
        token, signing_key.key, algorithms=["RS256"],
        audience=project_id, issuer=f"https://securetoken.google.com/{project_id}",
        leeway=60,
    )


async def _resolve_access(claims: dict, access_repo: AccessRequestRepository) -> None:
    """Raises HTTPException(403, detail="pending_approval") unless this email is the
    owner or already approved. A brand-new email gets a pending request created and the
    owner notified as a side effect — it still doesn't get in on this call, only once
    the owner clicks the emailed link.
    """
    settings = get_settings()
    email = claims.get("email")
    if not email or not claims.get("email_verified"):
        log.warning("auth rejected: email missing/unverified in token")
        raise HTTPException(status_code=403, detail="email_unverified")
    if email == settings.allowed_email:
        return
    existing = await access_repo.get(email)
    if existing and existing.status == "approved":
        return
    if existing and existing.status == "pending":
        raise HTTPException(status_code=403, detail="pending_approval")
    req = await access_repo.create_pending(email)
    log.warning("new access request from %s — notifying owner", email)
    await notify_access_request(email, req.token)
    raise HTTPException(status_code=403, detail="pending_approval")


async def require_auth(request: Request, access_repo: AccessRequestRepository) -> dict:
    """FastAPI-style guard for HTTP routes: 401/403 unless the bearer token is valid and
    the email is the owner or approved. A no-op (auth disabled) when ``ALLOWED_EMAIL``
    isn't set — the local/dev default.
    """
    settings = get_settings()
    if not settings.allowed_email:
        return {}
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer "):
        log.warning("auth rejected: no bearer token on %s %s", request.method, request.url.path)
        raise HTTPException(status_code=401, detail="missing bearer token")
    try:
        claims = verify_firebase_token(header[len("Bearer "):].strip(), settings.firebase_project_id)
    except HTTPException:
        raise
    except Exception as e:
        log.warning("token verification failed: %s", e)
        raise HTTPException(status_code=401, detail=f"invalid token: {e}") from e
    await _resolve_access(claims, access_repo)
    return claims


async def require_auth_ws(websocket: WebSocket, access_repo: AccessRequestRepository) -> bool:
    """WebSocket variant: the browser's WebSocket API can't send custom headers, so the
    token travels as a query parameter instead. Closes the socket and returns False on
    any failure; callers must not proceed to `accept()` when this returns False.
    """
    settings = get_settings()
    if not settings.allowed_email:
        return True
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return False
    try:
        claims = verify_firebase_token(token, settings.firebase_project_id)
        await _resolve_access(claims, access_repo)
    except Exception:
        await websocket.close(code=4401)
        return False
    return True
