# Running it

## The one-command way

```bash
docker compose up -d --build
# → http://localhost:8000
```

Postgres, Redis, the advisor service and the engine, all healthchecked, no host Python or
Node needed. It's the same image that would deploy to the cloud later.

Defaults to `PAZ_DATA=fixture` (offline demo data). For live delayed quotes, set
`PAZ_DATA=yfinance` in your shell before `up`. After a code change:
`docker compose up -d --build app`.

Don't want the extra container? Drop the `advisor` service and clear `ADVISOR_URL` — the
close-timing debate then runs in-process, identically. (See
[`ARCHITECTURE.md`](ARCHITECTURE.md#the-one-that-did-get-extracted).)

## Running from source

```bash
pip install -e ".[feeds,dev]"                      # core + free feed + tests
cd web && npm install && npm run build && cd ..     # build the dashboard once
UNDERLYINGS=SPY uvicorn paz_rav.api.app:app --port 8000
```

- **Frontend hot reload:** `cd web && npm run dev` (proxies `/api` and `/ws` to `:8000`),
  with the backend running separately.
- **No browser at all:** `PYTHONPATH=src python scripts/pipeline_demo.py SPY`.
- **Tests:** `python -m pytest` — pure, no infra, no network.
- Defaults to in-memory stores, so nothing survives a restart.

## With real persistence

```bash
docker compose up -d                       # just Postgres + Redis
PAZ_PERSIST=redis_postgres UNDERLYINGS=SPY,QQQ uvicorn paz_rav.api.app:app --port 8000
```

Candidates and positions both land in Postgres. To check they're really there:

```bash
docker exec paz-rav-postgres-1 psql -U paz -d pazrav -c "SELECT COUNT(*) FROM positions;"
docker exec paz-rav-redis-1 redis-cli KEYS '*'
```

## Environment variables worth knowing

| Variable | Does what | Default |
|---|---|---|
| `PAZ_DATA` | `fixture` (offline) or `yfinance` (live delayed) | `yfinance` from source, `fixture` under Compose |
| `PAZ_PERSIST` | `memory` or `redis_postgres` | `memory` from source, `redis_postgres` under Compose |
| `UNDERLYINGS` | Comma-separated universe to scan | a fixed list of 9 |
| `VRP` | Volatility risk premium — POP and expected P&L are computed at `realized = IV × (1 − VRP)`. **Read the "what we actually know" section of [`ROADMAP.md`](ROADMAP.md) before changing it**; `0` prices at fair value | `0.15` |
| `ANTHROPIC_API_KEY` | Enables the real LLM debates; without it they fall back to deterministic rules | unset |
| `ADVISOR_URL` | Point the debate at the advisor container; empty = run in-process | unset |
| `LANGFUSE_*` | Tracing; silently no-ops when unset | unset |
| `ALLOWED_EMAIL` | Turns on Google sign-in and names the owner. **Unset = auth off**, which is what you want locally | unset |

## Deploying to a cloud

Cloud-neutral by design — containers behind adapters, so this is a config change rather than
a rewrite. Since v1 is one process, the whole production shape is: one container, a managed
Postgres, a managed Redis, a static site for the dashboard.

**Three stages. Add the next one only when the current one actually hurts.**

1. **Start** — App Runner (one container, no cluster) + RDS + ElastiCache + S3/CloudFront. A
   real, cheap production deploy.
2. **More control** — ECS Fargate behind an ALB, Terraform for IaC, GitHub Actions for CI/CD,
   Claude via Bedrock.
3. **Scale** — EKS, and only after you've genuinely split into the ≤3 services from
   [`ARCHITECTURE.md`](ARCHITECTURE.md#why-one-process-not-seven).

GCP Cloud Run + Cloud SQL + Memorystore is arguably the easiest single-container deploy
anywhere, and is a config swap from here. (Firebase isn't a fit — it's built for serverless
apps, not a long-running real-time Python engine.)

A stage-1 Terraform scaffold sits in [`infra/terraform/`](../infra/terraform/). **Nothing has
ever been applied.** Read that directory's `README.md` first — running it costs real money.
