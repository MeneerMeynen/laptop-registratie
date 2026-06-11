# Project: Laptop Registratie

## Tech stack
- FastAPI + SQLAlchemy ORM
- MariaDB (productie), SQLite (tests)
- HTML/CSS/JS UI geserveerd vanuit FastAPI (templates via Jinja2)
- Alpine.js voor reactieve UI
- Pytest tests
- Alembic voor databasemigraties

## UI-tabs
1. **Registreer** — leerling selecteren, barcode/serienummer scannen en koppelen
2. **Beheer studenten** — CSV-import, zoeken, filteren, verwijderen
3. **Laptops** — laptop issue tracker met tijdlijn per laptop
4. **Foto's** — foto's per laptop uploaden en bekijken

## Kernfunctionaliteit

### Authenticatie
- Eén gedeelde login voor de hele applicatie (geen `users`-tabel)
- Credentials uit env vars: `AUTH_USERNAME`, `AUTH_PASSWORD`, `SESSION_SECRET`
- `SESSION_SECRET` genereren: `python -c "import secrets; print(secrets.token_hex(32))"`
- Sessie via signed cookie (Starlette `SessionMiddleware`), 8u geldig
- `app/auth.py::AuthMiddleware` gate alle requests behalve `/login`, `/logout`, `/static/*` en `/favicon*`
- HTMX-requests krijgen bij verlopen sessie `204` + `HX-Redirect: /login`; HTML-requests `303` redirect; API-requests `401`
- Uitloggen via knop rechtsboven in de UI (POST `/logout`)
- Productie-startup faalt expliciet als `AUTH_PASSWORD` of `SESSION_SECRET` ontbreekt (tenzij `DEBUG=true`)

### Laptop issue tracker (tab: Tickets)
- Zoeken op serienummer, issues aanmaken/bewerken/verwijderen
- Entries (tijdlijn) per issue toevoegen/bewerken/verwijderen
- Status-filter, koppeling aan student, linked_at tracking

### Leerlingkoppeling (tab: Registreer)
- Studenten worden uit CSV geïmporteerd in tabel `students`
- Laptops worden gekoppeld in tabel `laptops`
- Na koppelen blijft focus op het scanveld; volgende leerling wordt automatisch geselecteerd
- Navigatiebarcodes: `1UP`, `1DOWN`
- Speciale barcode `eigen laptop` zet `laptops.eigen_laptop = true` (lege serial, uniek per student)

### Studentenbeheer (tab: Instellingen)
- CSV-upload via UI, upsert op `students`
- `students.last_import` wordt gezet bij elke import; studenten met oudere datum krijgen badge `Uitgeschreven`
- Zoekbalk zoekt op: instellingsnummer, naam, voornaam, klas, klascode, klasnummer, gebruikersnaam, pointer, stamnummer
- Filterknop `Toon uitgeschreven`, multi-select lijst, `Selecteer alle`, verwijderknop
- Na verwijderen blijft de UI op tab `Beheer studenten`; zoekopdracht en filter blijven behouden

### Foto's (tab: Foto's)
- Foto's uploaden per serienummer (file upload of base64 voor iOS)
- Foto's bekijken in gallery/lightbox, verwijderen
- Opgeslagen in `uploads/laptops/`, geserveerd via `/uploads/laptops`

## Databaseschema (belangrijkste velden)
- `students.last_import` — tijdstip van laatste CSV-import
- `laptops.eigen_laptop` — boolean, true als leerling eigen laptop heeft
- Migraties via Alembic (`alembic upgrade head`)

## API-routes

| Router | Prefix / route | Doel |
|--------|---------------|------|
| `api/students.py` | `GET /api/students` | Alle studenten ophalen |
| | `POST /api/students/import` | CSV-import |
| | `DELETE /api/students` | Studenten verwijderen |
| `api/laptops.py` | `POST /api/laptops/link` | Laptop koppelen |
| | `POST /api/laptops/{id}/unlink` | Laptop inleveren (ontkoppelen) |
| | `GET /api/laptops/export` | CSV-export beheeroverzicht |
| `api/photos.py` | `GET /api/photos/{serial}` | Foto's per serienummer |
| | `POST /api/photos` | Foto uploaden (file) |
| | `POST /api/photos/base64` | Foto uploaden (base64, iOS) |
| | `DELETE /api/photos/{id}` | Foto verwijderen |
| `api/laptop_issues.py` | `/api/laptop-issues/…` | Issue CRUD + entries CRUD |
| `api/ui.py` | `GET /` | Hoofdpagina |
| | Partials voor HTMX-updates | |

## Belangrijke bestanden
- `app/main.py` — app factory, router registratie, static mounts
- `app/api/laptops.py` — koppelen/ontkoppelen
- `app/api/students.py` — import/verwijderen
- `app/api/photos.py` — foto-upload en -beheer
- `app/api/laptop_issues.py` — issue tracker
- `app/api/ui.py` — UI-routes en partials
- `app/models/` — Student, Laptop, LaptopIssue, LaptopIssueEntry, LaptopPhoto
- `app/schemas/` — Pydantic schemas
- `app/services/` — laptop_service, student_import, student_service, photo_service, laptop_issue_service
- `app/templates/index.html` — hoofd-UI (Alpine.js, alle tabs)
- `app/templates/photos.html` — foto-pagina
- `alembic/` — migratiescripts

## Versie beheren & releases

De versie staat op één plek: `pyproject.toml` (`version = "x.y.z"`).  
`importlib.metadata` leest die waarde at runtime — `app/main.py` en `app/api/ui.py` gebruiken dit, en de UI toont hem rechtsonder als `vX.Y.Z`.

### Release uitvoeren

```bash
# 1. Bump de versie in pyproject.toml
#    Gebruik semantic versioning: MAJOR.MINOR.PATCH
#    - PATCH: bugfix (1.0.1)
#    - MINOR: nieuwe functionaliteit, backwards compatible (1.1.0)
#    - MAJOR: breaking changes (2.0.0)

# 2. Commit
git add pyproject.toml
git commit -m "bump version to 1.x.y"

# 3. Tag aanmaken en pushen
git tag v1.x.y
git push origin main
git push origin v1.x.y
```

> De `*.egg-info/` map is lokaal gegenereerd en staat in `.gitignore` — niet committen.  
> Docker bouwt de versie correct in via `pip install` tijdens de image-build.

## Docker
- `Dockerfile`, `compose.yaml` en `entrypoint.sh` staan in de projectroot
- Gebruik altijd `docker compose up --build` vanuit de root
- `uploads/` wordt als persistent volume gemount

## Tests
- Pytest, alle tests groen
- SQLite in-memory voor tests
- E2e-tests (Playwright) in `tests/e2e/`

## Testen via Docker in Claude-sessies

De Docker stack (nginx + app + MariaDB) is de productieomgeving. Om in Claude de UI te kunnen testen via het preview paneel of met de Claude-in-Chrome tools, gebruik onderstaande workflows.

### Workflow A — Preview paneel (interactieve UI-verificatie)

Gebruik `preview_start` met de `app` config uit `.claude/launch.json`. Deze start `docker compose up --build` onder controle van het preview paneel en koppelt aan poort **8000** (directe FastAPI, geen HTTPS-cert vereist).

**Vereisten vóór starten:**
1. Controleer of de stack al extern draait: `docker compose ps`
2. Als containers draaien: `docker compose down` (preview_start kan geen poort claimen die al in gebruik is)
3. Daarna: `preview_start app`

Na opstarten (ca. 15–30s, langer bij eerste build) zijn deze tools bruikbaar:
- `preview_snapshot` — DOM-inhoud en structuur
- `preview_click` / `preview_fill` — interacties testen
- `preview_console_logs` / `preview_logs` / `preview_network` — fouten opsporen
- `preview_screenshot` — visueel bewijs voor de gebruiker

De MariaDB healthcheck heeft `retries: 10` met `interval: 5s`, dus de eerste startup kan tot 60s duren.

### Workflow B — E2e-tests draaien in Docker

Voor headless end-to-end tests (Playwright) zonder preview paneel:

```bash
docker compose run --rm test-e2e
```

De `test-e2e` service gebruikt het Playwright image en draait alle tests in `tests/e2e/` tegen `http://app:8000` binnen het Docker-netwerk. De `app`-service moet daarvoor draaien (`docker compose up -d app`).

### Workflow C — Unit-tests in Docker

```bash
docker compose run --rm test
```

Draait `pytest -v` tegen een `laptops_test` database op de MariaDB container. Gebruikt dezelfde image als de app.

### Poortoverzicht
| Service | Poort | Protocol | Gebruik |
|---------|-------|----------|---------|
| `app`   | 8000  | HTTP     | Direct FastAPI — **gebruik deze voor preview_start** |
| `nginx` | 80    | HTTP     | Redirect naar HTTPS |
| `nginx` | 443   | HTTPS    | Mobiele workflow met mkcert-certs (alleen via browser) |
| `db`    | 3306  | MySQL    | Debug-toegang tot MariaDB |
