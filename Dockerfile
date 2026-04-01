# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS builder
WORKDIR /app

# Download zxing-wasm dist files so we can serve them locally (avoids CDN ES-module issues on iOS Safari)
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && \
    mkdir -p /zxing-wasm && \
    curl -sLf "https://cdn.jsdelivr.net/npm/zxing-wasm@1.3.5/dist/iife/full/index.js"  -o /zxing-wasm/index.js && \
    curl -sLf "https://cdn.jsdelivr.net/npm/zxing-wasm@1.3.5/dist/full/zxing_full.wasm" -o /zxing-wasm/zxing_full.wasm && \
    echo "[build] zxing-wasm downloaded: $(du -sh /zxing-wasm/)"

COPY pyproject.toml .
# Install runtime deps + test extras into a prefix we can copy cleanly
RUN pip install --no-cache-dir --prefix=/install ".[test]"

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS runtime
WORKDIR /app

# Non-root user for security
RUN adduser --disabled-password --gecos "" appuser

# Copy only the installed Python packages from the builder stage
COPY --from=builder /install /usr/local

# Copy application source
COPY app ./app/
COPY alembic ./alembic/
COPY alembic.ini .
COPY tests ./tests/
COPY entrypoint.sh ./entrypoint.sh

# Copy zxing-wasm static assets (downloaded in builder stage)
COPY --from=builder /zxing-wasm /app/app/static/zxing-wasm/

RUN mkdir -p /app/uploads && chown -R appuser:appuser /app && chmod +x entrypoint.sh
USER appuser

CMD ["./entrypoint.sh"]
