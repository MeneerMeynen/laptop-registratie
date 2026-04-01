# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS builder
WORKDIR /app

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

RUN mkdir -p /app/uploads && chown -R appuser:appuser /app && chmod +x entrypoint.sh
USER appuser

CMD ["./entrypoint.sh"]
