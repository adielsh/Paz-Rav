"""Critic agent — the adversarial bear case for every position.

Its whole job is to argue *against* the trade, so the trader sees the risk before opening.
Deterministic and strategy-specific; returns the objection in Hebrew.
"""

from __future__ import annotations

from paz_rav.contracts import Feature
from paz_rav.strategies.base import Candidate


def objection(c: Candidate, feature: Feature | None) -> str:
    if c.strategy == "iron_condor":
        shorts = sorted(leg.strike for leg in c.legs if leg.side == "sell")
        exps = [leg.expiry for leg in c.legs if leg.expiry]
        exp = min(exps).isoformat() if exps else f"{c.dte} ימים"
        return (
            f"⚠️ הסיכון: תנועה חדה או קפיצת תנודתיות שתוציא את המחיר מהטווח "
            f"{shorts[0]:g}–{shorts[1]:g} עד {exp} — הפסד של עד {c.max_loss:g}$ למניה. "
            f"אירוע מאקרו, גאפ בפתיחה או ראלי חד הם האויב. אל תיישן על השמירה."
        )
    if c.strategy == "dacs":
        short = next(leg for leg in c.legs if leg.side == "sell")
        stop = c.meta.get("stop_conservative", short.strike - 5)
        return (
            f"⚠️ הסיכון: עליה גדולה מעל {short.strike:g} לפני הפקיעה — זה התרחיש היחיד שכואב. "
            f"גם קפיצת IV (בגלל דוח!) יכולה להעיף את השורט. אם המחיר עובר את {stop} — "
            f"יוצאים מיד, בלי להתמקח."
        )
    return "⚠️ שקול את הסיכון לפני הפתיחה."
