"""Auth gate — Firebase ID-token verification, owner/approval logic, on/off by config.

We never construct a real signed Google token in tests (that needs network access to
Google's JWKS endpoint); ``verify_firebase_token`` is mocked instead, so these tests
exercise our own logic (owner bypass, pending/approved states, the on/off switch, the
header/query-param plumbing) rather than JWT cryptography itself. ``notify_access_request``
is also mocked — sending real email in a test suite would be both slow and wrong.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException, Request

from paz_rav import auth as auth_mod
from paz_rav.access_requests_memory import InMemoryAccessRequestRepository
from paz_rav.config import get_settings


def _settings_with(**overrides):
    from dataclasses import dataclass

    @dataclass
    class _S:
        allowed_email: str = ""
        firebase_project_id: str = ""

    return _S(**overrides)


def _request(headers: dict) -> Request:
    scope = {
        "type": "http", "method": "GET", "path": "/api/state",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    return Request(scope)


def _run(coro):
    return asyncio.run(coro)


def test_auth_off_by_default_is_a_noop(monkeypatch):
    monkeypatch.setattr(auth_mod, "get_settings", lambda: _settings_with(allowed_email=""))
    repo = InMemoryAccessRequestRepository()
    assert _run(auth_mod.require_auth(_request({}), repo)) == {}


def test_auth_on_rejects_missing_token(monkeypatch):
    monkeypatch.setattr(auth_mod, "get_settings",
                        lambda: _settings_with(allowed_email="me@example.com", firebase_project_id="p"))
    repo = InMemoryAccessRequestRepository()
    with pytest.raises(HTTPException) as exc:
        _run(auth_mod.require_auth(_request({}), repo))
    assert exc.value.status_code == 401


def test_owner_email_always_allowed(monkeypatch):
    monkeypatch.setattr(auth_mod, "get_settings",
                        lambda: _settings_with(allowed_email="me@example.com", firebase_project_id="p"))
    monkeypatch.setattr(auth_mod, "verify_firebase_token",
                        lambda token, project_id: {"email": "me@example.com", "email_verified": True})
    repo = InMemoryAccessRequestRepository()
    claims = _run(auth_mod.require_auth(_request({"authorization": "Bearer faketoken"}), repo))
    assert claims["email"] == "me@example.com"


def test_unverified_email_rejected(monkeypatch):
    monkeypatch.setattr(auth_mod, "get_settings",
                        lambda: _settings_with(allowed_email="me@example.com", firebase_project_id="p"))
    monkeypatch.setattr(auth_mod, "verify_firebase_token",
                        lambda token, project_id: {"email": "me@example.com", "email_verified": False})
    repo = InMemoryAccessRequestRepository()
    with pytest.raises(HTTPException) as exc:
        _run(auth_mod.require_auth(_request({"authorization": "Bearer faketoken"}), repo))
    assert exc.value.status_code == 403


def test_new_email_creates_pending_request_and_notifies_owner(monkeypatch):
    monkeypatch.setattr(auth_mod, "get_settings",
                        lambda: _settings_with(allowed_email="owner@example.com", firebase_project_id="p"))
    monkeypatch.setattr(auth_mod, "verify_firebase_token",
                        lambda token, project_id: {"email": "new@example.com", "email_verified": True})
    notified = {}

    async def _fake_notify(email, token):
        notified["email"] = email
        notified["token"] = token

    monkeypatch.setattr(auth_mod, "notify_access_request", _fake_notify)
    repo = InMemoryAccessRequestRepository()

    with pytest.raises(HTTPException) as exc:
        _run(auth_mod.require_auth(_request({"authorization": "Bearer faketoken"}), repo))
    assert exc.value.status_code == 403
    assert exc.value.detail == "pending_approval"
    assert notified["email"] == "new@example.com"

    stored = _run(repo.get("new@example.com"))
    assert stored.status == "pending"
    assert stored.token == notified["token"]


def test_pending_email_stays_rejected_without_renotifying(monkeypatch):
    monkeypatch.setattr(auth_mod, "get_settings",
                        lambda: _settings_with(allowed_email="owner@example.com", firebase_project_id="p"))
    monkeypatch.setattr(auth_mod, "verify_firebase_token",
                        lambda token, project_id: {"email": "new@example.com", "email_verified": True})
    calls = []

    async def _fake_notify(email, token):
        calls.append(email)

    monkeypatch.setattr(auth_mod, "notify_access_request", _fake_notify)
    repo = InMemoryAccessRequestRepository()
    req = _request({"authorization": "Bearer faketoken"})

    for _ in range(2):
        with pytest.raises(HTTPException) as exc:
            _run(auth_mod.require_auth(req, repo))
        assert exc.value.detail == "pending_approval"

    assert calls == ["new@example.com"]   # only the first call notified


def test_approved_email_gets_in(monkeypatch):
    monkeypatch.setattr(auth_mod, "get_settings",
                        lambda: _settings_with(allowed_email="owner@example.com", firebase_project_id="p"))
    monkeypatch.setattr(auth_mod, "verify_firebase_token",
                        lambda token, project_id: {"email": "friend@example.com", "email_verified": True})
    repo = InMemoryAccessRequestRepository()
    req = _run(repo.create_pending("friend@example.com"))
    _run(repo.approve_by_token(req.token))

    claims = _run(auth_mod.require_auth(_request({"authorization": "Bearer faketoken"}), repo))
    assert claims["email"] == "friend@example.com"


def test_auth_on_rejects_bad_signature(monkeypatch):
    monkeypatch.setattr(auth_mod, "get_settings",
                        lambda: _settings_with(allowed_email="me@example.com", firebase_project_id="p"))

    def _boom(token, project_id):
        raise ValueError("signature verification failed")

    monkeypatch.setattr(auth_mod, "verify_firebase_token", _boom)
    repo = InMemoryAccessRequestRepository()
    with pytest.raises(HTTPException) as exc:
        _run(auth_mod.require_auth(_request({"authorization": "Bearer garbage"}), repo))
    assert exc.value.status_code == 401


def test_real_settings_default_to_auth_off():
    """Sanity check against the real Settings class (not the stub): unconfigured means off."""
    get_settings.cache_clear()
    s = get_settings()
    assert s.allowed_email == ""
    get_settings.cache_clear()
