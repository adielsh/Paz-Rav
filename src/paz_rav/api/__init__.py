"""API module — the BFF + WebSocket gateway (the only thing the browser talks to)."""

from paz_rav.api.app import app

__all__ = ["app"]
