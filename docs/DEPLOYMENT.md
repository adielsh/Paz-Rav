# Running & Deploying

## Option A — one command (recommended)

```bash
docker compose up -d --build
# → open http://localhost:8000
```

Builds the dashboard, starts Postgres + Redis + the engine together, healthchecked — no
host Python or Node needed, and it's the same image that deploys to the cloud later.
Defaults to `PAZ_DATA=fixture` (offline demo); set `PAZ_DATA=yfinance` for live delayed
quotes. Rebuild after a change: `docker compose up -d --build app`.

## Option B — run from source (active development)

```bash
pip install -e ".[feeds,dev]"                      # core + free data feed + tests
cd web && npm install && npm run build && cd ..    # build the dashboard once
UNDERLYINGS=SPY uvicorn paz_rav.api.app:app --port 8000
# → open http://localhost:8000
```

- Frontend hot reload: `cd web && npm run dev` (proxies `/api` + `/ws` to `:8000`),
  backend running separately.
- No browser needed: `PYTHONPATH=src python scripts/pipeline_demo.py SPY`.
- Tests: `python -m pytest` — pure, no infra or network required.
- Defaults to in-memory stores (nothing survives a restart).

## Real persistence

```bash
docker compose up -d                       # Postgres + Redis, healthchecked
PAZ_PERSIST=redis_postgres UNDERLYINGS=SPY,QQQ uvicorn paz_rav.api.app:app --port 8000
```

Candidates and positions both persist to Postgres in this mode — verified to survive a
restart:

```bash
docker exec paz-rav-postgres-1 psql -U paz -d pazrav -c "SELECT COUNT(*) FROM positions;"
docker exec paz-rav-redis-1 redis-cli KEYS '*'
```

## Cloud deployment (AWS)

Cloud-neutral by design (containers + adapters) — deploying is a config change, not a
rewrite. Because v1 is a single process: one container, a managed Postgres, a managed
Redis, a static site for the dashboard.

**Three stages — add the next only when the previous one actually hurts:**

1. **Start** — `App Runner` (one container, no cluster) + `RDS` + `ElastiCache` +
   `S3 + CloudFront`. Real, cheap production deploy.
2. **More control** — `ECS Fargate` behind an `ALB`; `Terraform` for IaC; `GitHub
   Actions` CI/CD; Claude on `Bedrock`.
3. **Scale** — `EKS`, only once you've actually split into the ≤3 services from
   [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) and scale demands it.

| Component | AWS service |
|---|---|
| Container(s) | App Runner → ECS Fargate → EKS |
| Postgres | Amazon RDS |
| Redis | Amazon ElastiCache |
| Object storage | Amazon S3 |
| Claude | Amazon Bedrock (or the Anthropic API directly) |
| IaC | Terraform |
| CI/CD | GitHub Actions → ECR |

**Alternative:** `GCP Cloud Run` + `Cloud SQL` + `Memorystore` is arguably the easiest
single-container deploy anywhere — a config swap here, not a rewrite. (Firebase isn't a
fit — it's for serverless mobile/web apps, not a long-running real-time Python engine.)

A Terraform scaffold for stage 1 exists at [`infra/terraform/`](../infra/terraform/) —
**nothing has been applied**; read that directory's `README.md` first (it costs real
money once you run it).
