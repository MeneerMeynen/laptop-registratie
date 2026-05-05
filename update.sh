#!/usr/bin/env bash
# update.sh — Productie-update voor laptop-registratie
#
# Gebruik:
#   ./update.sh          # pull + rebuild + herstart
#   ./update.sh --check  # toon alleen wat er zou veranderen (git log)
# ---------------------------------------------------------------------------
set -euo pipefail

COMPOSE="docker compose"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

step()  { echo -e "\n${GREEN}▶ $*${NC}"; }
warn()  { echo -e "${YELLOW}⚠  $*${NC}"; }
abort() { echo -e "${RED}✗  $*${NC}"; exit 1; }

# ---------------------------------------------------------------------------
# 1. Check-modus: toon nieuwe commits zonder iets te doen
# ---------------------------------------------------------------------------
if [[ "${1:-}" == "--check" ]]; then
  step "Nieuwe commits op origin/main:"
  git fetch origin main --quiet
  git log HEAD..origin/main --oneline || echo "  (geen nieuwe commits)"
  exit 0
fi

# ---------------------------------------------------------------------------
# 2. Zorg dat we in de projectroot zitten
# ---------------------------------------------------------------------------
cd "$(dirname "$0")"

# ---------------------------------------------------------------------------
# 3. Git pull
# ---------------------------------------------------------------------------
step "Git pull (main)"
git pull origin main

# ---------------------------------------------------------------------------
# 4. Rebuild app-container (alleen als er iets veranderd is)
# ---------------------------------------------------------------------------
step "Docker build"
$COMPOSE build app

# ---------------------------------------------------------------------------
# 5. Herstart app (migraties draaien automatisch via entrypoint.sh)
#    --no-deps zodat db en nginx niet geraakt worden
# ---------------------------------------------------------------------------
step "Herstart app-container"
$COMPOSE up -d --no-deps app

# ---------------------------------------------------------------------------
# 6. Wacht tot de app gezond is (max 60s)
# ---------------------------------------------------------------------------
step "Wachten tot app klaar is…"
# Healthcheck draait vanaf de host (poort 8000 is gepubliceerd) omdat het
# runtime-image geen curl bevat. -f faalt op 4xx/5xx; een 303 redirect naar
# /login telt als "app draait".
TRIES=0
MAX_TRIES=24
until curl -sf -o /dev/null http://localhost:8000/ 2>/dev/null; do
  TRIES=$((TRIES + 1))
  if [[ $TRIES -ge $MAX_TRIES ]]; then
    abort "App reageerde niet binnen $((MAX_TRIES * 5))s. Controleer: docker compose logs app"
  fi
  echo "  ⏳ nog niet klaar ($TRIES/$MAX_TRIES)…"
  sleep 5
done

# ---------------------------------------------------------------------------
# 7. Toon actieve versie
# ---------------------------------------------------------------------------
step "Klaar! Actieve versie:"
echo "  Commit : $(git rev-parse --short HEAD) — $(git log -1 --format='%s')"
echo "  App URL: http://localhost:8000"
echo ""
echo "  Logs bekijken:  docker compose logs -f app"
echo "  Rollback:       git revert HEAD && ./update.sh"
