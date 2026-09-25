#!/bin/sh
# Opstartscript van de container: poort instellen, APP_KEY voorzien,
# wachten op de database en migraties uitvoeren.
set -e
cd /var/www/html

# Cloud Run geeft de poort door via $PORT (standaard 80 in Docker Desktop).
sed -ri "s/^Listen [0-9]+/Listen ${PORT:-80}/" /etc/apache2/ports.conf
sed -ri "s/<VirtualHost \*:[0-9]+>/<VirtualHost *:${PORT:-80}>/" /etc/apache2/sites-available/000-default.conf

# Zonder APP_KEY: eenmalig een sleutel aanmaken en bewaren in het storage-volume,
# zodat sessies een herstart overleven.
if [ -z "$APP_KEY" ]; then
    KEY_FILE=storage/app/.app_key
    if [ ! -s "$KEY_FILE" ]; then
        echo "base64:$(head -c 32 /dev/urandom | base64)" > "$KEY_FILE"
    fi
    APP_KEY="$(cat "$KEY_FILE")"
    export APP_KEY
fi

mkdir -p storage/app/uploads/laptops storage/framework/cache storage/framework/sessions storage/framework/views storage/logs
if [ "${DB_CONNECTION:-}" = "sqlite" ] && [ -n "${DB_DATABASE:-}" ] && [ ! -f "$DB_DATABASE" ]; then
    touch "$DB_DATABASE"
fi
# Wachten tot de database bereikbaar is (MariaDB start soms trager dan de app).
tries=0
until php artisan migrate --force --no-interaction; do
    tries=$((tries + 1))
    if [ "$tries" -ge 30 ]; then
        echo "Database niet bereikbaar na 30 pogingen." >&2
        exit 1
    fi
    echo "Wachten op de database... ($tries)"
    sleep 2
done

# Bestanden die hierboven als root aangemaakt zijn, horen bij de webserver.
chown -R www-data:www-data storage bootstrap/cache

exec "$@"
