"""(De)serialization between domain objects and JSON/rows. Pure, fully testable."""

from __future__ import annotations

from datetime import date

from paz_rav.contracts import Feature
from paz_rav.strategies.base import Candidate, Leg


def feature_to_json(feature: Feature) -> str:
    return feature.model_dump_json()


def feature_from_json(raw: str | bytes) -> Feature:
    return Feature.model_validate_json(raw)


def _leg_to_dict(leg: Leg) -> dict:
    return {
        "side": leg.side,
        "option_type": leg.option_type,
        "strike": leg.strike,
        "quantity": leg.quantity,
        "expiry": leg.expiry.isoformat() if leg.expiry else None,
        "iv": leg.iv,
    }


def _leg_from_dict(d: dict) -> Leg:
    exp = d.get("expiry")
    return Leg(
        side=d["side"],
        option_type=d["option_type"],
        strike=d["strike"],
        quantity=d.get("quantity", 1),
        expiry=date.fromisoformat(exp) if exp else None,
        iv=d.get("iv"),
    )


def candidate_to_dict(c: Candidate) -> dict:
    """JSON-safe dict (dates -> ISO strings, tuples -> lists)."""
    return {
        "underlying": c.underlying,
        "strategy": c.strategy,
        "dte": c.dte,
        "legs": [_leg_to_dict(leg) for leg in c.legs],
        "credit": c.credit,
        "width": c.width,
        "max_profit": c.max_profit,
        "max_loss": c.max_loss,
        "breakevens": list(c.breakevens),
        "pop": c.pop,
        "score": c.score,
        "meta": dict(c.meta) if c.meta else {},
    }


def candidate_from_dict(d: dict) -> Candidate:
    return Candidate(
        underlying=d["underlying"],
        strategy=d["strategy"],
        dte=d["dte"],
        legs=tuple(_leg_from_dict(leg) for leg in d["legs"]),
        credit=d["credit"],
        width=d["width"],
        max_profit=d["max_profit"],
        max_loss=d["max_loss"],
        breakevens=tuple(d["breakevens"]),
        pop=d.get("pop", 0.0),
        score=d.get("score", 0.0),
        meta=d.get("meta", {}) or {},
    )
