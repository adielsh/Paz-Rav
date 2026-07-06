"""Explainer agent — a plain-language, child-friendly summary of each position.

This is the first AI agent (Phase 2 seed): it takes a fully-computed position and writes
a short explanation a 12-year-old could follow. If ANTHROPIC_API_KEY is set it uses Claude
(Haiku, cheap); otherwise it falls back to a clear deterministic template so the app always
shows something. Results are cached per position to avoid repeat calls.

The agent NEVER computes numbers — it only explains the ones the deterministic core produced.
"""

from __future__ import annotations

import json

from paz_rav.config import get_settings
from paz_rav.store.serialize import candidate_to_dict
from paz_rav.strategies.base import Candidate

_cache: dict[str, str] = {}

_SYSTEM = (
    "אתה מסביר פוזיציות אופציות בעברית פשוטה מאוד, כך שגם ילד בן 12 יבין. "
    "כתוב 3-4 משפטים קצרים בלבד, בלי מונחים מקצועיים מסובכים. "
    "הזכר: את הסטרייקים, את תאריך הפקיעה, כמה אפשר להרוויח וכמה אפשר להפסיד, "
    "ומתי יוצאים (נקודת הסטופ אם קיימת). התחל באימוג'י מתאים. אל תמציא מספרים — "
    "השתמש רק במה שנתון."
)


def _sig(c: Candidate) -> str:
    strikes = "-".join(f"{leg.side[0]}{leg.strike}" for leg in c.legs)
    return f"{c.underlying}:{c.strategy}:{strikes}:{c.dte}"


def _front_expiry(c: Candidate) -> str:
    exps = [leg.expiry for leg in c.legs if leg.expiry]
    return min(exps).isoformat() if exps else f"{c.dte} ימים"


def _template(c: Candidate) -> str:
    u = c.underlying
    if c.strategy == "iron_condor":
        shorts = sorted(leg.strike for leg in c.legs if leg.side == "sell")
        return (
            f"📦 איירון קונדור על {u}. אנחנו מנחשים שהמחיר יישאר בין {shorts[0]:g} ל-{shorts[1]:g} "
            f"עד לתאריך {_front_expiry(c)}. אם זה יקרה — מרוויחים עד {c.max_profit:g}$ למניה. "
            f"אם המחיר יברח החוצה — מפסידים לכל היותר {c.max_loss:g}$. "
            f"הסיכוי להצליח הוא בערך {c.pop * 100:.0f}%."
        )
    if c.strategy == "dacs":
        short = next(leg for leg in c.legs if leg.side == "sell")
        long = next(leg for leg in c.legs if leg.side == "buy")
        stop = c.meta.get("stop_conservative")
        se = short.expiry.isoformat() if short.expiry else "בקרוב"
        le = long.expiry.isoformat() if long.expiry else "חודש אחרי"
        return (
            f"🗓️ DACS על {u}. מוכרים CALL בסטרייק {short.strike:g} שפג ב-{se}, "
            f"וקונים CALL באותו סטרייק שפג ב-{le}. אם המניה תישאר רגועה ולא תעלה מעל {short.strike:g}, "
            f"החלק שמכרנו 'מתאדה' ואנחנו מוכרים את החלק שקנינו ברווח. "
            f"אם המחיר יקפוץ ויתקרב ל-{stop} — יוצאים (סטופ). מתכננים לצאת ברווח כשבועיים לפני הפקיעה."
        )
    return f"פוזיציית {c.strategy} על {u}."


async def _claude(c: Candidate, settings) -> str:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    payload = candidate_to_dict(c)
    msg = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=_SYSTEM,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    )
    return msg.content[0].text.strip()


async def explain(c: Candidate) -> str:
    """Return a cached, child-friendly explanation of the position."""
    sig = _sig(c)
    if sig in _cache:
        return _cache[sig]

    settings = get_settings()
    text = ""
    if settings.anthropic_api_key:
        try:
            text = await _claude(c, settings)
        except Exception:
            text = ""
    if not text:
        text = _template(c)

    _cache[sig] = text
    return text
