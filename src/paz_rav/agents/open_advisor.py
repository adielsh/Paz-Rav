"""Open-Timing Advisor — the same three-model debate, pointed at *entry* instead of exit.

On demand (a button on a candidate), three real Claude calls argue whether to open it NOW:

    Analyst — reads the computed setup and argues open vs. wait
    Critic  — the איפכא-מסתברא: argues the opposite, to surface what was missed
    Decider — weighs both and returns open | wait | skip, with a confidence

The fast, always-on filter stays the deterministic rule committee (analyst.py/critic.py —
every candidate, every scan, zero cost). This debate is the *deep* second opinion the user
explicitly requests for one candidate, so real LLM spend is justified and bounded: cached by
a coarse setup signature, advisory only, and every number it sees was computed by the quant
core (``OpenSituation``). Structured tool-use means a model cannot invent a figure — same
honesty contract as agents/close_advisor.py, whose ``_ask`` helper this reuses.

Case memory closes the loop here too: the debate recalls how similar *closed* trades ended,
so the Decider leans on the trader's own history before a dollar is committed.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from paz_rav.agents.close_advisor import _DECIDE_TOOL, _STANCE_TOOL, _ask, _memory_note
from paz_rav.strategies.base import Candidate

_cache: dict[str, dict] = {}   # candidate signature -> last result


# --------------------------------------------------------------------------- #
# 1. The deterministic setup — every number computed by the quant core.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class OpenSituation:
    """A fully-computed snapshot of a candidate — the ONLY thing the models see."""

    underlying: str
    strategy: str
    dte: int
    spot: float | None
    credit: float                 # per share; negative = debit
    max_profit: float
    max_loss: float
    pop: float
    score: float
    short_strikes: list[float]
    short_deltas: list[float]     # signed deltas of the short legs (empty if unknown)
    breakevens: list[float]
    expected_move: float | None   # $ move to the front expiry (from the Feature)
    iv_rank: float | None
    regime: str | None
    rsi: float | None
    fast_ratio: float | None      # DACS only
    committee_verdict: str        # the deterministic rule committee's take/caution/pass


def build_open_situation(c: Candidate, feature=None, verdict: str = "") -> OpenSituation:
    shorts = [leg for leg in c.legs if leg.side == "sell"]
    fast = c.meta.get("fast_ratio")
    spot = c.meta.get("spot")
    return OpenSituation(
        underlying=c.underlying,
        strategy=c.strategy,
        dte=c.dte,
        spot=float(spot) if spot is not None else (feature.spot if feature else None),
        credit=round(c.credit, 4),
        max_profit=round(c.max_profit, 4),
        max_loss=round(c.max_loss, 4),
        pop=round(c.pop, 4),
        score=round(c.score, 6),
        short_strikes=[leg.strike for leg in shorts],
        short_deltas=[round(leg.delta, 3) for leg in shorts if leg.delta is not None],
        breakevens=list(c.breakevens),
        expected_move=round(feature.expected_move, 2) if feature else None,
        iv_rank=round(feature.iv_rank, 1) if feature else None,
        regime=feature.regime if feature else None,
        rsi=round(feature.rsi, 1) if (feature and feature.rsi is not None) else None,
        fast_ratio=round(float(fast), 3) if fast is not None else None,
        committee_verdict=verdict,
    )


# --------------------------------------------------------------------------- #
# 2. The debate — same forced-JSON contract as the close advisor.
# --------------------------------------------------------------------------- #
_ANALYST_SYS = (
    "אתה סוחר אופציות ממושמע ששוקל האם לפתוח עסקה עכשיו. קיבלת SETUP מחושב "
    "(קרדיט, רווח/הפסד מקס, POP, דלתות השורטים, תנועה צפויה, IV rank, משטר) — כל "
    "המספרים כבר חושבו. טען האם לפתוח עכשיו או להמתין, אך ורק על סמך המספרים. "
    "אל תמציא מספר. שים לב במיוחד ליחס בין התנועה הצפויה למרחק הסטרייקים. "
    "השתמש ב-stance כך: hold=פתח, close=ותר, reduce=המתן/גודל קטן. החזר דרך record_stance."
)
_CRITIC_SYS = (
    "אתה 'איפכא מסתברא' לעסקה חדשה. קיבלת SETUP מחושב ואת עמדת המנתח. טען את ההפך "
    "ממנו, חזק ככל שהמספרים מאפשרים: אם אמר לפתוח — מצא את התרחיש שממוטט את העסקה; "
    "אם אמר להמתין — טען מה הולך לאיבוד בהמתנה. אל תמציא מספר. "
    "stance: hold=פתח, close=ותר, reduce=המתן. החזר דרך record_stance."
)
_DECIDER_SYS = (
    "אתה הסוחר הראשי. קיבלת SETUP מחושב של עסקה מוצעת, את עמדת המנתח ואת עמדת המבקר. "
    "הכרע: hold=פתח עכשיו, reduce=המתן או פתח בגודל קטן, close=ותר על העסקה. "
    "הישען על מספרים בלבד ונמק בפסקה קצרה בעברית עם רמת ביטחון. אתה מייעץ בלבד — "
    "המשתמש מבצע בברוקר. החזר דרך record_decision."
)

# the tools force hold/close/reduce; map them onto entry language for callers
_DECISION_MAP = {"hold": "open", "close": "skip", "reduce": "wait"}


async def _debate_llm(sit: OpenSituation, settings, mem_note: str) -> dict:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    sit_json = json.dumps(asdict(sit), ensure_ascii=False)
    if mem_note:
        sit_json += "\n\nזיכרון מקרים (עסקאות דומות שנסגרו):\n" + mem_note

    analyst = await _ask(client, system=_ANALYST_SYS, tool=_STANCE_TOOL,
                         user="SETUP:\n" + sit_json)
    critic = await _ask(client, system=_CRITIC_SYS, tool=_STANCE_TOOL,
                        user=("SETUP:\n" + sit_json +
                              "\n\nעמדת המנתח:\n" + json.dumps(analyst, ensure_ascii=False)))
    decision = await _ask(client, system=_DECIDER_SYS, tool=_DECIDE_TOOL,
                          user=("SETUP:\n" + sit_json +
                                "\n\nמנתח:\n" + json.dumps(analyst, ensure_ascii=False) +
                                "\n\nמבקר:\n" + json.dumps(critic, ensure_ascii=False)))
    return {
        "decision": _DECISION_MAP.get(decision.get("decision", "reduce"), "wait"),
        "confidence": decision.get("confidence"),
        "rationale": decision.get("rationale", ""),
        "analyst": {**analyst, "stance": _DECISION_MAP.get(analyst.get("stance", ""), "wait")},
        "critic": {**critic, "stance": _DECISION_MAP.get(critic.get("stance", ""), "wait")},
    }


def _debate_fallback(sit: OpenSituation) -> dict:
    """Rule-based mirror of the debate shape — no key, no network, still grounded."""
    good_pop = sit.pop >= 0.70
    positive_edge = sit.score > 0
    em_ok = True
    if sit.expected_move is not None and sit.spot and sit.short_strikes:
        # is the nearest short strike outside the expected move?
        nearest = min(abs(s - sit.spot) for s in sit.short_strikes)
        em_ok = nearest > sit.expected_move

    if positive_edge and good_pop and em_ok:
        decision, conf = "open", 0.65
        a_reasons = [f"POP {sit.pop:.0%} וקצה חיובי (score {sit.score})",
                     "הסטרייקים הקצרים מחוץ לתנועה הצפויה"]
    elif positive_edge and (good_pop or em_ok):
        decision, conf = "wait", 0.55
        a_reasons = [f"POP {sit.pop:.0%}; תנאים חלקיים — עדיף גודל קטן או המתנה",
                     f"ורדיקט הוועדה: {sit.committee_verdict or '—'}"]
    else:
        decision, conf = "skip", 0.6
        a_reasons = [f"score {sit.score} / POP {sit.pop:.0%} לא מספיקים",
                     f"ורדיקט הוועדה: {sit.committee_verdict or '—'}"]

    c_reasons = (["תנועה חדה אחת מוחקת את הקרדיט — בדוק אירועי מאקרו קרובים"]
                 if decision == "open"
                 else ["המתנה מוותרת על דעיכת הזמן שכבר עובדת לטובתך"])
    rationale = (
        f"על סמך המספרים: POP {sit.pop:.0%}, קרדיט {sit.credit}, הפסד מקס {sit.max_loss}"
        + (f", תנועה צפויה ±{sit.expected_move}" if sit.expected_move is not None else "")
        + ". (הערכה דטרמיניסטית — ללא מפתח מודל שפה.)"
    )
    return {
        "decision": decision, "confidence": conf, "rationale": rationale,
        "analyst": {"stance": decision, "confidence": conf, "reasons": a_reasons},
        "critic": {"stance": "wait" if decision == "open" else "open",
                   "confidence": 0.5, "reasons": c_reasons},
    }


# --------------------------------------------------------------------------- #
# 3. Cache + public entry point.
# --------------------------------------------------------------------------- #
def _signature(sit: OpenSituation) -> str:
    return (f"{sit.underlying}:{sit.strategy}:{sit.short_strikes}:{sit.dte}"
            f":{round(sit.pop, 2)}:{sit.regime}")


async def _recall(sit: OpenSituation, memory) -> list:
    """Similar closed trades for this setup (best-effort, never blocks the debate)."""
    if memory is None:
        return []
    try:
        from paz_rav.store.case_memory import vectorize

        vec = vectorize(strategy=sit.strategy, dte=sit.dte, pnl_pct_of_max=0.0,
                        distance_to_stop_pct=None, iv_rank=sit.iv_rank, rsi=sit.rsi,
                        recent_move_pct=None, regime=sit.regime)
        return await memory.similar(vec, strategy=sit.strategy, k=5)
    except Exception:
        return []


async def advise_open(c: Candidate, *, feature=None, verdict: str = "",
                      memory=None, force: bool = False) -> dict:
    """Run (or return a cached) open-timing debate for one candidate.

    Returns: ``decision`` (open|wait|skip), ``confidence``, ``rationale``,
    ``analyst``/``critic`` stances, ``recalled`` similar closed trades, the
    deterministic ``situation`` numbers, ``engine`` and ``computed_at``.
    """
    from paz_rav.config import get_settings

    sit = build_open_situation(c, feature=feature, verdict=verdict)
    sig = _signature(sit)
    cached = _cache.get(sig)
    if cached is not None and not force:
        return cached

    settings = get_settings()
    recalled = await _recall(sit, memory)
    if settings.anthropic_api_key:
        try:
            result = await _debate_llm(sit, settings, _memory_note(recalled))
            result["engine"] = "llm"
        except Exception:
            result = _debate_fallback(sit)
            result["engine"] = "deterministic"
    else:
        result = _debate_fallback(sit)
        result["engine"] = "deterministic"

    result["recalled"] = [
        {"summary": n.case.summary, "similarity": round(n.similarity, 3),
         "won": n.case.won, "realized_pnl": n.case.realized_pnl}
        for n in recalled
    ]
    result["situation"] = asdict(sit)
    result["computed_at"] = datetime.now(timezone.utc).isoformat()
    _cache[sig] = result
    return result
