# Paz Rav — one image, the whole engine + dashboard.
# Multi-stage: build the React dashboard, then run the Python app that serves it.
#
# This same image is what would push to ECR/App Runner/ECS/EKS later (docs/DEPLOYMENT.md) —
# containerizing locally now is what makes that transition a config change, not a rewrite.

# ---- Stage 1: build the dashboard ----
FROM node:20-alpine AS web-build
WORKDIR /app/web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# ---- Stage 2: runtime ----
FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Core + feed + AI-layer deps (the pure-stdlib quant core needs nothing extra).
COPY pyproject.toml ./
RUN pip install \
    "fastapi>=0.110" "uvicorn[standard]>=0.29" "pydantic>=2.6" "pydantic-settings>=2.2" \
    "redis>=5.0" "asyncpg>=0.29" "httpx>=0.27" "yfinance>=0.2.40" "pyjwt[crypto]>=2.9" \
    "langgraph>=0.2" "langfuse>=2.0" "anthropic>=0.25"

COPY src/ ./src/
COPY tests/fixtures/ ./tests/fixtures/
COPY --from=web-build /app/web/dist ./web/dist

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --retries=6 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "paz_rav.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
