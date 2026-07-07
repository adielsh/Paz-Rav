"""Strategic reflection agent — the system analyzing its own track record.

Every other AI touchpoint reasons about *one position, right now*. This one steps back and
asks a different question over the *whole* history: **what is the system doing well, and
what should be tuned?** It reads the accumulated outcomes (closed positions + case memory),
finds patterns, and recommends parameter adjustments — advisory only, never self-tuning.

Three things keep it honest (same spine as the rest of the project):

1. **The numbers are deterministic.** ``aggregate_stats()`` computes every statistic in
   Python — win rate / avg P&L per strategy, close-reason distribution, best/worst buckets.
   The LLM only ever *interprets* that compact summary and phrases recommendations; it never
   computes a stat or invents one.
2. **Bounded by design, so it scales.** The model never sees raw rows — only the aggregates
   (fixed size no matter how much history) plus a short window of recent past reflections.
   This is what lets it work at 10 or 10,000 closed trades without blowing the context.
3. **Minimum sample size.** Below ``MIN_SAMPLE`` closed trades it refuses to pattern-match
   on noise and says so — an honest "not enough data yet" instead of a confident hallucination.

It remembers its own past reflections (persisted via ``ReflectionRepository``): each run is
handed the recent ones, so it can revisit and refine ("last month I flagged DACS in low RSI —
the data since confirms it"). Without an ``ANTHROPIC_API_KEY`` it falls back to a
deterministic, rule-based reflection so the feature always works and tests stay offline.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

MIN_SAMPLE = 10   # below this many closed trades, refuse to pattern-match on noise


@dataclass(frozen=True, slots=True)
class Reflection:
    """One strategic look-back: the computed stats + the agent's interpretation."""

    created_at: datetime
    sample_size: int
    stats: dict                       # the deterministic aggregates the agent reasoned over
    summary: str                      # plain-language read of how the system is doing
    recommendations: list[str] = field(default_factory=list)
    engine: str = "deterministic"     # "llm" | "deterministic"
    enough_data: bool = True


# --------------------------------------------------------------------------- #
# 1. Deterministic aggregation — every statistic computed here, in Python.
# --------------------------------------------------------------------------- #
def _bucket(rows: list[dict], key: str) -> dict[str, dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[str(r.get(key))].append(r)
    out: dict[str, dict] = {}
    for name, items in groups.items():
        pnls = [i["realized_pnl"] for i in items]
        wins = sum(1 for p in pnls if p > 0)
        out[name] = {
            "count": len(items),
            "win_rate": round(wins / len(items), 3) if items else 0.0,
            "avg_pnl": round(sum(pnls) / len(pnls), 3) if pnls else 0.0,
            "total_pnl": round(sum(pnls), 3),
        }
    return out


def aggregate_stats(closed: list) -> dict:
    """Compact, deterministic summary of the closed-position track record.

    ``closed`` is a list of closed ``Position`` objects (realized_pnl set). The output is
    fixed-size regardless of history length — that's what the LLM reasons over, never the
    raw rows.
    """
    rows = [
        {"strategy": p.strategy, "underlying": p.underlying,
         "close_reason": p.close_reason or "manual",
         "realized_pnl": float(p.realized_pnl or 0.0)}
        for p in closed
    ]
    n = len(rows)
    if n == 0:
        return {"sample_size": 0, "overall": {}, "by_strategy": {},
                "by_close_reason": {}, "by_underlying": {}}
    pnls = [r["realized_pnl"] for r in rows]
    wins = sum(1 for p in pnls if p > 0)
    return {
        "sample_size": n,
        "overall": {
            "count": n,
            "win_rate": round(wins / n, 3),
            "avg_pnl": round(sum(pnls) / n, 3),
            "total_pnl": round(sum(pnls), 3),
        },
        "by_strategy": _bucket(rows, "strategy"),
        "by_close_reason": _bucket(rows, "close_reason"),
        "by_underlying": _bucket(rows, "underlying"),
    }


# --------------------------------------------------------------------------- #
# 2. LLM interpretation (real Claude call, forced structured output).
# --------------------------------------------------------------------------- #
_REFLECT_TOOL = {
    "name": "record_reflection",
    "description": "Record a strategic reflection on the system's own track record.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string",
                        "description": "2-4 sentences in Hebrew: how is the system doing, "
                                       "what patterns stand out. Cite the numbers."},
            "recommendations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "2-5 concrete, advisory tuning suggestions in Hebrew, each "
                               "grounded in a statistic (e.g. a parameter to consider "
                               "adjusting, a regime to favour/avoid). Advisory only.",
            },
        },
        "required": ["summary", "recommendations"],
    },
}

_REFLECT_SYS = (
    "אתה אנליסט-על שבוחן את ביצועי המערכת עצמה לאורך זמן. קיבלת סטטיסטיקות מצטברות "
    "(כבר חושבו עבורך) של כל העסקאות שנסגרו, ואת הרפלקציות הקודמות שלך. זהה דפוסים "
    "אמיתיים — מה עובד, מה מפסיד עקבית — והמלץ על כוונונים. הישען אך ורק על המספרים "
    "שניתנו; אל תמציא נתון. אתה מייעץ בלבד — לא משנה קונפיג. אם רפלקציה קודמת העלתה "
    "נקודה, ציין אם הדאטה החדשה מחזקת או סותרת אותה. החזר דרך record_reflection."
)


async def _reflect_llm(stats: dict, past: list, settings) -> tuple[str, list[str]]:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    past_note = "\n".join(f"- {r.summary}" for r in past[:3]) or "(אין רפלקציות קודמות)"
    user = ("סטטיסטיקות מצטברות:\n" + json.dumps(stats, ensure_ascii=False) +
            "\n\nרפלקציות קודמות שלך:\n" + past_note)
    msg = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=700,
        system=_REFLECT_SYS,
        tools=[_REFLECT_TOOL],
        tool_choice={"type": "tool", "name": _REFLECT_TOOL["name"]},
        messages=[{"role": "user", "content": user}],
    )
    for block in msg.content:
        if getattr(block, "type", None) == "tool_use":
            data = dict(block.input)
            return data.get("summary", ""), list(data.get("recommendations", []))
    raise RuntimeError("model returned no tool_use block")


# --------------------------------------------------------------------------- #
# 3. Deterministic fallback — a rule-based reflection so it always answers.
# --------------------------------------------------------------------------- #
def _reflect_fallback(stats: dict) -> tuple[str, list[str]]:
    overall = stats.get("overall", {})
    by_strat = stats.get("by_strategy", {})
    recs: list[str] = []

    # flag the weakest and strongest strategy buckets with a real sample
    graded = [(s, d) for s, d in by_strat.items() if d["count"] >= 3]
    graded.sort(key=lambda kv: kv[1]["avg_pnl"])
    if graded:
        worst_s, worst = graded[0]
        best_s, best = graded[-1]
        if worst["avg_pnl"] < 0:
            recs.append(f"{worst_s}: ממוצע P&L שלילי ({worst['avg_pnl']}) על {worst['count']} "
                        f"עסקאות — שקול להדק תנאי-כניסה או להקטין גודל.")
        if best["avg_pnl"] > 0 and best_s != worst_s:
            recs.append(f"{best_s}: הביצוע החזק ביותר ({best['avg_pnl']} ממוצע, "
                        f"{best['win_rate']:.0%} הצלחה) — שקול להעדיף אותו.")

    # close-reason signal: many stop_losses hint the stop or entry is too aggressive
    cr = stats.get("by_close_reason", {})
    sl = cr.get("stop_loss", {})
    if sl and sl["count"] >= 3 and sl["count"] / max(overall.get("count", 1), 1) > 0.4:
        recs.append(f"סטופ-לוס הוא {sl['count']} מתוך {overall.get('count')} הסגירות — "
                    "ייתכן שהסטופ הדוק מדי או שהכניסות מוקדמות.")

    if not recs:
        recs.append("אין דפוס חריג בולט — המשך לאסוף דאטה לפני כוונון.")

    summary = (
        f"נסגרו {overall.get('count', 0)} עסקאות, שיעור הצלחה {overall.get('win_rate', 0):.0%}, "
        f"ממוצע P&L {overall.get('avg_pnl', 0)}, סה\"כ {overall.get('total_pnl', 0)}. "
        "(רפלקציה דטרמיניסטית — ללא מפתח מודל שפה.)"
    )
    return summary, recs


# --------------------------------------------------------------------------- #
# 4. Public entry point.
# --------------------------------------------------------------------------- #
async def reflect(closed: list, past: list | None = None, settings=None) -> Reflection:
    """Produce a strategic reflection over the closed-trade history.

    ``closed``: closed Position objects. ``past``: recent prior Reflections (for continuity).
    Below MIN_SAMPLE closed trades it returns an honest "not enough data" reflection.
    """
    from paz_rav.config import get_settings

    settings = settings or get_settings()
    past = past or []
    stats = aggregate_stats(closed)
    n = stats["sample_size"]

    if n < MIN_SAMPLE:
        return Reflection(
            created_at=datetime.now(timezone.utc), sample_size=n, stats=stats,
            summary=(f"רק {n} עסקאות סגורות — מתחת לסף המינימלי ({MIN_SAMPLE}) לניתוח אמין. "
                     "אוסף עוד דאטה לפני שאסיק דפוסים."),
            recommendations=[], engine="deterministic", enough_data=False,
        )

    engine = "deterministic"
    if settings.anthropic_api_key:
        try:
            summary, recs = await _reflect_llm(stats, past, settings)
            engine = "llm"
        except Exception:
            summary, recs = _reflect_fallback(stats)
    else:
        summary, recs = _reflect_fallback(stats)

    reflection = Reflection(
        created_at=datetime.now(timezone.utc), sample_size=n, stats=stats,
        summary=summary, recommendations=recs, engine=engine, enough_data=True,
    )
    _maybe_trace(reflection, settings)
    return reflection


def _maybe_trace(reflection: Reflection, settings) -> None:
    """Best-effort Langfuse event for the reflection *run* — the observability copy of the
    LLM call (cost/prompt/output), distinct from the Postgres record the product reads back.
    Silently no-ops without Langfuse keys."""
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return
    try:
        from langfuse import Langfuse

        client = Langfuse(public_key=settings.langfuse_public_key,
                          secret_key=settings.langfuse_secret_key,
                          host=settings.langfuse_host)
        client.create_event(
            trace_context={"trace_id": client.create_trace_id()},
            name="strategic_reflection",
            input=reflection.stats,
            metadata={"sample_size": reflection.sample_size, "engine": reflection.engine,
                      "recommendations": reflection.recommendations},
        )
    except Exception:
        pass


def reflection_to_dict(r: Reflection) -> dict:
    return {
        "created_at": r.created_at.isoformat(),
        "sample_size": r.sample_size,
        "stats": r.stats,
        "summary": r.summary,
        "recommendations": list(r.recommendations),
        "engine": r.engine,
        "enough_data": r.enough_data,
    }


def reflection_from_dict(d: dict) -> Reflection:
    return Reflection(
        created_at=datetime.fromisoformat(d["created_at"]),
        sample_size=d["sample_size"],
        stats=d.get("stats", {}),
        summary=d.get("summary", ""),
        recommendations=list(d.get("recommendations", [])),
        engine=d.get("engine", "deterministic"),
        enough_data=d.get("enough_data", True),
    )
