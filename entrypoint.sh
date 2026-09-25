#!/bin/sh
# Ensure the target database exists, then run migrations and start the app.
# Every step prints a [entrypoint] marker so a failed boot is readable in
# `docker compose logs app`.
set -e

log() { echo "[entrypoint] $*"; }

fail() {
    echo "[entrypoint] ─────────────────────────────────────────────" >&2
    echo "[entrypoint] OPSTARTEN MISLUKT: $*" >&2
    echo "[entrypoint] ─────────────────────────────────────────────" >&2
    exit 1
}

log "Laptop Registratie start op."

# Database URL zonder wachtwoord tonen, zodat logs deelbaar blijven.
python - <<'EOF' || exit 1
import os, re, sys

url = os.environ.get("DATABASE_URL", "")
if not url:
    print("[entrypoint] FOUT: DATABASE_URL is niet gezet.", file=sys.stderr)
    sys.exit(1)

masked = re.sub(r"(://[^:/@]+:)[^@]*(@)", r"\1***\2", url)
print(f"[entrypoint] Database-URL: {masked}")
if re.search(r"://[^:/@]+:@", url):
    print(
        "[entrypoint] WAARSCHUWING: leeg databasewachtwoord. Staat "
        "MARIADB_ROOT_PASSWORD in .env?",
        file=sys.stderr,
    )
EOF

log "Wachten op de database en controleren of ze bestaat…"
python - <<'EOF' || fail "de database is niet bereikbaar (zie de fout hierboven)"
import os, re, sys, time
from sqlalchemy import create_engine, text

url = os.environ["DATABASE_URL"]
base_url = re.sub(r"/[^/]+$", "/", url)
db_name = url.rsplit("/", 1)[-1]

last_error = None
for attempt in range(1, 31):
    try:
        engine = create_engine(base_url)
        with engine.connect() as conn:
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{db_name}`"))
        engine.dispose()
        print(f"[entrypoint] Database '{db_name}' is bereikbaar.")
        break
    except Exception as exc:
        last_error = exc
        print(f"[entrypoint] Poging {attempt}/30 mislukt: {type(exc).__name__}: {exc}")
        time.sleep(2)
else:
    print(f"[entrypoint] FOUT: database onbereikbaar: {last_error}", file=sys.stderr)
    sys.exit(1)
EOF

log "Huidige migratie in de database:"
alembic current || log "(kon de huidige migratie niet lezen — nieuwe database?)"

log "Migraties uitvoeren (alembic upgrade head)…"
alembic upgrade head || fail "migratie mislukt (zie de alembic-fout hierboven)"

log "Migratie na upgrade:"
alembic current

if [ -n "$UVICORN_RELOAD" ]; then
    log "Uvicorn start in reload-modus op poort 8000."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*' \
        --reload --reload-dir /app/app
fi

log "Uvicorn start op poort 8000."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'
