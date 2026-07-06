"""Access requests — anyone can sign in with Google; the owner approves each new email.

The configured ``ALLOWED_EMAIL`` (the owner) always gets in and never goes through this
flow. Every other email that signs in gets a pending request + a one-click approval
email sent to the owner; the request stays pending until that link is clicked. This is
the middle ground between "only me" (too rigid to ever share) and "any Google account"
(too open for a trading dashboard).
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

Status = Literal["pending", "approved"]


@dataclass(frozen=True, slots=True)
class AccessRequest:
    email: str
    status: Status
    token: str
    requested_at: datetime
    decided_at: datetime | None = None


class AccessRequestRepository(Protocol):
    async def get(self, email: str) -> AccessRequest | None: ...
    async def create_pending(self, email: str) -> AccessRequest: ...
    async def approve_by_token(self, token: str) -> AccessRequest | None: ...


def new_token() -> str:
    return secrets.token_urlsafe(24)
