# Paz Rav — Multi-Agent Real-Time Options Strategy Engine
## A rationale-first plan: *why* every part exists, not just *what* it is

> Greenfield (empty home dir, no repo). This version defends each decision, is honest about
> what you truly need vs. what is "nice at scale" vs. resume-driven, and answers the business
> question first. **Assumptions** (all revisitable):
> advisory→paper v1, **Polygon.io** data, **AWS** (local mirror), backtesting core to v1.

---

# PART A — WHY THIS SYSTEM AT ALL (the business case)

## A1. What problem does it solve?
Iron condors, diagonals, and double diagonals on index ETFs are **premium-selling / vol-carry
income strategies**. They have a real, well-documented statistical edge, but that edge is
**thin, slow, and regime-dependent** — and it is destroyed by exactly the things humans are bad
at:

1. **Scale of scanning.** 5 underlyings × 3 strategies × dozens of expiries × hundreds of
   strikes = tens of thousands of candidate structures, changing every second. No human can
   continuously rank these on POP, credit/width, greeks, and liquidity.
2. **Regime discipline.** Selling a condor into an expanding-vol breakout gives back months of
   gains in one week. The edge only exists in the *right* regime; humans override the rules
   emotionally.
3. **Exit discipline.** The research edge is mostly in *management* — taking winners early
   (~50% of max profit), time-stopping (~21 DTE), cutting tested sides. Humans hold losers and
   cut winners — the exact opposite.
4. **Correlation blindness.** SPY≈SPX and IWM≈RUT are near-duplicates; QQQ is highly
   correlated. A human easily ends up with 5× the same short-vol bet and calls it
   "diversified."

**So the system's value is not a secret indicator — it's disciplined, quantified, always-on
execution of a known edge, with a full audit trail.** That is a real, defensible product.

## A2. How does it actually make money? (the edge, honestly)
Three documented, independent sources of expectancy — the system's job is to harvest them while
capping the tail:

| Edge | What it is | Which strategy uses it |
|---|---|---|
| **Volatility Risk Premium (VRP)** | Implied vol on index options is *systematically higher* than the volatility that later realizes → selling premium has positive expectancy | Iron condor (core) |
| **Term-structure / vol carry** | Front-month IV vs back-month IV differ; a steep curve lets you profit from *differential* time decay | Calendar / diagonal / double diagonal |
| **Skew richness** | Put skew is persistently overpriced → structure short strikes for better risk/reward | All three |
| **Management edge** | Mechanically closing winners ~50% and time-stopping ~21 DTE beats holding to expiry on a risk-adjusted basis | All three (the "best time to close") |

**Expectancy sketch (why it's not a coin flip):** a defined-risk condor might collect \$1.50
credit on \$5 wide wings (max loss \$3.50) at ~70% POP. Naive expectancy ≈ 0.70×\$150 −
0.30×\$350 = **−\$0** before edge. The *edge* comes from: (a) selling only when IV rank is high
(VRP fatter), (b) regime-gating out the breakouts that cause the −\$350 tail, (c) exiting
winners early to raise realized win-rate above the theoretical POP, and (d) paying less in
slippage via liquidity filters. **The whole system exists to bend each of those four levers.**

**Honest caveat:** this is not free money. If regime-gating and exit discipline don't add real
edge in backtest + paper, the strategy is a break-even premium grind. That is *precisely why*
backtesting and paper-tracking are core to v1 — we prove the edge before risking capital.

## A3. How do YOU monetize it? (three ladders)
1. **Trade your own capital** — advisory alerts → you place orders (v1), then paper to validate,
   then live. Lowest external risk.
2. **Signals / alerts subscription** — sell the ranked trades + exit signals as a service
   (no custody of client money, lighter regulation). The audit trail/thesis is the product.
3. **Managed capital (SMA/fund)** — only after a track record; heaviest regulatory load.

Start at (1); the architecture makes (2) a small add-on (the API + alert layer already exists).

---

# PART B — WHY MULTI-AGENT (and where agents must NOT be used)

## B1. The single most important design rule
**LLMs reason; they never compute the numbers.** Every greek, IV, price, POP, and P&L comes
from **deterministic code/tools**. An LLM asked "what's the delta of this spread?" will
confidently hallucinate. So:

- **The quant core (greeks, IV surface, candidate enumeration, POP, backtest) = pure Python.
  No agents.** Agents here would be slower, costlier, and *less accurate* — the opposite of your
  "must be accurate" requirement.
- **Agents live only in the judgment layer**, on top of pre-computed structured data.

## B2. So why use agents *at all* (vs. one big prompt, or pure rules)?
You could ship a **rules-only v1** with zero LLMs and it would function. Agents earn their place
in exactly three ways a mechanical rule handles poorly:

1. **Judgment under ambiguity.** "IV rank is 55 (borderline), but FOMC is in 3 days, term
   structure just inverted, and IWM is diverging from SPY — is this condor still smart?" This is
   synthesis of quantitative + contextual signals where a hard threshold is brittle.
2. **Critique reduces error.** A dedicated **Red-Team agent** that must argue *against* every
   trade, plus separated single-purpose agents (Regime, Risk), measurably reduces overconfident
   decisions vs. one monolithic prompt. This is the real reason for *multi*-agent rather than
   one agent: **separation of concerns + adversarial review**, not "more agents = better."
3. **Explainability = trust + debuggability.** Each agent emits one piece of a written thesis.
   When you're about to risk capital (or sell signals), "here is the regime call, the vol-edge
   rationale, the risk sizing, and the counter-argument" is worth far more than a black-box
   score. It's also how you debug a bad run.

**Honest framing:** agents are the *differentiator for judgment and explainability*, layered on
a deterministic core that already works without them. We build the core first; agents are
Phase 2.

## B3. The committee (each agent = one job, one reason to exist)
| Agent | Why it exists (the failure it prevents) |
|---|---|
| **Regime Analyst** | Stops us selling condors into the wrong regime (the #1 account killer) |
| **Scout** | Reduces the deterministic shortlist to a human-sized set the committee can reason over |
| **Quant Modeler** | Turns raw surface/greek numbers into a judged "is the vol edge real here?" |
| **Risk Officer** | Enforces portfolio greeks, max-loss, and correlation limits across the 5 names |
| **Red-Team** | Adversarial: forces a stated bear case (gap, vol spike, macro) before any yes |
| **Portfolio Manager** | Arbitrates, dedupes correlated bets, makes the final sized call |
| **Exit Manager** | Answers "best time to close" continuously per open position |
| **Historian (memory)** | Supplies precedents from past setups+outcomes (see RAG section) |

---

# PART C — DO WE NEED RAG? (honest answer: not the way people mean it)

**Classic document-RAG (embed docs, retrieve text) is NOT the point here** — there are no
documents; there are numbers. What *is* genuinely valuable is **case-based memory**:

> "This SPX condor — IV rank 60, term structure inverted, 45 DTE, 16-delta shorts — resembles
> 14 historical setups. 9 were losers, avg −\$180. Proceed with caution."

This is **retrieval over a vector of *numeric* setup features**, not text embeddings — a
similarity search over historical labeled setups. Call it **RAG-lite / case retrieval**. Verdict:

- **Not needed for v1 correctness** — the trade math stands alone.
- **Valuable in Phase 3+** once we have enough labeled outcomes to retrieve against.
- Implemented with **pgvector/Qdrant over engineered feature vectors**, feeding the Historian
  agent. We will *not* pretend to need heavyweight document-RAG we don't.

---

# PART D — WHY LANGCHAIN & LANGFUSE (honest, with alternatives)

## D1. LangChain → we want **LangGraph specifically, not the kitchen sink**
- **What we actually need:** a **stateful, branching orchestration graph** for the multi-agent
  debate — shared state, conditional edges (e.g., "if Red-Team objects, loop back to Quant"),
  retries, and human-in-the-loop pauses. That is **LangGraph's** exact sweet spot.
- **What we skip:** most of classic LangChain's "chains/loaders/wrappers" — unnecessary
  abstraction for us. We call **Claude via the Anthropic SDK / Bedrock** directly for the model.
- **Alternatives considered:** hand-rolled async orchestration (fine, but we'd reinvent graph
  state + retries); CrewAI/AutoGen (more opinionated, less control). **Verdict: LangGraph for
  the graph, thin and deliberate; no broad LangChain dependency.**

## D2. Langfuse → **strong keep**, this is the most justified LLM tool in the stack
LLM decisions are non-deterministic and real money rides on them. You need three things
Langfuse gives natively:
1. **Tracing** — every agent call's inputs/outputs/tool-calls captured, so you can see exactly
   why the committee said yes.
2. **Datasets + evals** — build test sets of past situations and re-run prompts against them
   when you change anything (regression testing for prompts).
3. **Outcome scoring = the closed loop.** When a trade later wins/loses, **score that outcome
   back onto the original trace.** Now you can ask: *which regimes/prompts/agents produce
   winning calls?* — and tune. This feedback loop is the difference between "a chatbot that
   picks trades" and "a system that learns which of its judgments are good."
- **Alternatives:** LangSmith (tied to LangChain, hosted), or roll-your-own logging. Langfuse
  is **open-source + self-hostable** → fits AWS/self-host and avoids lock-in. **Verdict: keep.**

---

# PART E — WHERE KAFKA, RABBITMQ, REDIS ACTUALLY FIT (the part you pushed on)

I'll be blunt: **for a solo v1, Kafka and RabbitMQ are both arguably overkill**, and I'll say so
per-item. But each has a *specific, real* justification if we want the system to scale and — more
importantly — to have **one code path for live and backtest**. Here is the honest map.

## E1. Redis — needed from day one (cheapest, highest value)
- **Job:** hot state + fan-out. Latest greeks/IV per contract, open-position state, **vendor API
  rate-limit tokens**, and **pub/sub → the dashboard WebSocket**.
- **What breaks without it:** every service re-hits the DB/vendor for "current" values; the live
  dashboard has no low-latency push.
- **Verdict: essential, not debatable.**

## E2. Kafka — justified by ONE killer property: *replayability*
- **Job:** the **market-data firehose as a durable, replayable log.** Ingest quotes/greeks for 5
  underlyings' full chains (tens of thousands of msgs/sec near the open) into topics that
  multiple independent consumers read (analytics, recorder, dashboard).
- **The real reason to bother:** **backtest = replay the exact same topic through the exact same
  analytics/builder/committee code.** No separate "backtest data path" that silently diverges
  from live. That single property is worth a lot for *accuracy* and trust.
- **Honest alternative:** if you drop the replay-from-log requirement, **Redis Streams** or even
  a direct WebSocket→process pipeline is far simpler. Kafka only pays off with replay + multiple
  consumers + durability.
- **Verdict: keep, but *because of replay*, not for its own sake.** Use **Redpanda** locally
  (Kafka-compatible, one binary) and **MSK** on AWS. If you later decide replay isn't worth the
  ops cost, this is the one piece to cut.

## E3. RabbitMQ — the *command/task* bus (a different pattern from Kafka)
- **Job:** discrete **jobs and request/reply** between services — "build candidates for SPX,"
  "run committee on this shortlist," "evaluate exit for position #42" — with retries,
  priorities, and dead-letter queues. This is **task orchestration**, not stream processing.
- **Why not just use Kafka for this too?** Different semantics: Kafka is an append-only *event
  log* (great for streams, awkward for RPC/per-task ack/retry); RabbitMQ is a *work broker*
  (great for "do this one job, ack it, retry on failure"). Using the right tool per pattern
  keeps each simple.
- **Honest alternative:** at small scale, **Celery-on-Redis** or in-process asyncio queues
  replace RabbitMQ entirely. RabbitMQ earns its keep once agent workflows are **distributed and
  independently scaled** (e.g., 10 builder workers, 3 committee workers).
- **Verdict: keep as the orchestration bus you asked for, with eyes open** — it's a Phase-2+
  need. On AWS: **Amazon MQ**.

## E4. One-line mental model
> **Kafka = "what happened" (streaming facts, replayable). RabbitMQ = "please do this" (tasks/
> RPC). Redis = "what's true right now" (hot state + push).** Three different jobs, no overlap.

## E5. Minimal-vs-full honesty table
| Tech | Truly needed in v1? | Cheapest substitute | Keep because… |
|---|---|---|---|
| Redis | **Yes** | — | hot state + dashboard push |
| Kafka | Optional (strong if backtest-parity matters) | Redis Streams / direct WS | one code path for live+backtest |
| RabbitMQ | Not until distributed | Celery/Redis, asyncio | clean task/RPC semantics at scale |
| LangGraph | Yes (once agents exist) | hand-rolled orchestration | branching multi-agent state |
| Langfuse | **Yes** | DIY logging | traces + outcome-scored learning loop |
| pgvector (RAG) | No (Phase 3) | skip | case-retrieval memory later |

---

# PART F — WORKED EXAMPLE: one trade's life, showing where each tech touches

1. **Tick in.** Polygon WebSocket → **ingestion** normalizes → **Kafka** `md.options.spx` topic.
2. **Analytics "skills"** consume the topic → fit IV surface, compute greeks/IV-rank/term-slope
   → write hot values to **Redis**, append features to the **S3 Parquet lake**.
3. **Scheduler** drops a "scan SPX" job on **RabbitMQ** → a **builder** worker enumerates iron
   condor / diagonal / double-diagonal candidates at ~45 DTE, filters by liquidity, scores
   (POP, credit/width, theta/vega), returns a shortlist.
4. **RabbitMQ** "run committee" job → **LangGraph** committee: Regime gates strategy → Quant
   judges vol edge → Risk sizes → **Red-Team** objects → PM decides. **Langfuse** traces it all.
5. **Recommendation + written thesis** → **API** → **Redis pub/sub** → dashboard WebSocket +
   Slack/mobile alert. (Paper mode: also booked into the paper OMS.)
6. **Exit Manager** watches the position's live greeks (from **Redis**) → when profit ≥ target,
   or 21 DTE, or gamma/regime escalates → emits "close now." → alert.
7. **Outcome** (realized P&L) → **scored back onto the Langfuse trace** + added to the case-memory
   store → next time, the Historian can cite this trade. **Loop closes.**

---

# PART F2 — MICROSERVICES STRUCTURE (how the pieces are split & talk)

## F2.0 Design principle
Split by **rate of change + failure domain**, not by "one service per noun." A service that
must never drop a tick (ingestion) is isolated from one that does heavy math (analytics) from one
that does slow LLM calls (committee). Each is independently deployable and scalable. **They
communicate only through the three buses** — never by reaching into each other's database.

> **Bus rules (repeat):** Kafka = streaming facts · RabbitMQ = commands/RPC · Redis = hot state +
> UI push. A service owns its own storage; others read it *only* via that service's API/topic.

## F2.1 The services (Phase 1 = services 1–5 + UI; 6–7 added later)

**1. `ingestion-service` (market-data gateway)** — *the only thing that talks to the vendor.*
- **Does:** hold Polygon WebSocket/REST sessions, normalize to our schema, publish ticks.
  Handles reconnect, backfill, sequence gaps, and **vendor rate-limiting via a Redis token
  bucket** so nothing else worries about vendor limits.
- **In:** Polygon feeds. **Out:** Kafka `md.underlying.{spy,qqq,iwm,spx,rut}`,
  `md.options.{...}`. **State:** Redis (rate tokens, last-seq).
- **Tech:** Python asyncio + confluent-kafka producer. **Scale:** 1 instance per vendor
  shard; stateless-ish, restart-safe (Kafka is the buffer).

**2. `analytics-service` (feature & greeks engine — the "skills")** — *turns ticks into truth.*
- **Does:** consume `md.*`, compute **IV surface (SVI fit), greeks, IV rank/percentile, term-
  structure slope, skew, expected move**. Writes **hot** values to Redis (for UI + builders) and
  **offline** features to the S3 Parquet lake + TimescaleDB (for backtest/history).
- **In:** Kafka `md.*`. **Out:** Redis hot keys + **Redis pub/sub `ui.features`** (live UI push),
  Parquet lake, Timescale. **Owns:** the feature store.
- **Tech:** numpy/scipy/**py_vollib**/polars. **Scale:** horizontally, partitioned by underlying.
- **This is the accuracy core.** Exposed as MCP/Skill tools (`iv-surface`, `pop`, …) so it's
  reusable by agents *and* by the backtester — same code, no divergence.

**3. `builder-service` (strategy candidate engine)** — *enumerates & ranks the trades.*
- **Does:** on a job (RabbitMQ) or schedule, enumerate **iron condor / diagonal / double-
  diagonal** candidates at ~45 DTE, filter by liquidity (bid/ask, OI), score (POP, credit/width,
  theta/vega, max-loss), and run the **digital-twin Monte-Carlo** payoff.
- **In:** RabbitMQ `build.request` + Redis features/chain. **Out:** Postgres `candidates` (durable
  ranked list), RabbitMQ reply, **Redis pub/sub `ui.candidates`** (live UI push). **Owns:**
  the candidates table.
- **Tech:** Python (shares the analytics libs). **Scale:** worker pool (N builders behind the
  queue).

**4. `backtester-service`** — *proves the edge; shares the exact live code path.*
- **Does:** replay historical data (Parquet, or **Kafka replay** of `md.*`) through the *same*
  analytics + builder logic; walk-forward; compute win-rate/P&L/drawdown per strategy.
- **In:** Parquet lake / Kafka replay. **Out:** Postgres `backtest_runs` + artifacts to S3.
- **Tech:** imports analytics/builder libs directly. **Scale:** batch/job, not always-on.

**5. `api-service` (BFF + WebSocket gateway)** — *the only thing the browser talks to.*
- **Does:** REST for history/queries (candidates, features, backtests from Postgres/Redis/Timescale)
  + **WebSocket** that fans out Redis pub/sub (`ui.features`, `ui.candidates`) to the UI. Auth,
  rate-limit, request validation.
- **In:** Redis pub/sub + hot, Postgres, Timescale. **Out:** HTTP/WS to the web UI.
- **Tech:** FastAPI + `websockets`. **Scale:** horizontal, stateless.

**6. `committee-service` (Phase 2)** — LangGraph multi-agent debate + Langfuse tracing.
- **In:** RabbitMQ `committee.request` + candidate/feature context. **Out:** Postgres
  `recommendations` (+ thesis), Redis pub/sub `ui.recs`, Langfuse traces. **Scale:** worker pool
  (LLM-bound, slowest tier — isolated so it can't slow ingestion).

**7. `exit-manager-service` (Phase 3)** — watches open positions' live greeks (Redis), applies
  rules + learned policy, emits close/adjust signals → alerts + `ui.exits`.

**Shared, not services:** `libs/contracts` (Pydantic + topic schemas — the contract every service
agrees on), and a light `scheduler` (cron → drops `build.request` jobs on RabbitMQ).

## F2.2 Who talks to whom (Phase 1)
```
Polygon ─▶ ingestion ──Kafka(md.*)──▶ analytics ──Redis(hot + pub ui.features)──▶ api ─WS─▶ Web UI
                                          │                                          ▲
                          Parquet lake / Timescale (offline)                        │
scheduler ──RabbitMQ(build.request)──▶ builder ──Postgres(candidates)──────────────▶│
                                          └──────Redis(pub ui.candidates)───────────┘
backtester ──(replays Kafka/Parquet through analytics+builder libs)──▶ Postgres(backtest_runs) ─▶ api
```
> **Phase-1 lean option (my recommendation):** you can run Phase 1 with **Redis only** —
> ingestion→analytics over **Redis Streams**, and the scheduler calling the builder directly.
> Introduce **Kafka** the moment you build the backtester (you'll want replay parity), and
> **RabbitMQ** when you scale to multiple builder/committee workers. The service boundaries above
> don't change — only the transport between them does.

---

# PART F3 — PHASE 1 WEB UI (all the data, visualized)

Phase 1 has **no LLM** — its job is to make the deterministic data *trustworthy and legible*. A
polished, real-time dashboard is how you (and later, subscribers) actually see the edge. Live via
WebSocket; **theme-aware, accessible, one visual system** (built to the dataviz design guidance).

**Views:**
1. **Market Overview** — the 5 underlyings as cards: price, **IV-rank gauge**, VIX, a rule-based
   **regime label** (trend/range × vol state), and a term-structure sparkline. Red/green health
   at a glance for "is any strategy eligible right now?"
2. **Vol Lab (per underlying)** — **IV-surface heatmap**, **skew curve**, and **term-structure
   curve** (front vs back month). This is where the calendar/diagonal edge is visible.
3. **Options Chain** — live chain with greeks (Δ Γ Θ V), IV, bid/ask/OI, filterable by expiry/
   delta. Updates in place via WebSocket.
4. **Candidate Trades** — the ranked table (IC / diagonal / double-diagonal) with POP, credit/
   width, max loss, net greeks, liquidity score. Sort/filter; click a row → …
5. **Trade Inspector** — for a selected candidate: **payoff-at-expiry diagram** + the digital-
   twin **Monte-Carlo P&L cone**, greek profile, and the exact strikes/legs. This is the "why
   this trade" panel.
6. **Backtest Dashboard** — equity curve, **win-rate, avg P&L, max drawdown** per strategy vs. the
   mechanical baseline; per-trade drill-down. This is where you decide to trust it.

**Frontend tech:** React + TypeScript, **Recharts** (+ a lightweight financial-chart lib for the
surface/payoff), WebSocket client to `api-service`, TailwindCSS. Data contract mirrors
`libs/contracts`. **Every number on screen traces to an analytics/builder computation — nothing
is invented.**

---

# PART G — STACK, REPO, ROADMAP, VERIFICATION

## G1. Concrete stack
- **Core:** Python 3.12, Pydantic, FastAPI, asyncio.
- **Quant (deterministic):** numpy, scipy, **py_vollib**/QuantLib (greeks), polars, PyArrow.
- **Agents:** **LangGraph** + **Langfuse**; **Claude Opus 4.8** for the committee, **Sonnet** for
  high-volume scanning (model routing to control cost) via Anthropic API or **AWS Bedrock**.
- **Messaging/state:** Kafka (Redpanda local / **MSK**), RabbitMQ (aio-pika / **Amazon MQ**),
  Redis (TimeSeries/JSON / **ElastiCache**).
- **Storage:** **TimescaleDB** time-series, **S3/MinIO** Parquet lake, **Postgres** app/positions,
  **pgvector/Qdrant** case-memory (Phase 3).
- **Data as "skills":** Claude Agent Skills + MCP servers wrapping the quant tools so agents (and
  you) call them as functions: `fetch-chain`, `iv-surface`, `pop`/`expected-move`,
  `build-iron-condor`/`-diagonal`/`-double-diagonal`, `digital-twin`, `portfolio-greeks`,
  `backtest-replay`.
- **Infra:** Docker Compose (local) → **EKS**; **Terraform**; GitHub Actions CI.
- **Cloud-portable by design:** adapters + containers → GCP (GKE/Confluent/Memorystore/Vertex) or
  self-hosted k3s is a config swap, not a rewrite.

## G2. Repo layout (monorepo, one deployable per service)
```
paz-rav/
  infra/            terraform/, docker-compose.yml, k8s/
  libs/
    contracts/      pydantic + topic schemas (the shared contract)
    quant/          greeks, iv-surface, pop, digital-twin  (imported by analytics+builder+backtester)
  services/
    ingestion/  analytics/  builder/  backtester/  api/     # Phase 1
    committee/  exit_manager/                               # Phase 2–3
  skills/           Claude Agent Skills + MCP servers wrapping libs/quant
  web/              React/TS dashboard (Phase 1 UI)
  eval/             Langfuse datasets, outcome-scoring jobs, prompt/policy tuning
```

## G3. Roadmap (each phase ships value; agents/heavy infra deferred until earned)
- **Phase 0 — Foundations:** repo, Terraform, local Compose, Polygon adapter → Kafka ingestion,
  shared schemas.
- **Phase 1 — Deterministic accuracy core + Web UI (NO LLM yet):** `ingestion` → `analytics`
  skills → feature store → the 3 `builder` strategies → `backtester` replay → `api` → **the
  Phase-1 web dashboard (PART F3) showing every computed value live.** *This is where "accurate"
  is earned, the edge is proven in backtest, and all data is legible in a nice UI.*
- **Phase 2 — Trade Committee:** LangGraph agents + Langfuse; advisory alerts + dashboard.
- **Phase 3 — Exit + learning loop:** Exit Manager, management policy/bandit, **paper OMS**,
  outcome→Langfuse closed loop, case-memory (RAG-lite).
- **Phase 4 — Hardening / optional live:** EKS, risk kill-switch, optional broker (IBKR/Tradier)
  behind hard limits.

## G4. Verification (how we know it works end-to-end)
1. **Deterministic parity:** builders/greeks unit-tested vs. a known vendor snapshot; IV-surface
   fit error within tolerance vs. vendor greeks.
2. **Live = backtest parity:** the same strategy over history via `backtest-replay` yields the
   same signals when that history is replayed live through Kafka (proves one code path — the
   whole reason Kafka is in the stack).
3. **Walk-forward backtest** on 2–3 yrs of all 5 underlyings: win-rate, avg P&L, max drawdown per
   strategy vs. a naive mechanical baseline.
4. **Trace audit:** every recommendation in Langfuse shows every tool call + numbers (zero
   un-sourced figures) + the Red-Team objection.
5. **Paper forward-test:** N weeks; committee P&L vs. mechanical baseline, scored onto traces.
6. **Infra smoke:** Kafka sustains target msgs/s; Redis dashboard latency < target; RabbitMQ
   committee round-trip within SLA.
7. **Phase-1 UI acceptance (your explicit requirement):** with markets open, the dashboard shows
   all 5 underlyings updating live — IV-rank gauges, vol surface/skew/term-structure, live chain,
   ranked candidates, and a Trade Inspector payoff + Monte-Carlo cone — every value pushed over
   WebSocket and traceable to an analytics/builder computation. The Backtest Dashboard renders the
   walk-forward results per strategy vs. baseline.

---

# PART H — OPEN QUESTIONS (assumed defaults, please confirm)
- **Execution scope:** advisory → paper → (later) live?  [assumed]
- **Data vendor + budget:** Polygon.io, or ThetaData/ORATS for deeper accuracy?  [assumed Polygon]
- **Cloud:** commit to AWS, or keep GCP/self-host open?  [assumed AWS]
- **Backtest depth:** how many years of history / how rigorous?  [assumed 2–3 yrs, core]
- **Do you want the heavy infra (Kafka/RabbitMQ) in v1, or start lean (Redis-only) and add them
  when scale/backtest-parity demands?** — my honest recommendation: **start lean, add Kafka when
  you build the backtester, add RabbitMQ when you distribute the workers.**
- **Alert channels** (Slack? mobile? email?) and, if paper/live, **capital & per-trade risk
  limits.**
