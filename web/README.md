# hiker – Web-Frontend

Server-gerenderte Web-Oberfläche (Flask + Jinja2) für hiker. Sie ist ein reiner Client der
REST-API: kein eigener Datenbestand, keine eigene Fachlogik. Rechte, Historie, Konfliktschutz
und Schätzungen kommen von der API (siehe `DESIGN.md`, Abschnitt 9a).

## Umfang

- Anmeldung in zwei Schritten (Passwort, dann Code der Authenticator-App; optional SSO über
  OpenID Connect), Registrierung mit
  doppelter Passworteingabe, zweiten Faktor einrichten, Passwort ändern, Profil
- Verwaltung für Administratoren: Nutzer ansehen, entfernen, Passwort und zweiten Faktor zurücksetzen
- Ausrüstung: Liste mit Filtern, Formular, Bild, Summen mit Gruppierung, Tags und Kategorien, Katalog
- Essen: eigene Lebensmittel, Suche im Katalog, Barcode von Hand, Übernahme aus dem Katalog
- Touren: Liste, Detail mit Karte und Höhenprofil, Editor, GPX- und Foto-Upload, Verlauf mit
  Wiederherstellen, Teilen, öffentliche Links, Kontakte, Export
- Öffentliche Linkseite `/p/<token>` ohne Anmeldung, `noindex`

- Auf der Karte bearbeiten: Wegpunkte, Fotoposition, Start und Ende, Track zeichnen, Wetter für
  einen eigenen Punkt
- Packlisten, die sich in eine Tour übernehmen lassen
- Planung: Routen auf der Karte planen (Punkte setzen und verschieben, den Wegen folgen oder
  Luftlinie – für alle oder einzelne Abschnitte –, Schwierigkeit T1–T6, Klettersteige),
  Eckdaten mit geschätzter Gehzeit, Höhenprofil, GPX-Download. Die Karte füllt das Fenster;
  Ebenen, Darstellung und Schwierigkeit liegen als Aufklappfelder an ihrem oberen Rand.
  Gehzeit nach DAV, SAC, „Profi“ oder eigenen Werten, die sich unter einem Namen speichern
  lassen (nur für den Ersteller). Tags statt Datum; mit einem Startzeitpunkt zeigt die Seite
  Sonnenaufgang und -untergang, die Uhrzeit an jeder Stelle des Profils und warnt, wenn die
  Tour ins Dunkle reicht. Der Planer braucht JavaScript.
  Aus einer Route lässt sich eine Tour anlegen; hat die Tour einen Track, stellt
  „Vergleichen“ Plan und Gegangenes gegenüber (Zahlen, Abweichung, beide Linien auf der
  Karte). Eine GPX-Datei lässt sich in der Routenliste als Route importieren.
- Statistik (`/stats`): Summen aller eigenen Touren, Tage unterwegs als Jahresraster, alle
  Tracks auf einer Karte, bestiegene Gipfel und Wunschgipfel.
- Karte (`/map`): die Karte ansehen, ohne zu planen. Ein Klick nennt Gipfel, Hütte oder Weg
  mit Schwierigkeit und die Sonnenzeiten des Tages dort (für Gipfel auch bei freiem Horizont)
  und führt auf Wunsch in den Planer. Ebenen: Hangneigung mit einstellbaren Winkeln,
  Lawinengefahr, Schnee und Wetter auch für einen Tag im letzten Jahr, Regenradar und Wolken
  mit Zeitregler, Umschalter 2D/3D. Das Suchfeld in jeder Karte findet Gipfel, Hütten, Orte
  und Seen der eigenen Karte nach Namen.

Nicht im Web: Kamera-Scanner und Offline-Betrieb (das kann die Android-App).

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
  static/         style.css, site.js, tour.js, map_edit.js, plan.js, map_view.js, map_layers.js,
                  profile.js, vendor/maplibre-gl
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

## Anmeldung

Solange einer Sitzung der zweite Faktor oder ein neues Passwort fehlt, ist nur die Seite
erreichbar, die das erledigt (`/mfa/setup`, `/password`). Der QR-Code für die Authenticator-App
wird auf dem Server als SVG erzeugt (`segno`); Wiederherstellungscodes und vorläufige Passwörter
werden genau einmal angezeigt und nirgends im Web-Frontend gespeichert.

SSO: Beim OIDC-Anbieter `<PUBLIC_BASE_URL>/login/sso/callback` als Redirect-URI eintragen und in
der `.env` der API `OIDC_ISSUER`, `OIDC_CLIENT_ID` und `OIDC_CLIENT_SECRET` setzen. Dann zeigt die
Anmeldeseite den Knopf „Mit … anmelden“.

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
Reverse Proxy – der mitgelieferte Caddy (Profil `proxy`) oder ein vorhandener – leitet `/api/` an
die API und alles andere an das Web-Frontend.
