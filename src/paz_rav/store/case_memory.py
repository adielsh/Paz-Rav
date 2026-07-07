"""Case memory — "how did trades like this one end?"

The learning layer the ROADMAP calls case-memory (RAG-lite). When the close-timing debate
runs, it can recall the *k* most similar *closed* positions and hand their real outcomes to
the models as context — so the Decider leans on your own history, not just the current
snapshot. This is what turns "I built a debate" into "I built a system that learns from its
own trades."

**The deterministic line holds, deliberately.** A case's vector is NOT an LLM text
embedding — it's a fixed-length, deterministic feature vector built straight from the
numbers the quant core already computed (`vectorize()`). Similar market states sit close in
that space; retrieval is plain cosine similarity. The models still only ever *reason over*
computed numbers — now including the outcomes of past cases — never invent one. (Because the
vector is deterministic, it's also fully testable offline, with no embedding API.)

Storage sits behind a Protocol like everything else: an in-memory implementation (default,
tests) and a pgvector-backed Postgres one (`store/postgres_case_memory.py`). Retrieval
degrades gracefully to "no cases" everywhere, so the debate always runs — with memory when
it's there, without when it isn't.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

# Fixed feature layout — order is the contract; never reorder, only append (a new dim must
# go at the end so existing stored vectors stay meaningful). Keep VECTOR_DIM in sync.
_STRATEGIES = ("iron_condor", "dacs")
_REGIME_KEYS = ("range", "trend", "high-vol", "low-vol")
VECTOR_DIM = 6 + len(_STRATEGIES) + len(_REGIME_KEYS)   # 12


@dataclass(frozen=True, slots=True)
class Case:
    """A closed position reduced to (deterministic vector, real outcome)."""

    position_id: str
    underlying: str
    strategy: str
    vector: tuple[float, ...]
    realized_pnl: float
    close_reason: str | None
    won: bool
    summary: str        # short human/LLM-readable recap, e.g. "IC QQQ · +12.5 · profit_target"


@dataclass(frozen=True, slots=True)
class Neighbor:
    case: Case
    similarity: float   # cosine, 1.0 = identical state


def _clip(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def vectorize(*, strategy: str, dte: int | None, pnl_pct_of_max: float | None,
              distance_to_stop_pct: float | None, iv_rank: float | None,
              rsi: float | None, recent_move_pct: float | None,
              regime: str | None) -> tuple[float, ...]:
    """Deterministic, normalized feature vector for a market state. Same inputs the
    close-timing ``Situation`` carries — so a live situation and a stored case live in the
    same space and are directly comparable. All dims roughly in [-1, 1]."""
    dte_n = _clip((dte or 0) / 60.0)                       # ~0..1 over a typical hold
    pnl_n = _clip(pnl_pct_of_max if pnl_pct_of_max is not None else 0.0)
    dist_n = _clip((distance_to_stop_pct or 0.0) * 10.0)   # ±10% -> ±1
    iv_n = _clip(((iv_rank or 50.0) - 50.0) / 50.0)        # 0..100 -> -1..1
    rsi_n = _clip(((rsi if rsi is not None else 50.0) - 50.0) / 50.0)
    move_n = _clip((recent_move_pct or 0.0) * 10.0)        # ±10% -> ±1

    strat = [1.0 if strategy == s else 0.0 for s in _STRATEGIES]
    reg = (regime or "").lower()
    regime_vec = [1.0 if key in reg else 0.0 for key in _REGIME_KEYS]

    return tuple([dte_n, pnl_n, dist_n, iv_n, rsi_n, move_n, *strat, *regime_vec])


def cosine(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class CaseMemory(Protocol):
    """Durable memory of closed cases, queried by market-state similarity."""

    async def add(self, case: Case) -> None: ...

    async def similar(self, vector: tuple[float, ...], *, strategy: str | None = None,
                      k: int = 5) -> list[Neighbor]: ...

    async def count(self) -> int: ...


class InMemoryCaseMemory:
    """Default implementation (and the one tests use) — a plain list + cosine scan.

    Fine for a solo trader's volume; the pgvector implementation exists for when the case
    count grows enough that an indexed ANN search actually earns its keep.
    """

    def __init__(self) -> None:
        self._cases: list[Case] = []

    async def add(self, case: Case) -> None:
        self._cases.append(case)

    async def similar(self, vector: tuple[float, ...], *, strategy: str | None = None,
                      k: int = 5) -> list[Neighbor]:
        pool = [c for c in self._cases if strategy is None or c.strategy == strategy]
        scored = [Neighbor(c, cosine(vector, c.vector)) for c in pool]
        scored.sort(key=lambda n: n.similarity, reverse=True)
        return scored[:k]

    async def count(self) -> int:
        return len(self._cases)


def case_from_position(position, situation_vector: tuple[float, ...]) -> Case:
    """Build a Case from a just-closed Position + the vector of its closing state."""
    pnl = position.realized_pnl or 0.0
    won = pnl > 0
    label = "iron condor" if position.strategy == "iron_condor" else position.strategy.upper()
    # realized_pnl is per-share; show real per-contract dollars (×100) in the recap.
    dollars = pnl * 100
    summary = (f"{label} {position.underlying} · "
               f"{'+' if dollars >= 0 else '-'}${abs(dollars):,.0f} · {position.close_reason or 'manual'}")
    return Case(
        position_id=position.id, underlying=position.underlying, strategy=position.strategy,
        vector=tuple(situation_vector), realized_pnl=round(pnl, 4),
        close_reason=position.close_reason, won=won, summary=summary,
    )
