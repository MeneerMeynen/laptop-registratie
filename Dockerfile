# Laptop Registratie — container voor lokaal testen (Docker Desktop) of een demo op Cloud Run.
# Productie draait op Plesk zonder Docker; zie README.md.

# ── Stap 1: PHP-dependencies installeren ──────────────────────────────────
FROM composer:2 AS vendor
WORKDIR /app
COPY composer.json composer.lock ./
RUN composer install --no-dev --no-scripts --no-autoloader --prefer-dist --no-interaction --no-progress
COPY . .
RUN composer dump-autoload --optimize --no-dev --no-scripts

# ── Stap 2: PHP 8.3 + Apache ──────────────────────────────────────────────
FROM php:8.3-apache

RUN docker-php-ext-install pdo_mysql \
    && a2enmod rewrite \
    && echo 'ServerName localhost' > /etc/apache2/conf-available/servername.conf \
    && a2enconf servername \
    && sed -ri 's#/var/www/html#/var/www/html/public#g' /etc/apache2/sites-available/*.conf \
    && mv "$PHP_INI_DIR/php.ini-production" "$PHP_INI_DIR/php.ini"

COPY docker/php.ini "$PHP_INI_DIR/conf.d/laptops.ini"
COPY docker/entrypoint.sh /usr/local/bin/laptops-entrypoint
COPY --from=vendor /app /var/www/html

RUN chmod +x /usr/local/bin/laptops-entrypoint \
    && chown -R www-data:www-data /var/www/html/storage /var/www/html/bootstrap/cache

ENV APP_ENV=production \
    APP_DEBUG=false \
    LOG_CHANNEL=stderr \
    SESSION_DRIVER=database \
    CACHE_STORE=file \
    QUEUE_CONNECTION=sync \
    PORT=80

WORKDIR /var/www/html
EXPOSE 80
ENTRYPOINT ["laptops-entrypoint"]
CMD ["apache2-foreground"]
