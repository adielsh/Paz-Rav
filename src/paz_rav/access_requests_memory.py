"""In-memory AccessRequestRepository — default and test backend.

Pending requests don't survive a restart in this mode, same trade-off as every other
in-memory store in this project (see store/memory.py) — fine for local/dev, not for a
real public deployment (use PostgresAccessRequestRepository there instead).
"""

from __future__ import annotations

from datetime import datetime, timezone

from paz_rav.access_requests import AccessRequest, new_token


class InMemoryAccessRequestRepository:
    def __init__(self) -> None:
        self._by_email: dict[str, AccessRequest] = {}

    async def get(self, email: str) -> AccessRequest | None:
        return self._by_email.get(email)

    async def create_pending(self, email: str) -> AccessRequest:
        req = AccessRequest(email=email, status="pending", token=new_token(),
                            requested_at=datetime.now(timezone.utc))
        self._by_email[email] = req
        return req

    async def approve_by_token(self, token: str) -> AccessRequest | None:
        for email, req in self._by_email.items():
            if req.token == token:
                approved = AccessRequest(email=req.email, status="approved", token=req.token,
                                         requested_at=req.requested_at,
                                         decided_at=datetime.now(timezone.utc))
                self._by_email[email] = approved
                return approved
        return None
