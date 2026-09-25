#!/usr/bin/env bash
# Verzamelt in één keer alles wat nodig is om een opstartprobleem te melden.
# Wachtwoorden worden gemaskeerd, dus de uitvoer is veilig te delen.
#
#   ./diagnose.sh              # rapport op het scherm
#   ./diagnose.sh > rapport.txt
set -uo pipefail

cd "$(dirname "$0")"

if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  echo "FOUT: docker compose niet gevonden." >&2
  exit 1
fi

# Maskeer alles wat op een wachtwoord lijkt (URL-wachtwoorden en KEY=waarde).
mask() {
  sed -E \
    -e 's#(://[^:/@]+:)[^@]*(@)#\1***\2#g' \
    -e 's#((PASSWORD|SECRET|PASSWD|TOKEN)[A-Z_]*[=:])[^[:space:],"]*#\1***#gI'
}

section() { printf '\n══════ %s ══════\n' "$1"; }

echo "Laptop Registratie — diagnoserapport"
date

section "Versie in git"
git log --oneline -1 2>/dev/null || echo "(geen git-repo)"

section "Containers"
$DC ps 2>&1 | mask

section "Variabelen uit .env (alleen namen, geen waarden)"
if [ -f .env ]; then
  grep -oE '^[A-Za-z_][A-Za-z0-9_]*=' .env | tr -d '='
else
  echo "(.env ontbreekt)"
fi

section "Resolveerde database-URL"
$DC config 2>/dev/null | grep -E '^\s+DATABASE_URL:' | mask || echo "(niet gevonden)"
if $DC config 2>/dev/null | grep -q 'DATABASE_URL: mysql+pymysql://root:@'; then
  echo ">>> LET OP: leeg databasewachtwoord. Zet MARIADB_ROOT_PASSWORD in .env."
fi

section "App rechtstreeks (http://localhost:8000/health)"
curl -sS -m 10 http://localhost:8000/health 2>&1 | mask || echo "(app antwoordt niet op poort 8000)"

section "App via nginx (https://localhost/health)"
curl -sSk -m 10 https://localhost/health 2>&1 | mask || echo "(nginx antwoordt niet)"

section "Laatste 60 regels app-log"
$DC logs --tail=60 app 2>&1 | mask

section "Laatste 20 regels nginx-log"
$DC logs --tail=20 nginx 2>&1 | mask

section "Laatste 20 regels db-log"
$DC logs --tail=20 db 2>&1 | mask

echo
echo "Einde rapport."
