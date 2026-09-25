# Laptop Registratie

Webapplicatie voor het beheer van schoollaptops: laptops koppelen aan leerlingen en
leerkrachten, defecten opvolgen (tickets met tijdlijn en reserve-laptops), foto's per
laptop en uitleenkasten/magazijnen.

Versie 2 is een **Laravel/PHP**-applicatie die op een gewone **Plesk**-hosting draait
(geen Docker nodig). De functionaliteit en de database zijn identiek aan de vroegere
FastAPI/Python-versie; zie [Overstappen van de Python-versie](#overstappen-van-de-python-versie).

- Gebruikershandleiding: [USER_GUIDE.md](USER_GUIDE.md)
- Technische notities voor ontwikkelaars: [claude.md](claude.md)

## Vereisten

- PHP **8.3 of hoger** met de extensies `pdo_mysql`, `mbstring`, `fileinfo`, `openssl`
- MySQL 8 of MariaDB 10.6+
- HTTPS (nodig voor de camera op de fotopagina en voor de beveiligde sessiecookie)

## Installeren op Plesk (Laravel Toolkit)

1. **Subdomein aanmaken** — *Websites & domeinen → Subdomein toevoegen*, bv.
   `laptops.provil.be`. Zet meteen een gratis **Let's Encrypt**-certificaat op
   (*SSL/TLS-certificaten*).
2. **PHP instellen** — bij het subdomein: *PHP-instellingen* → versie **8.3 of 8.4**. Zet ook:
   - `upload_max_filesize` = `12M`
   - `post_max_size` = `16M`

   (foto's zijn max. 10 MB; base64-uploads vanop een iPhone zijn ~33 % groter).
3. **Database aanmaken** — *Databases → Database toevoegen*, bv. database `laptops`
   met een eigen gebruiker. Noteer naam, gebruiker en wachtwoord.
4. **App installeren** — *Laravel → Toepassing installeren*:
   - domein: het subdomein uit stap 1
   - bron: **Git-repository** `https://github.com/MeneerMeynen/laptop-registratie`, branch `main`
   - de toolkit zet de documentroot automatisch op `public/` en voert `composer install` uit.
5. **`.env` invullen** — in de Laravel Toolkit via *Omgevingsvariabelen* (of bewerk `.env`
   met *Bestanden*). Vertrek van [`.env.example`](.env.example) en vul minstens in:

   ```dotenv
   APP_ENV=production
   APP_DEBUG=false
   APP_URL=https://laptops.provil.be
   AUTH_USERNAME=admin
   AUTH_PASSWORD=<sterk wachtwoord>
   DB_CONNECTION=mariadb        # of mysql
   DB_DATABASE=laptops
   DB_USERNAME=<db-gebruiker>
   DB_PASSWORD=<db-wachtwoord>
   ```

   Genereer de `APP_KEY` via de toolkit (*Artisan → key:generate*).
6. **Database-tabellen aanmaken** — *Artisan → `migrate --force`*.
7. Open `https://laptops.provil.be` en log in met `AUTH_USERNAME` / `AUTH_PASSWORD`.

### Updates uitrollen

In de Laravel Toolkit: *Deployment → Pull updates* (of automatisch bij elke push). Stel als
deployment-script in:

```bash
composer install --no-dev --optimize-autoloader
php artisan migrate --force
php artisan config:cache
php artisan route:cache
php artisan view:cache
```

### Zonder Laravel Toolkit

Het kan ook met de gewone Plesk-functies: *Git* om de repository binnen te halen, bij
*Hosting-instellingen* de documentroot op `httpdocs/public` zetten, en via *SSH* (of de
Plesk-terminal) `composer install --no-dev`, `php artisan key:generate` en
`php artisan migrate --force` uitvoeren.

### Back-ups

Neem zowel de **database** als de map **`storage/app/uploads/`** (laptopfoto's) mee in de
Plesk-back-up.

## Overstappen van de Python-versie

De tabellen hebben exact dezelfde namen en kolommen, dus de bestaande gegevens kunnen
rechtstreeks mee: een database-dump en de fotomap.

> **Belangrijk:** importeer de dump in een **lege** database. Heeft de Laravel-app de
> tabellen al aangemaakt (`migrate`, of automatisch bij het starten van de Docker-versie),
> wis ze dan eerst met `php artisan db:wipe --force`. Anders weigert MariaDB de import
> (*Foreign key constraint is incorrectly formed*), omdat de nieuwe tabellen iets andere
> kolomtypes hebben.

### 1. Exporteren op de oude server

In de map van de oude (Python/Docker) installatie:

```bash
# database (gebruikt het root-wachtwoord dat al in de database-container staat)
docker exec mariadb-laptop sh -c 'exec mariadb-dump -uroot -p"$MARIADB_ROOT_PASSWORD" --single-transaction laptops' > laptops.sql

# foto's
docker compose cp app:/app/uploads/laptops ./laptops-fotos
```

Neem `laptops.sql` en de map `laptops-fotos` mee naar de nieuwe omgeving.

### 2a. Importeren in de lokale Docker-versie

In de map van de nieuwe (Laravel) versie, terwijl `docker compose up` draait:

```bash
docker compose exec app php artisan db:wipe --force
docker compose cp laptops.sql db:/tmp/laptops.sql
docker compose exec db sh -c "mariadb -ulaptops -plaptops laptops < /tmp/laptops.sql"
docker compose exec app php artisan migrate --force

docker compose cp laptops-fotos/. app:/var/www/html/storage/app/uploads/laptops/
docker compose exec app chown -R www-data:www-data storage/app/uploads
```

Log daarna opnieuw in (het wissen verwijdert ook de sessies).

### 2b. Importeren op Plesk

1. Tabellen wissen als `migrate` al gelopen heeft: Laravel Toolkit → *Artisan* → `db:wipe --force`
   (of in phpMyAdmin alle tabellen verwijderen).
2. *Databases → phpMyAdmin → Importeren* → `laptops.sql`. Gebruikt Plesk **MySQL** in plaats
   van MariaDB, verwijder dan eerst de eerste regel van `laptops.sql`
   (`/*M!999999\- enable the sandbox mode */`); MySQL kent die niet.
3. Laravel Toolkit → *Artisan* → `migrate --force` — voegt alleen de tabellen `migrations`
   en `sessions` toe. (De tabel `alembic_version` mag blijven staan.)
4. Upload de inhoud van `laptops-fotos` naar `storage/app/uploads/laptops/` (Plesk
   *Bestanden* of SFTP), zodat bv. `storage/app/uploads/laptops/<serienummer>/<bestand>.jpg`
   ontstaat.

> **Tijdzone:** de Python-versie draaide in een Docker-container in UTC; de Laravel-versie
> bewaart tijden in `Europe/Brussels`. Oude tijdstempels (koppel-/inleverdatum,
> opvolgingen) worden daardoor 1–2 uur vroeger getoond dan ze in Belgische tijd waren.

## Lokaal testen met Docker Desktop

Hiervoor hoef je alleen [Docker Desktop](https://www.docker.com/products/docker-desktop/) en
Git te installeren; PHP en de database draaien in containers.

```bash
git clone https://github.com/MeneerMeynen/laptop-registratie.git
cd laptop-registratie
docker compose up --build
# (andere mapnaam: voeg die toe na de URL van git clone)
```

De eerste keer duurt dit een paar minuten. Open daarna **http://localhost:8000** en log in
met **admin / test**. Een voorbeeld-CSV met leerlingen staat in `students_data/`.

- Stoppen: `Ctrl+C` (of `docker compose down`). Gegevens en foto's blijven bewaard in
  Docker-volumes.
- Alles wissen en opnieuw beginnen: `docker compose down -v`
- Na een `git pull` de nieuwe versie starten: `docker compose up --build`
- Ander wachtwoord: maak naast `compose.yaml` een bestand `.env` met `AUTH_PASSWORD=...`
- De database is bereikbaar op `localhost:3307` (gebruiker/wachtwoord `laptops`/`laptops`),
  bv. met HeidiSQL of DBeaver.
- De camera op de fotopagina werkt op `localhost` in je browser, maar niet vanaf je gsm
  (daarvoor is HTTPS nodig — test dat op Plesk).

## Lokaal ontwikkelen (zonder Docker)

```bash
composer install
cp .env.example .env              # zet DB_CONNECTION=sqlite, AUTH_PASSWORD=test, SESSION_SECURE_COOKIE=false
php artisan key:generate
touch database/database.sqlite
php artisan migrate
php artisan serve                 # http://localhost:8000
```

## Tests

```bash
php artisan test                                  # PHPUnit, SQLite in-memory
DB_CONNECTION=mariadb DB_DATABASE=laptops_test \
  DB_USERNAME=root DB_PASSWORD=secret php artisan test   # tegen MariaDB
```

De GitHub Actions-workflow draait de tests op SQLite én MariaDB.

End-to-end-tests (Playwright, optioneel) staan in [`tests/e2e/`](tests/e2e/conftest.py) en
draaien tegen een lokaal gestarte app met een lege database.
