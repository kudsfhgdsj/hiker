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
deploy/smoke_test.py           # prüft den laufenden Stack
```

Betrieb auf dem Server (Proxy, Sicherung): `../deploy/README.md`.

Die API lauscht nur auf `127.0.0.1:${API_PORT}`; Migrationen laufen beim Start des Containers.

## Module

Ein Modul ist ein Paket unter `app/modules/<name>/` und exportiert in `__init__.py`:

- `MODULE_INFO = ModuleInfo(name=..., version=..., depends_on=(...))`
- `register(app)`: bindet die Router unter `/api/v1` ein

Aktiviert wird es über `ENABLED_MODULES`. Die Registry (`app/core/registry.py`) prüft,
dass alle Abhängigkeiten aktiv sind und keine Zyklen bestehen, und registriert in
Abhängigkeitsreihenfolge. Core importiert nie ein Modul direkt.

Andere Module nutzen von `auth` nur `app.modules.auth.deps` (`CurrentUser`, `AdminUser`,
`is_admin`), `app.modules.auth.service` und Nutzer-IDs.

## Dateien und Bilder

Dateien liegen hinter dem Interface `app.core.storage.Storage` (Standard: lokales
Dateisystem unter `STORAGE_PATH`), die Metadaten in `file_object`. Hochgeladene Bilder
(JPEG, PNG, WebP, höchstens `MAX_UPLOAD_MB`) werden geprüft, auf `IMAGE_MAX_EDGE_PX`
verkleinert und als JPEG ohne Metadaten neu kodiert. Ausgeliefert werden sie nur über
Endpunkte des jeweiligen Moduls, die die Berechtigung prüfen.

## Externe Dienste

Externe Dienste werden nur über Adapter angesprochen. `nutrition` nutzt Open Food Facts
(`app/modules/nutrition/sources.py`, Interface `FoodSource`), `protocols` die Höhenabfrage und
das Wetter von Open-Meteo (`elevation.py` mit `ElevationSource`, `weather.py` mit
`WeatherSource`, beide unter `app/modules/protocols/`). Die Tests
ersetzen die Adapter durch Attrappen und brauchen kein Netz. Die Daten stehen unter der ODbL: Bei
Lebensmitteln mit `source = openfoodfacts` muss die App die Quelle nennen.

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

Bei `--depends-on` nur die direkten Abhängigkeiten nennen (z. B. `gear_0001`, nicht zusätzlich
`auth_0001`, von dem `gear_0001` schon abhängt); doppelte Angaben bringen Alembic durcheinander.

Core-Tabellen (`file_object`) liegen im Zweig `core` unter `migrations/versions/`.
Das Datenbankschema umfasst alle installierten Module, unabhängig von `ENABLED_MODULES`.

Automatisch erzeugte Skripte vor dem Commit prüfen: `app.core.db.UTCDateTime` durch
`sa.DateTime(timezone=True)` ersetzen, damit Migrationen keinen App-Code importieren.

## Modul maps (Kartenkacheln)

`GET /api/v1/maps/tiles/{z}/{x}/{y}.png` liefert Kacheln aus dem eigenen Speicher
(`TILE_CACHE_PATH`). Eine fehlende Kachel wird einmal von `TILE_SOURCE_URL` geholt; nach
`TILE_CACHE_DAYS` fragt der Server mit dem gespeicherten ETag nach einer neuen Fassung. Ist die
Quelle nicht erreichbar, wird die gespeicherte Kachel weiter ausgeliefert. Es wird nichts auf
Vorrat geladen. Quelle nennen: © OpenStreetMap-Mitwirkende (ODbL).
