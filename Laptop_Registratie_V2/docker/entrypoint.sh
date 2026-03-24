#!/bin/sh
# Ensure the target database exists, then run migrations and start the app.
set -e

python - <<'EOF'
import os, re
from sqlalchemy import create_engine, text

url = os.environ["DATABASE_URL"]
# Build a connection URL without the database name so we can run CREATE DATABASE
base_url = re.sub(r"/[^/]+$", "/", url)
db_name = url.rsplit("/", 1)[-1]

engine = create_engine(base_url)
with engine.connect() as conn:
    conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{db_name}`"))
engine.dispose()
print(f"[entrypoint] Database '{db_name}' is ready.")
EOF

alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
