# hiker – Backend

FastAPI-Backend mit Modulregistry. Grundlage: `../DESIGN.md`, Regeln: `../CLAUDE.md`.

## Lokal starten (ohne Docker, SQLite)

```sh
cd backend
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp ../.env.example .env        # SECRET_KEY setzen, DATABASE_URL einkommentieren
.venv/bin/alembic upgrade heads
.venv/bin/uvicorn --factory app.main:create_app --reload
```

API-Dokumentation: <http://localhost:8000/api/v1/docs>, Health-Check: `/healthz`.

## Tests und Lint

```sh
.venv/bin/python -m pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

Die Tests laufen gegen SQLite im Arbeitsspeicher und brauchen keine `.env`.

## Mit Docker Compose

```sh
cp .env.example .env           # im Repository-Hauptverzeichnis; Werte ausfüllen
docker compose up -d --build
```

Die API lauscht nur auf `127.0.0.1:${API_PORT}`; Migrationen laufen beim Start des Containers.

## Module

Ein Modul ist ein Paket unter `app/modules/<name>/` und exportiert in `__init__.py`:

- `MODULE_INFO = ModuleInfo(name=..., version=..., depends_on=(...))`
- `register(app)`: bindet die Router unter `/api/v1` ein

Aktiviert wird es über `ENABLED_MODULES`. Die Registry (`app/core/registry.py`) prüft,
dass alle Abhängigkeiten aktiv sind und keine Zyklen bestehen, und registriert in
Abhängigkeitsreihenfolge. Core importiert nie ein Modul direkt.

Andere Module nutzen von `auth` nur `app.modules.auth.deps` (`CurrentUser`, `AdminUser`),
`app.modules.auth.service` und Nutzer-IDs.

## Migrationen

Jedes Modul hat eigene Migrationen in `app/modules/<name>/migrations/` als eigenen
Alembic-Zweig (Branch-Label = Modulname). Deshalb immer `heads` (Mehrzahl) verwenden.

Neue Migration für ein bestehendes Modul:

```sh
.venv/bin/alembic revision --autogenerate -m "add something" --head auth@head
```

Erstes Modul-Skript eines neuen Moduls: Pfad in `alembic.ini` unter `version_locations`
ergänzen, dann

```sh
.venv/bin/alembic revision --autogenerate -m "create gear tables" \
  --head base --branch-label gear --version-path app/modules/gear/migrations \
  --depends-on auth_0001
```

Das Datenbankschema umfasst alle installierten Module, unabhängig von `ENABLED_MODULES`.
