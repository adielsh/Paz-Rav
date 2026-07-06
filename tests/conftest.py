"""Shared test fixtures — keeps the whole suite hermetic (no network, no real secrets).

Without this, any test that touches the agents/committee would silently pick up a real
ANTHROPIC_API_KEY / LANGFUSE_* from a developer's local .env file (env vars outrank the
.env file in pydantic-settings' source order, but an *absent* override falls through to
whatever the .env file has) — making "pure, no network" test runs quietly false, slow,
and dependent on real API spend. Setting empty-string overrides beats the file's values.
"""

from __future__ import annotations

import pytest

from paz_rav.config import get_settings


@pytest.fixture(autouse=True)
def _no_real_secrets(monkeypatch):
    for key in ("ANTHROPIC_API_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
        monkeypatch.setenv(key, "")   # empty string outranks the .env file's real value
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()   # don't leak the override into whatever runs next
