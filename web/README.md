# hiker – Web-Frontend

Server-gerenderte Web-Oberfläche (Flask + Jinja2) für hiker. Sie ist ein reiner Client der
REST-API: kein eigener Datenbestand, keine eigene Fachlogik. Rechte, Historie, Konfliktschutz
und Schätzungen kommen von der API (siehe `DESIGN.md`, Abschnitt 9a).

## Umfang

- Anmeldung, Registrierung, Profil
- Ausrüstung: Liste mit Filtern, Formular, Bild, Summen mit Gruppierung, Tags und Kategorien, Katalog
- Essen: eigene Lebensmittel, Suche im Katalog, Barcode von Hand, Übernahme aus dem Katalog
- Touren: Liste, Detail mit Karte und Höhenprofil, Editor, GPX- und Foto-Upload, Verlauf mit
  Wiederherstellen, Teilen, öffentliche Links, Kontakte, Export
- Öffentliche Linkseite `/p/<token>` ohne Anmeldung, `noindex`

Nicht im Web: Kamera-Scanner, Offline-Betrieb, Track zeichnen, Fotoposition von Hand verschieben
(das kann die Android-App bzw. folgt später).

## Lokal starten

Die API muss laufen (siehe `backend/README.md`, Standard `http://127.0.0.1:8000`).

```sh
cd web
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
export WEB_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
export WEB_COOKIE_SECURE=false          # nur lokal ohne HTTPS
.venv/bin/flask --app hiker_web.wsgi run --port 8020
```

## Konfiguration (Umgebungsvariablen)

| Variable | Bedeutung | Standard |
|---|---|---|
| `WEB_SECRET_KEY` | signiert das Sitzungs-Cookie, mindestens 32 Zeichen (Pflicht) | – |
| `API_BASE_URL` | Adresse der API aus Sicht dieses Dienstes, ohne `/api/v1` | `http://127.0.0.1:8000` |
| `WEB_SESSION_DIR` | Verzeichnis der serverseitigen Sitzungen | `./data/web-sessions` |
| `WEB_SESSION_DAYS` | ungenutzte Sitzungen werden danach gelöscht; wie `REFRESH_TOKEN_TTL_DAYS` der API wählen | `30` |
| `WEB_COOKIE_SECURE` | Cookie nur über HTTPS; `false` nur für lokale Entwicklung | `true` |
| `MAX_UPLOAD_MB` | Größe einer Datei wie in der API; begrenzt Uploads | `15` |
| `MAP_TILE_URL` | Kachelquelle der Karte; leer = Kacheln vom eigenen Server | `/tiles/{z}/{x}/{y}.png` |

## Aufbau

```
hiker_web/
  __init__.py     create_app, Fehlerseiten, Sicherheits-Header, Navigation
  api.py          Client der REST-API (Token-Erneuerung, Fehler)
  sessions.py     serverseitige Sitzungen als Dateien
  security.py     Login-Prüfung, CSRF, Token aus Logs entfernen
  forms.py        Formularwerte lesen, Dateien durchreichen
  formatting.py   deutsche Zahlen-, Gewichts- und Datumsformate
  texts_de.py     alle Texte der Oberfläche
  views/          je Modul ein Blueprint: auth, gear, nutrition, protocols, public
  templates/      Jinja2-Vorlagen
  static/         style.css, site.js, tour.js, vendor/maplibre-gl
```

Seiten eines Moduls gibt es nur, wenn die API es unter `/modules` meldet.

## Sicherheit

- Access- und Refresh-Token liegen nur auf dem Server (Sitzungsdatei, Rechte 600). Der Browser
  bekommt ein signiertes Cookie mit der Sitzungs-ID (`HttpOnly`, `Secure`, `SameSite=Lax`).
- Jedes Formular trägt ein CSRF-Token; ohne gültiges Token antwortet der Server mit 400.
- `Content-Security-Policy`: Skripte und Stile nur vom eigenen Server, Kartenkacheln nur von
  `MAP_TILE_URL`. Keine Inline-Skripte.
- Bilder, GPX und Export werden mit dem Token des Nutzers von der API durchgereicht.
- `Referrer-Policy: strict-origin-when-cross-origin`: fremde Server erfahren nur die Herkunft,
  nie den Pfad. Ganz ohne Referer geht es nicht – der Kachelserver von OpenStreetMap lehnt
  solche Anfragen ab („Access blocked“).
- Öffentliche Links: `X-Robots-Tag: noindex, nofollow`, `Cache-Control: no-store`. Die Tokens erscheinen nicht im Log (Filter in `security.py`; gunicorn
  läuft ohne Zugriffs-Log). **Der Reverse Proxy muss `/p/…` ebenfalls aus seinem Log halten.**
- Die Client-Adresse wird an die API weitergegeben, damit deren Rate-Limit je Besucher zählt.

## Karte

MapLibre GL JS 5.24.0 (BSD-3-Clause) liegt unverändert in `static/vendor/maplibre-gl/` und wird
vom eigenen Server ausgeliefert, in der CSP-Variante mit eigener Worker-Datei. Aktualisieren:
Paket `maplibre-gl` von npm laden und `dist/maplibre-gl-csp.js`, `dist/maplibre-gl-csp-worker.js`,
`dist/maplibre-gl.css` sowie `LICENSE.txt` ersetzen, `VERSION.txt` anpassen. Version 6 liefert
nur noch ES-Module und braucht eine andere Einbindung.

Die Kacheln kommen vom eigenen Server: `/tiles/{z}/{x}/{y}.png` reicht die Kacheln durch, die
die API im Modul `maps` zwischenspeichert (beim ersten Ansehen von OpenStreetMap geholt, danach
lokal). Hinter dem Reverse Proxy geht es mit `MAP_TILE_URL=https://<domain>/api/v1/maps/tiles/{z}/{x}/{y}.png`
ohne den Umweg über das Web-Frontend.

## Tests

```sh
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/pytest
```

Die Tests laufen mit dem Flask-Testclient; die API ist durch eine Attrappe ersetzt
(`tests/conftest.py`, `FakeApi`). Das JavaScript (Karte, Höhenprofil) hat keine automatischen
Tests; es wurde am 04.10.2026 von Hand mit Firefox (headless, Playwright) gegen ein laufendes
Backend geprüft.

## Betrieb

Im Compose-Stack läuft der Dienst `web` mit gunicorn nur auf `127.0.0.1:${WEB_PORT}`. Der
Reverse Proxy leitet `/api/` an die API und alles andere an das Web-Frontend.
