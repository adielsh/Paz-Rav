"""(De)serialization between domain objects and JSON/rows. Pure, fully testable."""

from __future__ import annotations

from dataclasses import asdict

from paz_rav.contracts import Feature
from paz_rav.strategies.base import Candidate, Leg


def feature_to_json(feature: Feature) -> str:
    return feature.model_dump_json()


def feature_from_json(raw: str | bytes) -> Feature:
    return Feature.model_validate_json(raw)


def candidate_to_dict(c: Candidate) -> dict:
    """JSON-safe dict (tuples become lists)."""
    return asdict(c)


def candidate_from_dict(d: dict) -> Candidate:
    """Rebuild a Candidate, restoring tuple/Leg types from a JSON-decoded dict."""
    return Candidate(
        underlying=d["underlying"],
        strategy=d["strategy"],
        dte=d["dte"],
        legs=tuple(Leg(**leg) for leg in d["legs"]),
        credit=d["credit"],
        width=d["width"],
        max_profit=d["max_profit"],
        max_loss=d["max_loss"],
        breakevens=tuple(d["breakevens"]),
        pop=d.get("pop", 0.0),
        score=d.get("score", 0.0),
        meta=d.get("meta", {}) or {},
    )
