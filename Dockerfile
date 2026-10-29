# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

WORKDIR /app
# git resolves zarreh-agentkit, which is pinned to a git tag.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN UV_PROJECT_ENVIRONMENT=/opt/venv uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 1000 appuser
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY src ./src
# The serving model, its evidence and the synthetic queue are versioned artifacts.
# data/ is a volume for the SQLite databases and the cached UCI file used by the
# analyst's aggregate queries, so state survives a rebuild.
COPY artifacts ./artifacts
COPY data/queue.json ./data/queue.json
RUN chown -R appuser:appuser /app/data
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    CREDIT_ENVIRONMENT=production

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz', timeout=3)"

EXPOSE 8000
# Trusting X-Forwarded-For is safe only because no host port is published in
# compose.prod.yaml and the proxy overwrites the header (docs/deploy.md).
CMD ["uvicorn", "credit.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
