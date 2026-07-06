"""Notify the owner a new email is asking for access — one Gmail SMTP call.

Uses Python's stdlib smtplib against Gmail (an App Password, not the real account
password) rather than a transactional-email service — no new external dependency for
something this occasional. A no-op when GMAIL_APP_PASSWORD isn't set: the access
request is still recorded, you'd just need another way to notice it (e.g. checking
Postgres directly).
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from paz_rav.config import get_settings

log = logging.getLogger("paz_rav.notify")


def _send_sync(to_addr: str, subject: str, body: str) -> None:
    settings = get_settings()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.gmail_address
    msg["To"] = to_addr
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(settings.gmail_address, settings.gmail_app_password)
        server.send_message(msg)


async def notify_access_request(requester_email: str, token: str) -> None:
    """Emails the owner (ALLOWED_EMAIL) an approve link for a new pending request.
    Best-effort: logs and swallows any failure rather than breaking the sign-in flow
    that triggered it — a lost notification shouldn't 500 the requester's browser.
    """
    settings = get_settings()
    if not settings.gmail_app_password or not settings.allowed_email:
        log.info("access request from %s recorded, but GMAIL_APP_PASSWORD is not set "
                  "— no notification sent", requester_email)
        return
    base = settings.public_base_url.rstrip("/")
    link = f"{base}/admin/approve?token={token}" if base else f"/admin/approve?token={token} (set PUBLIC_BASE_URL for a full link)"
    body = (
        f"{requester_email} is asking for access to Paz Rav.\n\n"
        f"Approve by opening:\n{link}\n\n"
        f"If this wasn't you or someone you trust, just ignore this email — nothing "
        f"happens until that link is opened."
    )
    try:
        await asyncio.to_thread(_send_sync, settings.allowed_email,
                                "Paz Rav — access request", body)
    except Exception:
        log.exception("failed to send access-request notification for %s", requester_email)
