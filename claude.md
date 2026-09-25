# Project: Laptop Registratie

## Tech stack
- Laravel 13 (PHP 8.3+), Eloquent + query builder
- MariaDB/MySQL (productie op Plesk), SQLite (lokaal en tests)
- Blade-templates, HTMX voor partials, Alpine.js voor reactieve UI (geen build-stap: gewone JS/CSS in `public/static/`)
- PHPUnit-featuretests (`php artisan test`), optionele Playwright-e2e-tests in `tests/e2e/`
- Hosting: Plesk met Laravel Toolkit (zie README.md)
- Lokaal testen: `docker compose up --build` → http://localhost:8000 (admin / test). `Dockerfile` = PHP 8.3 + Apache; `docker/entrypoint.sh` voert migraties uit en bewaart een gegenereerde `APP_KEY` in het storage-volume

Versie 2.0.0 is een 1-op-1-port van de FastAPI-versie (v1.1.0, nog te vinden op `main`-historiek):
zelfde URL's, JSON-velden, statuscodes en databaseschema, zodat de frontend-JS ongewijzigd bleef.

## UI-tabs
1. **Tickets** — laptop issue tracker met tijdlijn per laptop
2. **Laptop info** — rapport per serienummer
3. **Registreer** — leerling selecteren, barcode/serienummer scannen en koppelen
4. **Instellingen** — leerlingen (CSV-import), laptops, uitleenkasten en magazijnen
5. **Foto's** — foto's per laptop bekijken; opnemen via de mobiele pagina `/photos`

## Kernfunctionaliteit

### Authenticatie
- Eén gedeelde login (geen users-tabel): `AUTH_USERNAME` / `AUTH_PASSWORD` in `.env` (`config/laptops.php`); leeg wachtwoord = niemand kan inloggen
- Sessie (database-driver) 8 u geldig; sessie-ID wordt vernieuwd na inloggen
- `App\Http\Middleware\RequireLogin` beschermt alles behalve `/login`, `/logout`, `/up` en `public/static/*`
- Niet ingelogd: HTMX-request → `204` + `HX-Redirect: /login`; HTML (`Accept: text/html`) → `303` naar `/login?next=…`; anders `401 {"detail": "Not authenticated"}`
- CSRF: `public/static/js/csrf.js` voegt het token uit `<meta name="csrf-token">` toe aan elke niet-GET `fetch()` en elke HTMX-request. Nieuwe pagina's met eigen `<head>` moeten die meta-tag + script ook laden
- Verlopen sessie/CSRF (419): HTMX → `HX-Redirect: /login`, API → `{"detail": "Sessie verlopen…"}`

### Foutafhandeling
- Services gooien `App\Support\DetailException(status, detail)` → JSON `{"detail": ...}` (zoals FastAPI's HTTPException). De frontend toont `data.detail`
- Uitzondering: bij koppelen aan een leerling die al een laptop heeft is `detail` een object met `requires_confirmation`, `existing_serials`, `message`, `stamnummer`
- Datums in JSON: `Y-m-d\TH:i:s` zonder tijdzone (`Fmt::iso`), datums `Y-m-d`; tijdzone van de app is `Europe/Brussels`

### Laptop issue tracker (tab: Tickets)
- Zoeken op serienummer, issues aanmaken/bewerken/verwijderen, statussen `aangemeld` / `open` / `gesloten`
- Opvolgingen (tijdlijn) per issue via HTMX (`/ui/laptop-issues/...`)
- Reserve-laptop meegeven bij een issue; bij sluiten wordt die automatisch vrijgegeven + tijdlijnregel
- Sidebar-filter stuurt herhaalde `?statuses=a&statuses=b` — PHP leest dat niet als lijst, daarom `LaptopIssueController::repeatedQueryParam()`
- Afdrukbare defect-/herstelfiche: `/laptop-issues/{id}/fiche`

### Leerlingkoppeling (tab: Registreer)
- Na koppelen blijft focus op het scanveld; volgende leerling wordt automatisch geselecteerd
- Navigatiebarcodes: `1UP`, `1DOWN`; `CLEAR` wist het veld
- Speciale barcode `eigen laptop` zet `laptops.eigen_laptop = true` (lege serial)
- Opnieuw dezelfde laptop scannen is idempotent (geen nieuw historiekrecord)
- Laptop uit een **magazijn** mag toegekend worden (hetzelfde record verlaat het magazijn); laptop uit een **kast** niet
- Inleveren met ontbrekende hoes/oplader maakt automatisch een issue (categorie `Accessoires`)

### Studentenbeheer (tab: Instellingen)
- CSV-upload, upsert op `students`; `students.last_import` wordt gezet bij elke import; wie een oudere datum heeft dan de laatste import van dezelfde groep krijgt badge `Uitgeschreven`
- Leerkrachten staan in dezelfde tabel met `is_leerkracht = true`; import via `POST /ui/students/import?leerkracht=true` (API: `POST /api/students/import?leerkracht=true`)
- Scheidingsteken wordt gedetecteerd (`;`, tab of `,`); headers hoofdletterongevoelig; `Instellingsnummers` → `instellingsnummer`, `Klasnr` → `klasnummer`
- Leerkracht zonder `Stamnummer` krijgt `Gebruikersnaam` als sleutel; `Afkorting` → `students.afkorting`
- Kolommen `StandaardPaswoord`, `Betaalkaart` en `Pincode` worden expliciet genegeerd (nooit opgeslagen)
- Een import zet nooit een leerling om in een leerkracht of andersom

### Foto's
- Upload per serienummer (multipart `POST /api/photos?serial_number=…` of base64 `POST /api/photos/base64`)
- Opgeslagen in `storage/app/uploads/laptops/<serial>/<uuid>.<ext>` (`UPLOAD_DIR`), geserveerd via `/uploads/laptops/...` **achter de login**
- Validatie tegen path traversal: serienummer `^[A-Za-z0-9._-]{1,100}$`, extensies jpg/jpeg/png/webp, max 10 MB
- Barcode-scanner op `/photos`: BarcodeDetector → zxing-wasm (`public/static/zxing-wasm/`, v1.3.5 uit npm) → ZXing JS

## Databaseschema
- Eén migratie: `database/migrations/2026_09_24_000001_create_laptop_registratie_schema.php` = Alembic-revisie 0013 van de Python-versie
- Elke tabel wordt alleen aangemaakt als ze nog niet bestaat → werkt ook op een geïmporteerde database van de Python-versie
- Nieuwe schemawijzigingen: **nieuwe** migratie toevoegen (niet de bestaande aanpassen)
- Belangrijkste velden: `students.last_import`, `students.is_leerkracht`, `students.afkorting`, `laptops.eigen_laptop`, `laptops.is_reserve`, `laptops.alias`, `laptops.storage_cabinet_id`, `laptops.linked_at`/`unlinked_at` (historiek: een serienummer kan meerdere records hebben, max. één actief), `storage_cabinets.kind` (`kast`/`magazijn`)

## Structuur
- `routes/web.php` — alle routes (UI, HTMX-partials en JSON-API)
- `app/Http/Controllers/` — `UiController`, `AuthController`, `LaptopController`, `LaptopIssueController`, `StudentController`, `StorageCabinetController`, `PhotoController`
- `app/Services/` — businesslogica (1-op-1 met de vroegere `app/services/*.py`)
- `app/Support/` — `DetailException`, `Fmt` (formattering), `Sql` (portabele LIKE/CONCAT voor MariaDB én SQLite), `CsvWriter`
- `resources/views/` — `index.blade.php` (hoofd-UI), `partials/*` (HTMX), `photos`, `barcodes`, `issue_fiche`, `login`
- `public/static/` — CSS, `laptop_app.js`, `photo_app.js`, `csrf.js`, vendor-libs
- `Dockerfile`, `compose.yaml`, `docker/` — lokale testomgeving (niet nodig voor Plesk)

## Aandachtspunten bij Blade
- Alpine-attributen (`@click`, `@keydown`, …) zijn geen Blade-directives en blijven staan
- Een Blade-directive vlak na een letter (bv. `Leerkracht@if`) wordt **niet** herkend — bouw zulke tekst in `@php`
- `{{ }}` escapet (htmlspecialchars); waarden die in inline JS-strings belanden (`'{{ ... }}'`) blijven dus HTML-ge-escaped zoals voorheen

## Versie beheren
- Versie staat in `config/laptops.php` (`version`) en wordt rechtsonder getoond als `vX.Y.Z`
- Semantic versioning; tag releases als `vX.Y.Z`

## Tests
- `php artisan test` (SQLite in-memory; `DB_CONNECTION=mariadb …` voor MariaDB) — CI draait beide
- Dependencies zijn vastgelegd voor PHP 8.3 (`config.platform.php` in composer.json); verhoog dat pas als Plesk overal 8.4 heeft
- Testhelpers in `tests/TestCase.php` (`addStudent`, `link`, `unlink`, `createReserve`, `createIssue`); standaard ingelogd, zet `$loggedIn = false` om de login-gate te testen
- Let op: de Laravel-testclient stuurt standaard `Accept: text/html`; stuur `Accept: */*` om het API-gedrag (401 i.p.v. redirect) te testen
- E2e: `pytest tests/e2e --base-url http://localhost:8000` tegen een app met lege database
