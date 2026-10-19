# Build context is the repo root (see docker-compose.yml / .prod.yml) so the
# prod stage can also pull in data/catalog, which lives outside backend/.
FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

EXPOSE 8000

# --- dev: used by docker-compose.yml. App code arrives via bind mount
# (./backend:/app), so this stage intentionally doesn't COPY it or drop to
# a non-root user — both would fight the bind mount's host-owned files
# during local development. ---
FROM base AS dev
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# --- prod: used by docker-compose.prod.yml. Code is baked into the image,
# owned by and run as a non-root user; no --reload, multiple workers. ---
FROM base AS prod

RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /data/uploads \
    && chown -R appuser:appuser /data/uploads /app

COPY --chown=appuser:appuser backend/ .

USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
