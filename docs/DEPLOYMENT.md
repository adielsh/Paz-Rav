# Running & Deploying

## Option A — one command, the whole stack (recommended)

```bash
docker compose up -d --build
# → open http://localhost:8000
```

Builds the dashboard, starts Postgres + Redis + the engine together, healthchecked. No
host Python or Node needed — this is the same image that would deploy to the cloud
later. Uses `PAZ_DATA=fixture` (offline demo data) by default; set `PAZ_DATA=yfinance`
in your shell before `up` for live delayed quotes.

Rebuild just the app after a change: `docker compose up -d --build app`.

## Option B — run from source (active development)

```bash
pip install -e ".[feeds,dev]"                      # core + free data feed + tests
cd web && npm install && npm run build && cd ..    # build the dashboard once
UNDERLYINGS=SPY uvicorn paz_rav.api.app:app --port 8000
# → open http://localhost:8000
```

- **Frontend dev mode** (hot reload): `cd web && npm run dev` (proxies `/api` + `/ws` to
  `:8000`), backend running separately.
- **No browser needed** — CLI demos exercise the same pipeline:
  `PYTHONPATH=src python scripts/pipeline_demo.py SPY`
- **Tests:** `python -m pytest` — pure, no infra or network required.

Running from source defaults to in-memory stores (nothing survives a restart).

## Real persistence

```bash
docker compose up -d                       # Postgres + Redis, healthchecked
PAZ_PERSIST=redis_postgres UNDERLYINGS=SPY,QQQ uvicorn paz_rav.api.app:app --port 8000
```

Both candidates and positions are stored in Postgres in this mode — a paper position
survives a restart. Verify it's real, not just working in-process:

```bash
docker exec paz-rav-postgres-1 psql -U paz -d pazrav -c "SELECT COUNT(*) FROM positions;"
docker exec paz-rav-redis-1 redis-cli KEYS '*'
```

## Cloud deployment (AWS)

Cloud-neutral by design (containers + adapters) — deploying is a config change, not a
rewrite. Because v1 is a single process, deployment stays simple: one container, a
managed Postgres, a managed Redis, a static site for the dashboard.

**Three stages — add the next only when the previous one actually hurts:**

1. **Simplest start** — `App Runner` (one container, no cluster) + `RDS` (Postgres) +
   `ElastiCache` (Redis) + `S3 + CloudFront` (dashboard). Real, cheap production deploy.
2. **More control** — `ECS Fargate` behind an `ALB`; `Terraform` for IaC; `GitHub
   Actions` CI/CD; Claude on `Bedrock`.
3. **Scale** — `EKS` (Kubernetes), only once you've actually split into the ≤3 services
   from `docs/ARCHITECTURE.md` and scale demands it.

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
single-container deploy anywhere — everything here is cloud-portable, so this is a
config swap, not a rewrite. (Firebase is **not** a fit — it's for serverless mobile/web
apps, not a long-running real-time Python engine.)

A Terraform scaffold for stage 1 exists at [`infra/terraform/`](../infra/terraform/) —
**nothing has been applied**; see that directory's `README.md` before running it (it
costs real money once you do).
