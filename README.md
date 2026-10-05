# hiker

Selbst gehostete App für Tourenprotokolle, Ausrüstung und Essen: Android-App, Web-Frontend und
eigenes Backend. Ohne Google-Dienste, ohne Tracker.

| Teil | Technik | Ordner | Anleitung |
|---|---|---|---|
| Backend (REST-API) | FastAPI, PostgreSQL, Alembic | `backend/` | [backend/README.md](backend/README.md) |
| Web-Frontend | Flask, Jinja2, MapLibre GL JS | `web/` | [web/README.md](web/README.md) |
| Android-App | Flutter (nur Android), Drift, offline-fähig | `app/` | [app/README.md](app/README.md) |
| Betrieb | Docker Compose, Proxy-Beispiele, Backup | `deploy/` | [deploy/README.md](deploy/README.md) |

Architektur, Datenmodell, API und Phasenplan stehen in [DESIGN.md](DESIGN.md), die Regeln für die
Arbeit am Code in [CLAUDE.md](CLAUDE.md).

## Was die App kann (Phase 1)

- **Touren**: Protokoll mit Beschreibung, GPX-Track (Strecke, Höhenmeter, Herzfrequenz), Karte und
  Höhenprofil, Fotos am Track, Gipfel und Pässe entlang der Strecke, Wetter, Kalorienschätzung.
- **Ausrüstung** und **Essen**: eigene Listen, gemeinsamer Katalog, Barcode-Suche (Open Food Facts).
- **Teilen**: mit anderen Nutzern (lesen oder bearbeiten) und über öffentliche Links.
- **Verlauf**: jede Änderung an einer Tour bleibt erhalten und lässt sich wiederherstellen.

## Schnellstart mit Docker

```sh
cp .env.example .env          # SECRET_KEY, WEB_SECRET_KEY, POSTGRES_PASSWORD, PUBLIC_BASE_URL setzen
docker compose up -d --build
deploy/smoke_test.py          # prüft API und Web-Frontend einmal von vorn bis hinten
```

Danach laufen die API auf `127.0.0.1:8010` und das Web-Frontend auf `127.0.0.1:8011`. Beide sind
nur lokal erreichbar; nach außen bringt sie der Reverse Proxy des Servers
(siehe [deploy/README.md](deploy/README.md)).

**Der erste registrierte Nutzer wird Administrator.** Lege also zuerst dein eigenes Konto an und
stelle danach `REGISTRATION_MODE=closed`, wenn sich niemand sonst registrieren soll.

## Tests

```sh
(cd backend && .venv/bin/python -m pytest)      # API
(cd web && .venv/bin/python -m pytest)          # Web-Frontend
(cd app && flutter analyze && flutter test)     # Android-App
```

## Datenquellen

Kartendaten und Orte: © OpenStreetMap-Mitwirkende (ODbL). Lebensmitteldaten: Open Food Facts
(ODbL). Wetter und Höhen: Open-Meteo.
