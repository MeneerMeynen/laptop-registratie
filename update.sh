#!/usr/bin/env bash
# Update-script voor de productieserver (Ubuntu).
# Pullt de laatste code, herbouwt de Docker-app en wacht tot de app klaar is.
set -euo pipefail

# Altijd vanuit de map waarin dit script staat werken.
cd "$(dirname "$0")"

# docker compose (v2) met fallback naar docker-compose (v1).
if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  echo "FOUT: docker compose niet gevonden." >&2
  exit 1
fi

HEALTH_URL="http://localhost:8000/login"
TIMEOUT=180   # max wachttijd in seconden

echo "==> Laatste code ophalen (git pull)"
git pull --ff-only

echo "==> Docker-image bouwen en app herstarten"
$DC up -d --build

echo "==> Wachten tot de app antwoordt op ${HEALTH_URL} (max ${TIMEOUT}s)"
deadline=$(( $(date +%s) + TIMEOUT ))
until curl -sf -o /dev/null "$HEALTH_URL"; do
  if [ "$(date +%s)" -ge "$deadline" ]; then
    echo "FOUT: app reageerde niet binnen ${TIMEOUT}s." >&2
    echo "Laatste logs:" >&2
    $DC logs --tail=50 app >&2
    exit 1
  fi
  sleep 2
done

echo "==> App is klaar."
$DC ps
