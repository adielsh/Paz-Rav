"""Close-Timing Advisor — the project's first genuine multi-LLM *decision* call.

Three real Claude calls debate one question about an OPEN position: close now, or hold?

    Analyst  — reads the situation and argues what the position is telling us now
    Critic   — the איפכא-מסתברא: argues the OPPOSITE of the Analyst, on purpose,
               to surface the overlooked risk (or the overlooked opportunity)
    Decider  — weighs both and returns hold | close | reduce, with a confidence

This is deliberately the ONE place a language model is trusted to *reason toward a
decision*, not just phrase one — justified because a close call weighs genuinely
conflicting, contextual signals ("at 48% of max profit, but 9 DTE and spot drifting toward
the short") that a single fixed rule can't. The deterministic rules still run in parallel
(``positions/exit_rules.py`` via the Exit Manager sweep) and are fed to the debate as one
more input — the models argue *around* them, they don't replace them.

The non-negotiable project rule still holds: every NUMBER (unrealized P&L, DTE, distance to
stop, IV rank, recent move) is computed in deterministic Python and handed to the models as
a structured ``Situation``. The models never compute a number — they only weigh the ones
they are given, and each is asked to cite the numbers it leaned on. Structured tool-use
(forced JSON output) is what keeps them grounded: a model literally cannot return free-form
prose, only a stance + reasons.

Cost is bounded by a cache keyed on a coarse *state signature* (``_signature``): repeated
dashboard refreshes in the same market state return the cached debate instantly; a
materially new state (crossed a profit band, DTE dropped a band, spot moved a band, the
exit-rule flag flipped) invalidates it. ``advise(..., force=True)`` bypasses the cache for
an explicit "check now" button.

Graceful fallback: with no ``ANTHROPIC_API_KEY`` the three roles fall back to a
deterministic rule-based debate so the dashboard always shows something and the tests stay
offline and pure — exactly like the Explainer.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any, TypedDict

from paz_rav.positions.base import Position
from paz_rav.positions.exit_rules import ExitConfig, check_exit, mark_to_market

_cache: dict[str, dict] = {}   # position_id -> last result (carries "_sig")

Decision = str  # "hold" | "close" | "reduce"


# --------------------------------------------------------------------------- #
# 1. The deterministic situation — every number computed here, in Python.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Situation:
    """A fully-computed snapshot of an open position — the ONLY thing the models see.

    No field is opinion; every number comes from the quant core or the position itself.
    """

    underlying: str
    strategy: str
    dte: int                                # days to the nearer expiry
    spot: float
    entry_credit: float
    unrealized_pnl: float                   # mark-to-market via the digital-twin valuation
    max_profit: float | None
    pnl_pct_of_max: float | None            # unrealized / max_profit (condor); progress so far
    short_strikes: list[float]
    stop_level: float | None                # strategy-aware danger level
    distance_to_stop: float | None          # signed: >0 = cushion left, <0 = breached
    distance_to_stop_pct: float | None      # as a fraction of spot
    iv_rank: float | None
    regime: str | None
    rsi: float | None
    recent_move_pct: float | None           # spot vs the start of the recent window
    exit_rule_flag: str | None              # what the deterministic exit rule says NOW
    alert: str | None                       # the Exit Manager's standing advisory flag


def _front_dte(position: Position, today: date) -> int:
    exps = [leg.expiry for leg in position.legs if leg.expiry]
    return (min(exps) - today).days if exps else 0


def _stop_info(position: Position, spot: float,
               cfg: ExitConfig) -> tuple[float | None, float | None, list[float]]:
    """(stop_level, signed distance-to-stop, short strikes) — strategy aware.

    Distance is positive while the position is safe and goes negative once the danger
    level is crossed, matching the deterministic exit rule's own breach test.
    """
    if position.strategy == "iron_condor":
        shorts = sorted(leg.strike for leg in position.legs if leg.side == "sell")
        if not shorts:
            return None, None, shorts
        lower, upper = shorts[0], shorts[-1]
        dist = min(spot - lower, upper - spot)   # min cushion to either tested side
        # the "stop level" here is whichever short side spot is closest to
        stop = lower if (spot - lower) <= (upper - spot) else upper
        return stop, dist, shorts
    if position.strategy == "dacs":
        short = next((leg for leg in position.legs if leg.side == "sell"), None)
        if short is None:
            return None, None, []
        stop = short.strike + cfg.dacs_stop_offset   # offset is negative -> below the strike
        return stop, stop - spot, [short.strike]     # >0 while spot is below the stop
    return None, None, []


def build_situation(position: Position, *, spot: float, today: date,
                    feature=None, recent_closes: list[float] | None = None,
                    cfg: ExitConfig | None = None) -> Situation:
    """Assemble the deterministic snapshot the debate reasons over. Pure and testable."""
    cfg = cfg or ExitConfig()
    unrealized = mark_to_market(position, spot, today, cfg.r)
    max_profit = position.meta.get("max_profit")
    max_profit = float(max_profit) if max_profit not in (None, 0) else None
    pnl_pct = (unrealized / max_profit) if max_profit else None

    stop_level, dist, shorts = _stop_info(position, spot, cfg)
    should_close, reason = check_exit(position, spot, today, cfg)

    move_pct = None
    if recent_closes and len(recent_closes) >= 2 and recent_closes[0]:
        move_pct = (spot - recent_closes[0]) / recent_closes[0]

    return Situation(
        underlying=position.underlying,
        strategy=position.strategy,
        dte=_front_dte(position, today),
        spot=round(spot, 2),
        entry_credit=round(position.entry_credit, 4),
        unrealized_pnl=round(unrealized, 4),
        max_profit=round(max_profit, 4) if max_profit else None,
        pnl_pct_of_max=round(pnl_pct, 4) if pnl_pct is not None else None,
        short_strikes=shorts,
        stop_level=round(stop_level, 2) if stop_level is not None else None,
        distance_to_stop=round(dist, 2) if dist is not None else None,
        distance_to_stop_pct=round(dist / spot, 4) if (dist is not None and spot) else None,
        iv_rank=round(feature.iv_rank, 1) if feature is not None else None,
        regime=feature.regime if feature is not None else None,
        rsi=round(feature.rsi, 1) if (feature is not None and feature.rsi is not None) else None,
        recent_move_pct=round(move_pct, 4) if move_pct is not None else None,
        exit_rule_flag=reason if should_close else None,
        alert=position.alert,
    )


# --------------------------------------------------------------------------- #
# 2. The three-role LLM debate (real Claude calls, forced structured output).
# --------------------------------------------------------------------------- #
_STANCE_TOOL = {
    "name": "record_stance",
    "description": "Record your stance on whether to close the open options position now.",
    "input_schema": {
        "type": "object",
        "properties": {
            "stance": {"type": "string", "enum": ["hold", "close", "reduce"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reasons": {
                "type": "array",
                "items": {"type": "string"},
                "description": "2-4 short reasons in Hebrew, each citing a specific number "
                               "from the situation (e.g. 'DTE=9', 'רווח 48% מהמקסימום').",
            },
        },
        "required": ["stance", "confidence", "reasons"],
    },
}

_DECIDE_TOOL = {
    "name": "record_decision",
    "description": "Record the final close/hold decision after weighing both sides.",
    "input_schema": {
        "type": "object",
        "properties": {
            "decision": {"type": "string", "enum": ["hold", "close", "reduce"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "rationale": {"type": "string",
                          "description": "One short paragraph in Hebrew weighing the Analyst "
                                         "and the Critic, grounded in the numbers."},
        },
        "required": ["decision", "confidence", "rationale"],
    },
}

_ANALYST_SYS = (
    "אתה מנהל פוזיציות אופציות ממושמע. קיבלת תמונת-מצב (SITUATION) של פוזיציה פתוחה — "
    "כל המספרים כבר חושבו עבורך (רווח לא-ממומש, DTE, מרחק מהסטופ, IV rank, תנועת מחיר). "
    "טען האם כדאי לסגור עכשיו או להחזיק, אך ורק על סמך המספרים האלה. אל תמציא מספר. "
    "נמק בקצרה בעברית וצטט מספרים קונקרטיים. החזר את עמדתך דרך הכלי record_stance."
)
_CRITIC_SYS = (
    "אתה 'איפכא מסתברא' — עורך הדין של השטן. קיבלת את אותה תמונת-מצב ואת עמדת המנתח. "
    "תפקידך לטעון את ההפך מהמנתח, חזק ככל שהמספרים מאפשרים, כדי לחשוף את הסיכון "
    "(או ההזדמנות) שהוא פספס. אל תמציא מספר — הישען רק על מה שנתון. אם המנתח אמר 'החזק' — "
    "מצא את התרחיש שבו זו טעות, ולהיפך. החזר את עמדתך דרך הכלי record_stance."
)
_DECIDER_SYS = (
    "אתה הסוחר הראשי. קיבלת את תמונת-המצב, את עמדת המנתח, ואת עמדת המבקר. "
    "שקלל את שניהם והכרע: hold (החזק), close (סגור), או reduce (הקטן). "
    "הישען על מספרים בלבד ונמק בפסקה קצרה אחת בעברית. ציין רמת ביטחון. "
    "אתה מייעץ בלבד — המשתמש הוא שמבצע בפועל אצל הברוקר. החזר דרך הכלי record_decision."
)


async def _ask(client, *, system: str, tool: dict, user: str) -> dict:
    """One forced tool-use call — guarantees valid structured output, never free prose."""
    msg = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        system=system,
        tools=[tool],
        tool_choice={"type": "tool", "name": tool["name"]},
        messages=[{"role": "user", "content": user}],
    )
    for block in msg.content:
        if getattr(block, "type", None) == "tool_use":
            return dict(block.input)
    raise RuntimeError("model returned no tool_use block")


async def _debate_llm(sit: Situation, settings) -> dict:
    """Run the three-model debate. Prefers the LangGraph orchestration (real LLM nodes +
    a conditional revision loop); falls back to a plain sequential pass if langgraph isn't
    installed or the graph errors — both return the identical shape to callers."""
    if _graph_available():
        try:
            return await _debate_graph(sit, settings)
        except Exception:
            pass
    return await _debate_sequential(sit, settings)


async def _debate_sequential(sit: Situation, settings) -> dict:
    """The straight-line path: analyst -> critic -> decider, no loop-back."""
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    sit_json = json.dumps(asdict(sit), ensure_ascii=False)

    analyst = await _ask(client, system=_ANALYST_SYS, tool=_STANCE_TOOL,
                         user="SITUATION:\n" + sit_json)
    critic = await _ask(
        client, system=_CRITIC_SYS, tool=_STANCE_TOOL,
        user=("SITUATION:\n" + sit_json +
              "\n\nעמדת המנתח:\n" + json.dumps(analyst, ensure_ascii=False)),
    )
    decision = await _ask(
        client, system=_DECIDER_SYS, tool=_DECIDE_TOOL,
        user=("SITUATION:\n" + sit_json +
              "\n\nמנתח:\n" + json.dumps(analyst, ensure_ascii=False) +
              "\n\nמבקר:\n" + json.dumps(critic, ensure_ascii=False)),
    )
    return {
        "decision": decision.get("decision", "hold"),
        "confidence": decision.get("confidence"),
        "rationale": decision.get("rationale", ""),
        "analyst": analyst,
        "critic": critic,
        "revisions": 0,
        "orchestration": "sequential",
    }


# --------------------------------------------------------------------------- #
# 2b. The LangGraph orchestration — real LLM nodes with a conditional loop.
#
# This is where LangGraph genuinely earns its place: it drives *language-model*
# calls (not rule nodes) through a branching graph. The graph is
#   analyst -> critic -> decider -> (if the Decider's confidence < 0.5 AND we
#   haven't revised yet: loop back to the Analyst, handing it the Critic's
#   objection to reconsider, once) -> done
# A single agent wouldn't need a graph; three agents with a conditional revision
# do. Everything degrades to `_debate_sequential` when langgraph isn't installed.
# --------------------------------------------------------------------------- #
_REVISE_CONFIDENCE = 0.5   # a shaky Decider verdict triggers exactly one reconsideration


class DebateState(TypedDict, total=False):
    sit_json: str
    client: Any            # AsyncAnthropic — travels in state, never serialized
    analyst: dict
    critic: dict
    decision: dict
    revisions: int
    focus: str             # the Critic's objection, fed back into a revising Analyst
    loop: bool


async def _g_analyst(state: DebateState) -> DebateState:
    prompt = "SITUATION:\n" + state["sit_json"]
    if state.get("revisions", 0) > 0 and state.get("focus"):
        prompt += ("\n\nשקול מחדש לאור התנגדות המבקר (אל תתעלם ממנה):\n" + state["focus"])
    analyst = await _ask(state["client"], system=_ANALYST_SYS, tool=_STANCE_TOOL, user=prompt)
    return {"analyst": analyst}


async def _g_critic(state: DebateState) -> DebateState:
    user = ("SITUATION:\n" + state["sit_json"] +
            "\n\nעמדת המנתח:\n" + json.dumps(state["analyst"], ensure_ascii=False))
    critic = await _ask(state["client"], system=_CRITIC_SYS, tool=_STANCE_TOOL, user=user)
    return {"critic": critic}


async def _g_decider(state: DebateState) -> DebateState:
    user = ("SITUATION:\n" + state["sit_json"] +
            "\n\nמנתח:\n" + json.dumps(state["analyst"], ensure_ascii=False) +
            "\n\nמבקר:\n" + json.dumps(state["critic"], ensure_ascii=False))
    decision = await _ask(state["client"], system=_DECIDER_SYS, tool=_DECIDE_TOOL, user=user)
    rev = state.get("revisions", 0)
    conf = decision.get("confidence")
    conf = conf if conf is not None else 1.0
    loop = conf < _REVISE_CONFIDENCE and rev == 0
    out: DebateState = {"decision": decision, "loop": loop}
    if loop:   # send it back to the Analyst once, with the Critic's objection to chew on
        out["revisions"] = rev + 1
        out["focus"] = " · ".join(state.get("critic", {}).get("reasons", []))
    return out


def _g_route(state: DebateState) -> str:
    return "analyst" if state.get("loop") else "done"


_debate_graph_compiled = None


def _graph_available() -> bool:
    try:
        import langgraph  # noqa: F401
        return True
    except Exception:
        return False


def _build_debate_graph():
    from langgraph.graph import END, StateGraph

    g = StateGraph(DebateState)
    g.add_node("analyst", _g_analyst)
    g.add_node("critic", _g_critic)
    g.add_node("decider", _g_decider)
    g.set_entry_point("analyst")
    g.add_edge("analyst", "critic")
    g.add_edge("critic", "decider")
    g.add_conditional_edges("decider", _g_route, {"analyst": "analyst", "done": END})
    return g.compile()


async def _debate_graph(sit: Situation, settings) -> dict:
    from anthropic import AsyncAnthropic

    global _debate_graph_compiled
    if _debate_graph_compiled is None:
        _debate_graph_compiled = _build_debate_graph()

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    state = await _debate_graph_compiled.ainvoke({
        "sit_json": json.dumps(asdict(sit), ensure_ascii=False),
        "client": client, "revisions": 0,
    })
    d = state["decision"]
    return {
        "decision": d.get("decision", "hold"),
        "confidence": d.get("confidence"),
        "rationale": d.get("rationale", ""),
        "analyst": state["analyst"],
        "critic": state["critic"],
        "revisions": state.get("revisions", 0),
        "orchestration": "langgraph",
    }


# --------------------------------------------------------------------------- #
# 3. Deterministic fallback — a rule-based "debate" so the app always answers.
# --------------------------------------------------------------------------- #
def _debate_fallback(sit: Situation) -> dict:
    """Mirror the LLM shape using the same numbers, purely by rule. No network, no key."""
    flagged = sit.exit_rule_flag is not None
    near_stop = sit.distance_to_stop_pct is not None and sit.distance_to_stop_pct <= 0.01
    rich_profit = sit.pnl_pct_of_max is not None and sit.pnl_pct_of_max >= 0.50

    if flagged or near_stop:
        a_stance, a_conf = "close", 0.7
        a_reasons = [f"כלל היציאה מסמן: {sit.exit_rule_flag or 'קרוב לסטופ'}",
                     f"מרחק מהסטופ: {sit.distance_to_stop} ({sit.short_strikes})"]
    elif rich_profit:
        a_stance, a_conf = "close", 0.6
        a_reasons = [f"נלכד רווח של {sit.pnl_pct_of_max:.0%} מהמקסימום — שקול לממש",
                     f"DTE={sit.dte}"]
    else:
        a_stance, a_conf = "hold", 0.6
        a_reasons = [f"אין טריגר יציאה; רווח לא-ממומש {sit.unrealized_pnl}",
                     f"מרחק מהסטופ {sit.distance_to_stop}, DTE={sit.dte}"]

    # the "critic" argues the opposite corner, grounded in the same numbers
    if a_stance == "close":
        c_stance = "hold"
        c_reasons = [f"עדיין יש כרית ביטחון (מרחק {sit.distance_to_stop}) ו-DTE={sit.dte}",
                     "סגירה מוקדמת מוותרת על ערך-זמן שעוד עשוי להתאדות"]
    else:
        c_stance = "close"
        c_reasons = [f"תנועת מחיר אחרונה {sit.recent_move_pct}; משטר {sit.regime}",
                     "רווח על השולחן יכול להימחק בקפיצת תנודתיות אחת"]

    decision = a_stance
    conf = round((a_conf + (1 - 0.5)) / 2, 2)
    rationale = (
        f"על סמך המספרים: DTE={sit.dte}, רווח לא-ממומש {sit.unrealized_pnl}"
        + (f" ({sit.pnl_pct_of_max:.0%} מהמקסימום)" if sit.pnl_pct_of_max is not None else "")
        + f", מרחק מהסטופ {sit.distance_to_stop}. "
        + ("כלל היציאה הדטרמיניסטי פעיל — ההטיה לסגירה." if flagged
           else "אין טריגר יציאה — ההטיה להחזקה, בכפוף לניהול סיכון.")
        + " (הערכה דטרמיניסטית — ללא מפתח מודל שפה.)"
    )
    return {
        "decision": decision, "confidence": conf, "rationale": rationale,
        "analyst": {"stance": a_stance, "confidence": a_conf, "reasons": a_reasons},
        "critic": {"stance": c_stance, "confidence": 0.5, "reasons": c_reasons},
        "revisions": 0, "orchestration": "deterministic",
    }


# --------------------------------------------------------------------------- #
# 4. Cache signature + public entry point.
# --------------------------------------------------------------------------- #
def _signature(sit: Situation) -> str:
    """Coarse bands so ordinary refreshes hit the cache, but a material move busts it."""
    pnl = round(sit.pnl_pct_of_max, 2) if sit.pnl_pct_of_max is not None else None
    dist = round(sit.distance_to_stop_pct, 2) if sit.distance_to_stop_pct is not None else None
    return f"{sit.dte // 2}:{pnl}:{dist}:{sit.exit_rule_flag}:{sit.alert}:{sit.regime}"


def _maybe_trace(position: Position, sit: Situation, result: dict) -> None:
    """Best-effort Langfuse event on the position's original opening trace (the closed
    feedback loop): the close-timing debate is recorded against the same decision the
    committee produced at open. Silently no-ops without Langfuse keys."""
    from paz_rav.config import get_settings

    s = get_settings()
    if not (s.langfuse_public_key and s.langfuse_secret_key):
        return
    try:
        from langfuse import Langfuse

        client = Langfuse(public_key=s.langfuse_public_key, secret_key=s.langfuse_secret_key,
                          host=s.langfuse_host)
        ctx = ({"trace_id": position.langfuse_trace_id}
               if position.langfuse_trace_id else {"trace_id": client.create_trace_id()})
        client.create_event(
            trace_context=ctx,
            name="close_advice",
            input=asdict(sit),
            metadata={"decision": result.get("decision"),
                      "confidence": result.get("confidence"),
                      "engine": result.get("engine")},
        )
    except Exception:
        pass


async def _debate_remote(sit: Situation, settings) -> dict:
    """Call the extracted advisor microservice over HTTP (paz_rav/services/advisor)."""
    import httpx

    url = settings.advisor_url.rstrip("/") + "/advise"
    async with httpx.AsyncClient(timeout=settings.advisor_timeout) as client:
        resp = await client.post(url, json={"situation": asdict(sit)})
        resp.raise_for_status()
        return resp.json()


async def _resolve_debate(sit: Situation, settings) -> dict:
    """Pick where the debate runs, most-specific first, each degrading to the next:
    remote advisor service -> in-process LLM debate -> deterministic rule-based debate.

    The remote path is a small circuit breaker: any failure (service down, timeout, 5xx)
    falls back to running the debate in-process, so a broken advisor never takes the
    dashboard down with it. This is exactly the seam that lets the LLM layer be extracted
    to its own deployable (docs/ARCHITECTURE.md) without the monolith depending on it.
    """
    if settings.advisor_url:
        try:
            r = await _debate_remote(sit, settings)
            r.setdefault("served_by", "advisor-service")
            return r
        except Exception:
            pass   # circuit breaker -> run it here instead
    if settings.anthropic_api_key:
        try:
            r = await _debate_llm(sit, settings)
            r["engine"] = "llm"
            return r
        except Exception:
            pass
    r = _debate_fallback(sit)
    r["engine"] = "deterministic"
    return r


async def advise(position: Position, *, spot: float, today: date, feature=None,
                 recent_closes: list[float] | None = None, force: bool = False,
                 cfg: ExitConfig | None = None) -> dict:
    """Run (or return a cached) close-timing debate for one open position.

    Returns a JSON-safe dict: ``decision`` (hold|close|reduce), ``confidence``,
    ``rationale`` (Hebrew), ``analyst``/``critic`` stances, the deterministic
    ``situation`` numbers, ``engine`` ("llm" | "deterministic") and ``computed_at``.
    """
    from paz_rav.config import get_settings

    sit = build_situation(position, spot=spot, today=today, feature=feature,
                          recent_closes=recent_closes, cfg=cfg)
    sig = _signature(sit)
    cached = _cache.get(position.id)
    if cached is not None and cached.get("_sig") == sig and not force:
        return cached

    settings = get_settings()
    result = await _resolve_debate(sit, settings)
    result["situation"] = asdict(sit)
    result["computed_at"] = datetime.now(timezone.utc).isoformat()
    result["_sig"] = sig
    _maybe_trace(position, sit, result)
    _cache[position.id] = result
    return result
