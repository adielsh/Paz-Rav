"""Explainer — a plain-language, precise summary of each position.

Deterministic by design. It used to call an LLM (Haiku) to phrase this in free text, but a
small model writing prose *that contains numbers* risks stating them slightly wrong — the
one thing this project refuses to allow. So the explanation is now a fixed, exact template
built straight from the computed figures: always correct, always consistent, clear to a
non-expert. (The genuine LLM reasoning lives in the close-timing debate, where models weigh
numbers toward a decision — never restate them as prose.)

Dollar figures on a Candidate are per share; a standard contract is ×100, so we show the
real per-contract dollars here. Cached per position signature.
"""

from __future__ import annotations

from paz_rav.strategies.base import Candidate

_cache: dict[str, str] = {}

CONTRACT_MULTIPLIER = 100  # US equity/index options: 1 contract = 100 shares


def _usd(per_share: float) -> str:
    """Per-share premium/P&L -> real per-contract dollars, e.g. 9.55 -> '$955'."""
    dollars = per_share * CONTRACT_MULTIPLIER
    return f"${dollars:,.0f}" if abs(dollars) >= 100 else f"${dollars:,.2f}"


def _lvl(strike: float) -> str:
    """A price level (strike/breakeven) — NOT multiplied by the contract size."""
    return f"${strike:,.0f}" if strike >= 100 else f"${strike:,.2f}"


def _sig(c: Candidate) -> str:
    strikes = "-".join(f"{leg.side[0]}{leg.strike}" for leg in c.legs)
    return f"{c.underlying}:{c.strategy}:{strikes}:{c.dte}"


def _front_expiry(c: Candidate) -> str:
    exps = [leg.expiry for leg in c.legs if leg.expiry]
    return min(exps).isoformat() if exps else f"{c.dte} ימים"


def _condor(c: Candidate) -> str:
    u = c.underlying
    shorts = sorted(leg.strike for leg in c.legs if leg.side == "sell")
    return (
        f"📦 איירון קונדור על {u}. הרעיון: שהמחיר יישאר בין {_lvl(shorts[0])} ל-{_lvl(shorts[1])} "
        f"עד {_front_expiry(c)}. אם כן — הרווח המרבי הוא {_usd(c.max_profit)} לחוזה. "
        f"אם המחיר יברח מהטווח — ההפסד המרבי הוא {_usd(c.max_loss)} לחוזה. "
        f"הסיכוי להצליח מוערך ב-{c.pop * 100:.0f}%, ונקודות האיזון הן "
        f"{' ו-'.join(_lvl(b) for b in c.breakevens)}."
    )


def _dacs(c: Candidate) -> str:
    u = c.underlying
    short = next(leg for leg in c.legs if leg.side == "sell")
    long = next(leg for leg in c.legs if leg.side == "buy")
    stop = c.meta.get("stop_conservative")
    se = short.expiry.isoformat() if short.expiry else "בקרוב"
    le = long.expiry.isoformat() if long.expiry else "חודש אחרי"
    debit = abs(c.credit)
    stop_txt = f" אם המחיר מתקרב ל-{_lvl(float(stop))} — יוצאים (סטופ)." if stop is not None else ""
    return (
        f"🗓️ DACS על {u}. מוכרים CALL בסטרייק {_lvl(short.strike)} שפג ב-{se}, "
        f"וקונים CALL באותו סטרייק שפג ב-{le}, בעלות (debit) של {_usd(debit)} לחוזה. "
        f"אם המניה תישאר רגועה ולא תעלה מעל {_lvl(short.strike)} — החלק שמכרנו 'מתאדה' "
        f"ומוכרים את החלק שקנינו ברווח.{stop_txt} מתכננים לצאת כשבועיים לפני הפקיעה."
    )


def _template(c: Candidate) -> str:
    if c.strategy == "iron_condor":
        return _condor(c)
    if c.strategy == "dacs":
        return _dacs(c)
    return f"פוזיציית {c.strategy} על {c.underlying}."


async def explain(c: Candidate) -> str:
    """Return a cached, precise, plain-language explanation (deterministic — no LLM)."""
    sig = _sig(c)
    if sig not in _cache:
        _cache[sig] = _template(c)
    return _cache[sig]
