"""Analyst agent — proposes a verdict on a position: take / caution / pass.

Deterministic, rule-based judgment over the pre-computed numbers + regime (it never
computes the numbers itself). When ANTHROPIC_API_KEY is set the explainer already adds a
Claude-written summary; the verdict here stays transparent and rule-driven so it can be
backtested. Returns (verdict, rationale) in Hebrew.
"""

from __future__ import annotations

from paz_rav.contracts import Feature
from paz_rav.strategies.base import Candidate

Verdict = str  # "take" | "caution" | "pass"


def review(c: Candidate, feature: Feature | None) -> tuple[Verdict, str]:
    if c.strategy == "iron_condor":
        return _condor(c, feature)
    if c.strategy == "dacs":
        return _dacs(c, feature)
    if c.score > 0:
        return "caution", "קצה חיובי, אבל אין כלל ייעודי לאסטרטגיה הזו — בזהירות."
    return "pass", "אין קצה חיובי — עדיף לוותר."


def _condor(c: Candidate, feature: Feature | None) -> tuple[Verdict, str]:
    friendly = bool(feature and feature.regime.startswith("range") and feature.regime.endswith("high-vol"))
    if c.score > 0 and c.pop >= 0.70 and friendly:
        return "take", (
            f"סיכוי גבוה ({c.pop * 100:.0f}%) עם קצה חיובי, והמשטר ({feature.regime}) "
            f"מתאים למכירת פרמיה. יחס רווח/סיכון {c.max_profit:g} מול {c.max_loss:g}."
        )
    if c.score > 0 and c.pop >= 0.65:
        return "caution", (
            f"קצה חיובי ו-POP סביר ({c.pop * 100:.0f}%), אבל " +
            ("המשטר לא אידיאלי" if not friendly else "לא מושלם") +
            " — שקול גודל פוזיציה קטן."
        )
    return "pass", (
        f"POP {c.pop * 100:.0f}% והקצה " + ("חלש" if c.score <= 0 else "בינוני") +
        " — עדיף לחכות להזדמנות טובה יותר."
    )


def _dacs(c: Candidate, feature: Feature | None) -> tuple[Verdict, str]:
    fast = float(c.meta.get("fast_ratio", 0.0))
    low_iv = bool(feature and feature.iv_rank < 50)
    if c.score > 0 and fast >= 0.20 and low_iv:
        return "take", (
            f"IV נמוך (מתאים ל-DACS), Fast Ratio יפה ({fast * 100:.0f}%), וקצה חיובי. "
            f"אם הנכס יישאר רגוע — השורט מתאדה ומוכרים את הלונג ברווח."
        )
    if c.score > 0 and fast >= 0.15:
        return "caution", (
            f"Fast Ratio {fast * 100:.0f}% וקצה חיובי, אבל " +
            ("ה-IV לא נמוך מספיק" if not low_iv else "לא מושלם") +
            " — ודא שאין דוח קרוב וש-RSI ~60."
        )
    return "pass", (
        f"Fast Ratio {fast * 100:.0f}% נמוך מדי או שהתזמון לא מתאים — עדיף לוותר."
    )
