# hiker – Designgrundlage

Stand: 03.10.2026 (v3) · Zweck: Grundlage zur Umsetzung mit Claude Code
Regeln für Claude Code stehen in der separaten Datei `CLAUDE.md`.

## 1. Ziele und Leitplanken

- Android-App zuerst, später dieselbe Codebasis im Browser (auf dem eigenen Server gehostet).
- Module: **Protokolle**, **Ausrüstung** und **Ernährung** (jetzt), **Planung** und **Berichte** (später).
- **Strikt modular**: Jedes Modul ist in sich abgeschlossen und kann hinzugefügt/entfernt werden, ohne andere Module anzufassen.
- **Keine Google-Dienste**: kein Firebase, kein Google Maps, kein FCM, kein Google Sign-In, kein Google ML Kit.
- **Eigener Server** (Self-Hosting) als Zielplattform.
- Offline-fähig (in den Bergen oft kein Netz): lokal speichern, später synchronisieren.
- Datenhoheit beim Nutzer: Export als JSON, alles selbst hostbar.

Hinweis: Flutter/Dart stammen von Google, sind aber Open Source und benötigen keine Google-Dienste. Falls das später stört, ist die Alternative Kotlin Multiplatform oder eine PWA; die Architektur (API-first) bleibt gleich.

## 2. Getroffene Entscheidungen

| Thema | Entscheidung | Auswirkung |
|---|---|---|
| Hosting | Eigener, bereits vorhandener Server, Ubuntu 26.04, Domain vorläufig `hiker.lacasa.internal` (endgültige Domain später, nur über `PUBLIC_BASE_URL`) | Läuft neben anderen Diensten, Reverse-Proxy-Konzept in Abschnitt 11 |
| Teilen mit Usern | `read` und `edit` | Edit = Textfelder, Listen und Fotos, **nicht** GPX/Punkte/Freigaben/Löschen |
| Historie | Jede Änderung wird als Revision gespeichert | Abschnitt 6.5 |
| Partner | Per Nutzerkonto verknüpfbar, sonst Platzhalter, später austauschbar | Kontakte (6.4) |
| Teilen per Link | Zufälliges UUID-Token, nur lesend, widerrufbar | Abschnitt 7 |
| Kartenlayer-Lizenzen | Zurückgestellt bis Phase 2 | Tile-URL konfigurierbar |
| Ausrüstung | Eigene Datenbank + gemeinsamer Katalog | Modul `gear` |
| Essen | Eigene Datenbank + Barcode-Scan + gemeinsamer Katalog | Modul `nutrition` |
| Kalorienverbrauch | Manuell, sonst automatische Schätzung | Abschnitt 7 |
| GPX-Quelle | Meist Garmin-Uhr; zusätzlich einfache, manuell erstellte Tracks | Tolerante Auswertung + Zeichenwerkzeug |
| Fotos auf Tracks | Darstellung angelehnt an wanderer (Abschnitt 9) | Fotos werden dem Track zugeordnet |
| Wetter | Automatisch aus Track, sonst Start/Ende auf Karte | Karte schon in Phase 1 |
| Registrierung | Per `REGISTRATION_MODE` schaltbar (`open` \| `closed`); Einladungen bei Bedarf später | Nach dem Anlegen der Konten auf `closed` stellen |
| Admin | Der erste registrierte Nutzer wird `admin` | Katalogmoderation |
| Refresh-Tokens | Zufällige Tokens, gehasht in der Datenbank, Rotation bei jeder Nutzung, widerrufbar | Tabelle `refresh_token`; erneute Nutzung eines verbrauchten Tokens beendet alle Sitzungen des Nutzers |
| Datenbankzugriff | SQLAlchemy 2 synchron (psycopg), Endpunkte im Threadpool | Einfacher Code und einfache Tests |
| Migrationen | Je Modul ein eigener Alembic-Zweig in `modules/<name>/migrations` | `alembic upgrade heads`; Schema umfasst alle installierten Module |
| Fehlerformat | `{"error": {"code", "message"}}` für fachliche Fehler | Client übersetzt anhand von `code` |

## 3. Technologie-Stack

| Bereich | Wahl | Begründung |
|---|---|---|
| App/Web-Client | Flutter (Android zuerst, `flutter build web` später) | Eine Codebasis |
| State/DI | Riverpod | Testbar, modular |
| Routing | go_router | Deep Links, Web-tauglich |
| Lokale DB | Drift (SQLite) | Offline, typsicher, auch im Web |
| HTTP | dio | Interceptors (Auth, Retry) |
| Karten | MapLibre (`maplibre_gl`) | Open Source; ab Phase 1 für Track, Fotos, Punktauswahl |
| Kartenquellen | Konfigurierbare Tile-URL (Standard: OpenStreetMap) | Lizenzfragen später |
| Diagramme | Eigenes Höhenprofil-Widget (Höhe, Herzfrequenz, Foto-Marker) | Foto-Marker und Kartenverknüpfung nötig |
| Barcode-Scan | `flutter_zxing` (ZXing, lokal) | Kein ML Kit; Paketstatus vor Einsatz prüfen |
| Lebensmitteldaten | Open Food Facts | Kostenlos, Barcode-Abfrage, ODbL (Quelle nennen) |
| Backend | FastAPI (Python) | OpenAPI-Doku automatisch |
| Datenbank | PostgreSQL (Dev und Tests: SQLite) | Relational, Historie, Teilen |
| Dateispeicher | Lokales Dateisystem oder MinIO hinter Interface | Austauschbar; für den Start reicht Dateisystem |
| GPX | gpxpy plus eigener Leser für Sensor-Erweiterungen; FIT später | Garmin-Daten |
| Höhendaten | Open-Meteo Elevation API (nur wenn der Track keine Höhe hat) | Für manuell gezeichnete Tracks |
| Auth | E-Mail + Passwort (argon2), JWT als Access-Token, Refresh-Token in der Datenbank | Kein Drittanbieter |
| Wetter | Open-Meteo (Forecast + Archive) | Kostenlos, kein Key |
| Deployment | Docker Compose, Anbindung an vorhandenen Reverse Proxy | Siehe Abschnitt 11 |

## 4. Gesamtarchitektur

```
┌────────────────────────────┐        ┌───────────────────────────────┐
│ Flutter Client (App / Web) │  HTTPS │ FastAPI Backend               │
│  core/  features/*         │◄──────►│  core/  modules/*             │
│  Drift (lokal, offline)    │  JSON  │  PostgreSQL + Dateispeicher   │
└────────────────────────────┘        └───────────────────────────────┘
                                              │
                          Open-Meteo, Open Food Facts, (später hikr.org)
```

Prinzipien:
1. **API-first**: Die App spricht nur mit der REST-API. Web = gleicher Client.
2. **Local-first**: Änderungen landen zuerst in Drift, ein Sync-Dienst schickt sie an den Server.
3. **Module sind Pakete**: eigene Ordner, Routen, Tabellen, Tests.
4. **Abhängigkeiten explizit**: Core kennt keine Module. Ein Modul nutzt ein anderes nur über `MODULE_INFO.depends_on` und dessen öffentliche Service-Schnittstelle oder IDs. Keine Zyklen. `protocols` hängt von `gear` und `nutrition` ab, nie umgekehrt.
5. **Externe Dienste hinter Adaptern** (Wetter, Höhe, Open Food Facts, Dateispeicher, später hikr.org).

## 5. Ordnerstruktur

### Repository
```
hiker/
├── DESIGN.md
├── CLAUDE.md
├── docker-compose.yml
├── deploy/                   # Proxy-Beispiele, Backup-Skript, systemd-Timer
├── backend/
└── app/                      # Flutter
```

### Backend
```
backend/app/
├── main.py                   # lädt Module über Registry
├── core/                     # config, db, security, registry, storage, deps, errors, geo, history
│   └── storage/              # Interface + local_fs.py + s3.py
├── modules/
│   ├── auth/                 # Nutzer, Profil, Login, Tokens (+ migrations/ je Modul)
│   ├── gear/                 # Ausrüstung + Katalog
│   ├── nutrition/            # Lebensmittel + Katalog + Barcode (Open Food Facts)
│   ├── protocols/
│   │   ├── models.py  schemas.py  router.py  service.py  export.py
│   │   ├── history.py        # Revisionen
│   │   ├── sharing.py        # Nutzer-Freigaben, Public Links, Rechteprüfung
│   │   ├── track.py          # GPX-Auswertung (Garmin-Erweiterungen, tolerant)
│   │   ├── photos.py         # EXIF lesen, Fotos dem Track zuordnen
│   │   ├── calories.py       # Verbrauchsschätzung
│   │   └── weather.py        # Wetter-Adapter
│   ├── planning/             # Phase 2
│   └── reports/              # Phase 3
└── tests/
```
Jedes Modul exportiert `register(app)` und `MODULE_INFO` (Name, Version, `depends_on`). Aktivierung über `ENABLED_MODULES=auth,gear,nutrition,protocols`. Die Registry bricht den Start ab, wenn eine Abhängigkeit nicht aktiv ist oder ein Zyklus besteht. Alembic-Umgebung (`migrations/`) und `alembic.ini` liegen in `backend/`.

### Flutter
```
app/lib/
├── main.dart
├── core/                     # theme, router, network, db, sync, i18n, map, widgets
├── shared/                   # gemeinsame Modelle (User, GeoPoint)
└── features/
    ├── auth/
    ├── gear/
    ├── nutrition/            # inkl. Scanner
    ├── protocols/
    │   ├── data/  domain/  presentation/
    ├── planning/             # Phase 2
    └── reports/              # Phase 3
```
Jedes Feature registriert sich über ein `FeatureModule` (Routen, Navigationseintrag, Provider). In `core/map` liegen die wiederverwendbaren Bausteine: Karte, Track zeichnen, Punkt setzen, Foto-Marker, Höhenprofil.

## 6. Datenmodell

Alle IDs sind UUIDs und clientseitig erzeugbar. Hauptdaten haben `created_at`, `updated_at`, `deleted_at` (Soft Delete für Sync).

### 6.1 Nutzer (Modul auth)
**user** (Tabelle `user_account`, da `user` in PostgreSQL reserviert ist): id, email (kleingeschrieben, eindeutig), display_name, password_hash, role (`user` | `admin`), created_at
**user_profile** (optional, für Kalorienschätzung): weight_kg, birth_year, sex (`female` | `male` | `trans` | `undisclosed` = keine Angabe, optional), max_heart_rate (optional), resting_heart_rate (optional)
**refresh_token**: id, user_id, token_hash (SHA-256), created_at, expires_at, revoked_at

### 6.2 Ausrüstung (Modul gear)
**gear_item** (persönliche Gegenstände)
- id, owner_id, catalog_id (optional, Verweis auf Katalog)
- name, brand, type, weight_g
- purchase_date, purchase_price, currency
- description, notes, website_url, image_file_id
- status (`active` | `retired`)
- optional: serial_number, size, color

**gear_catalog_item** (gemeinsamer Katalog, nutzerübergreifend)
- id, created_by, name, brand, type, nominal_weight_g, website_url, image_file_id
- status (`pending` | `approved` | `rejected`), Moderation durch `admin`

Ablauf: Nutzer legt Gegenstand an → kann Katalogeintrag vorschlagen („Teilen im Katalog“, nur Produktdaten, keine persönlichen Felder wie Kaufpreis/-datum) → Admin gibt frei. Beim Anlegen eines eigenen Gegenstands lässt sich ein Katalogeintrag als Vorlage übernehmen (Kopie, spätere Katalogänderungen verändern persönliche Gegenstände nicht).

**gear_type**: id, name, sort_order (Standardliste, erweiterbar)
**gear_list** (Packlisten-Vorlage) + **gear_list_item**: gear_item_id, quantity

Auswertungen (abgeleitet): Touren und Gesamtstrecke je Gegenstand, Gewicht je Kategorie.

### 6.3 Ernährung (Modul nutrition)
**food_item**
- id, owner_id (leer = gemeinsamer Katalog), barcode (EAN/UPC, indexiert), name, brand
- kcal_per_100g, protein_g, carbs_g, fat_g, sugar_g, salt_g (je 100 g)
- serving_size_g, image_url oder image_file_id
- source (`openfoodfacts` | `custom`), source_synced_at
- visibility (`private` | `catalog_pending` | `catalog`)

Gemeinsamer Katalog = Open-Food-Facts-Cache plus von Nutzern vorgeschlagene eigene Produkte (nach Freigabe durch `admin`). Eigene Korrekturen an einem Katalogprodukt werden als private Kopie des Nutzers gespeichert.

### 6.4 Protokolle (Modul protocols)
**tour**
- id, owner_id, title, summary (Fazit)
- start_time, end_time, duration_minutes (berechnet, überschreibbar)
- start_point, end_point (lat, lon, optional Name), `points_source` (`gpx` | `manual`)
- pack_weight_start_g (aus Ausrüstung berechnet, überschreibbar)
- calories_burned, `calories_burned_source` (`manual` | `estimated`), calories_eaten (aus Einträgen)
- gpx_file_id, `track_source` (`device` | `drawn` | `none`), track_stats (JSON)
- cover_photo_id
- version (Revisionszähler, Konflikterkennung)

**tour_gear**: tour_id, gear_item_id, quantity, weight_g_snapshot, carried
**tour_food_entry**: tour_id, food_item_id, amount_g, kcal_snapshot, eaten_at (optional), planned
**contact**: id, owner_id, display_name, linked_user_id (leer = Platzhalter)
**tour_partner**: tour_id, contact_id

Platzhalter → echter User: `contact.linked_user_id` setzen; gilt sofort in allen Touren des Owners.

**tour_peak**: tour_id, name, elevation_m, lat, lon, reached_at

**tour_waypoint** (wie bei wanderer): id, tour_id, name, description, icon, lat, lon, track_distance_m, elevation_m
**tour_photo**: id, tour_id, file_id, caption, taken_at, lat, lon, `position_source` (`exif_gps` | `exif_time` | `manual` | `none`), track_distance_m (Position entlang des Tracks), elevation_m, waypoint_id (optional), sort_order

**tour_weather**: tour_id, sample_point (`start` | `summit` | `end` | `manual`), lat, lon, elevation_m, time, Werte (Temperatur, gefühlt, Wind, Böen, Niederschlag, Bewölkung, Nullgradgrenze), source, fetched_at

**track_series**: tour_id, abgetastete Zeitreihe (Zeit, Distanz, Höhe, Herzfrequenz, Kadenz, Temperatur); Original-GPX bleibt unverändert im Dateispeicher.

### 6.5 Teilen und Historie
**tour_share**: tour_id, user_id, permission (`read` | `edit`)
**tour_public_link**: id, tour_id, token (zufälliges UUIDv4), created_by, created_at, expires_at, revoked_at, Optionen (`hide_exact_start`, `strip_photo_gps`)
**tour_revision**: id, tour_id, version, author_user_id, created_at, change_summary, snapshot (JSON), diff (JSON)

### 6.6 Dateien (core)
**file_object**: id, owner_id, storage_key, mime, size, sha256

## 7. Wichtige Abläufe

**GPX von Garmin und anderen Quellen**
Upload → serverseitig parsen. Neben Position, Höhe und Zeit werden Sensor-Erweiterungen gelesen (Garmin TrackPointExtension: Herzfrequenz, Kadenz, Temperatur). Daraus entstehen `track_stats`: Distanz, Höhenmeter hoch/runter, tiefster/höchster Punkt, Gesamt- und Bewegungszeit, Herzfrequenz (Durchschnitt, Maximum, Zeit je Zone), Kadenz, Temperatur. Der Parser ist tolerant: Fehlende Felder (z. B. keine Zeitstempel, keine Höhe, kein Puls) führen nie zu einem Fehler, die jeweilige Auswertung bleibt leer. Spätere Erweiterung: FIT-Dateien direkt importieren.

**Einfache, manuell erstellte Tracks**
Wer kein Gerät dabei hatte, zeichnet den Track in der App auf der Karte (Punkte setzen, verschieben, löschen). Daraus erzeugt die App ein GPX (`track_source = drawn`). Fehlen Höhen, werden sie über die Open-Meteo-Elevation-API ergänzt. Zeiten gibt der Nutzer manuell an; Dauer und Tempo sind dann Schätzwerte oder manuell. Auch ein einfaches, extern erstelltes GPX ohne Zeit und Puls lässt sich hochladen.

**Start-/Endpunkt und Wetter**
1. Track vorhanden → Start und Ende daraus (`points_source = gpx`), Zeitfenster aus den Zeitstempeln (sonst manuelle Zeiten).
2. Kein Track → Nutzer setzt Start und Ende auf der Karte, dazu Datum und Uhrzeit (`manual`).
3. Wetter wird nach dem Speichern automatisch abgerufen: Open-Meteo (Archive für Vergangenheit, Forecast für Zukunft) für Start, Gipfel (höchster Punkt) und Ende, jeweils für die passende Stunde und die Höhe der Position.
4. Ergebnis wird gespeichert (`tour_weather`). Neuabruf manuell; ändern sich Punkte oder Zeiten, wird er angeboten.

**Kalorienverbrauch**
Manuell eingegebene Werte haben immer Vorrang (`manual`). Fehlt ein Wert, schätzt der Server (`estimated`, in der UI klar als Schätzung markiert):
- Mit Herzfrequenzdaten und Nutzerprofil (Gewicht, Alter, Geschlecht): pulsbasierte Formel. Bei `trans`, `undisclosed` oder fehlender Angabe wird der Mittelwert der Formeln für `female` und `male` verwendet.
- Ohne Puls: Berechnung aus Körper- plus Rucksackgewicht, Distanz, Höhenmetern und Dauer mit einer anerkannten Geh-/Wanderformel.
- Ohne Profil oder Track: keine Schätzung, Hinweis zur Eingabe.
Die verwendete Formel und Parameter werden im Code dokumentiert und als Tooltip erklärt. Änderungen an Track, Gewicht oder Profil lösen eine Neuberechnung aus, solange der Wert nicht manuell ist.

**Fotos und Track**
1. Upload der Fotos (mehrere gleichzeitig). EXIF wird gelesen: Aufnahmezeit und, falls vorhanden, GPS.
2. Zuordnung zum Track: mit EXIF-GPS → nächster Punkt des Tracks; ohne GPS → über die Aufnahmezeit zum Zeitstempel im Track (mit einstellbarem Zeitversatz, z. B. wegen Kamera-/Uhrzeit-Abweichung); sonst bleibt das Foto ohne Position und kann per Hand auf der Karte oder im Höhenprofil gesetzt werden.
3. Ergebnis: `track_distance_m`, Koordinate und Höhe pro Foto.
4. Funktion „Aus Fotos“: Aus Fotos mit GPS lassen sich Wegpunkte automatisch anlegen.
5. Ein Foto lässt sich als Titelbild (`cover_photo_id`) festlegen.

**Ausrüstung in Touren**
Auswahl aus der Datenbank oder per Packlisten-Vorlage. Startgewicht = Summe der mitgeführten Gegenstände (plus geplantes Essen), überschreibbar.

**Barcode-Scan und Essen**
Scanner liest EAN lokal → lokale Datenbank → Backend `GET /nutrition/barcode/{ean}` (eigener Katalog, dann Open Food Facts, mit Cache) → sonst Formular für ein eigenes Produkt (Barcode wird mitgespeichert) → Menge eingeben → Kalorien als Momentaufnahme in der Tour.

**Änderungshistorie**
Jede Änderung erzeugt eine `tour_revision` (Autor, Zeit, Diff, Snapshot). Zeitleiste, Vergleich zweier Stände, Wiederherstellen (erzeugt neue Revision). Konfliktschutz über `version`: veralteter Stand → 409 mit aktuellem Stand; Client führt feldweise zusammen und fragt bei Überschneidung.

**Offline-Sync**
Lokale Änderungen mit `updated_at`/`deleted_at` und Basis-`version`; Konfliktregel wie bei der Historie. Fotos und GPX laufen über eine getrennte Upload-Warteschlange.

**Teilen mit Usern**
- Owner: alles.
- `edit`: Textfelder (Titel, Fazit, Beschreibungen), Listen (Ausrüstung, Essen, Partner, Gipfel, Wegpunkte) und **Fotos** (hinzufügen, entfernen, Beschriftung, Titelbild, Position).
- `edit` darf **nicht**: GPX/Track und Start-/Endpunkte ändern, Freigaben und Links verwalten, Tour löschen.
- `read`: nur lesen.
Empfänger sehen die Tour im Tab „Mit mir geteilt“. Entfernen des Teilens wirkt sofort serverseitig; die lokale Kopie wird beim nächsten Sync gelöscht.

**Teilen per Link**
`https://hiker.lacasa.internal/p/<token>`, Token = zufälliges UUIDv4. Nur lesend, widerrufbar, optional befristet, ohne Login, `noindex`, Rate-Limit, ohne E-Mail-Adressen oder interne IDs. Optional: genauen Start verbergen, Foto-GPS entfernen. Die Basis-URL kommt aus der Konfiguration (`PUBLIC_BASE_URL`).

**Export JSON**
Versioniertes Schema (`schema_version`): Tour, Ausrüstung (Snapshots), Essen, Partner (Anzeigenamen), Wetter, Track-Statistik, Wegpunkte, Foto-Metadaten (inkl. Position) und Verweise auf Dateien oder ZIP mit den Dateien.

## 8. API (Version `/api/v1`)

### Auth und Profil
| Methode | Pfad | Zweck |
|---|---|---|
| POST | /auth/register, /auth/login, /auth/refresh | Konto/Tokens (Refresh rotiert das Token) |
| POST | /auth/logout | Refresh-Token widerrufen |
| GET | /users/lookup?email= | Nutzer für Freigabe/Partner finden (exakte Adresse; liefert nur ID und Anzeigename) |
| GET | /me | Eigenes Konto |
| GET/PUT | /me/profile | Profil für Kalorienschätzung |
| GET | /modules | Aktive Module (ohne Login), damit der Client nur vorhandene Funktionen zeigt |

### Protokolle
| Methode | Pfad | Zweck |
|---|---|---|
| GET, POST | /tours | Eigene + geteilte listen (Filter, Suche, Paging) / erstellen |
| GET, PUT, DELETE | /tours/{id} | Lesen, Editieren, Löschen (nur Owner) |
| GET | /tours/{id}/revisions, /revisions/{rev} | Historie |
| POST | /tours/{id}/revisions/{rev}/restore | Wiederherstellen |
| POST | /tours/{id}/shares | Teilen (`read`/`edit`) |
| PATCH, DELETE | /tours/{id}/shares/{user_id} | Recht ändern / entfernen |
| POST, DELETE | /tours/{id}/public-link, …/{link_id} | Link erzeugen / widerrufen |
| GET | /public/tours/{token} | Öffentliche Ansicht |
| PUT | /tours/{id}/gpx | GPX hochladen, auswerten (nur Owner) |
| POST | /tours/{id}/track/drawn | Gezeichneten Track speichern, GPX erzeugen (nur Owner) |
| GET | /tours/{id}/track | Zeitreihen für Diagramme |
| PUT | /tours/{id}/points | Start/Ende manuell setzen (nur Owner) |
| POST | /tours/{id}/photos | Fotos hochladen (EXIF-Auswertung, Track-Zuordnung) |
| PATCH, DELETE | /tours/{id}/photos/{photo_id} | Beschriftung, Position, Titelbild / löschen |
| POST | /tours/{id}/waypoints/from-photos | Wegpunkte aus Foto-GPS erzeugen |
| GET, POST, PATCH, DELETE | /tours/{id}/waypoints | Wegpunkte |
| POST | /tours/{id}/weather/fetch | Wetter abrufen |
| POST | /tours/{id}/calories/estimate | Verbrauch schätzen |
| GET | /tours/{id}/export | JSON-Export |
| GET, POST, PATCH, DELETE | /contacts | Partner-Kontakte, Verknüpfung setzen |
| GET | /sync/changes?since=, POST /sync/push | Offline-Sync |

### Ausrüstung
| Methode | Pfad | Zweck |
|---|---|---|
| GET, POST | /gear/items | Liste (Filter) / Anlegen |
| GET, PUT, DELETE | /gear/items/{id} | CRUD |
| POST | /gear/items/{id}/image | Bild |
| GET | /gear/catalog?q= | Katalog durchsuchen |
| POST | /gear/items/{id}/propose-to-catalog | Katalogvorschlag |
| GET, PATCH | /gear/catalog/pending, …/{id} | Moderation (admin) |
| GET, POST, PUT, DELETE | /gear/types, /gear/lists | Kategorien, Packlisten |

### Ernährung
| Methode | Pfad | Zweck |
|---|---|---|
| GET | /nutrition/barcode/{ean} | Produkt per Barcode |
| GET | /nutrition/search?q= | Produktsuche (privat + Katalog) |
| GET, POST, PUT, DELETE | /nutrition/foods | Eigene Lebensmittel |
| POST | /nutrition/foods/{id}/propose-to-catalog | Katalogvorschlag |
| GET, PATCH | /nutrition/catalog/pending, …/{id} | Moderation (admin) |

Berechtigungen werden zentral in einer Dependency geprüft, nicht in jedem Endpunkt.

## 9. UI-Grundlage

- Material 3, helles und dunkles Theme, Design-Tokens zentral in `core/theme`.
- Farbidee: Tannengrün, Fels-Grau, Schnee-Weiß, Akzent Orange.
- Navigation: untere Leiste mit aktiven Modulen (Touren | Ausrüstung | Essen | später Planung, Berichte); auf großen Bildschirmen Navigation Rail.
- Responsiv von Beginn an, Deutsch zuerst, Texte über ARB-Dateien.

### Tourdetail (orientiert an wanderer)
wanderer (open-wanderer/wanderer, AGPLv3) dient als **UX-Vorbild, nicht als Code- oder Asset-Quelle**. Aus der Dokumentation entnommen: Fotos hängen an der Tour und erscheinen in der Detailansicht, eines ist als Vorschaubild wählbar, Wegpunkte haben Name, Beschreibung, Icon und Fotos, und „Aus Fotos“ erzeugt Wegpunkte aus GPS-Daten der Bilder. Wie genau Karte und Höhenprofil die Fotos zeigen, steht dort nicht; das Verhalten bitte am Demo-System (demo.wanderer.to) ansehen und hier festhalten, bevor die Detailansicht gebaut wird.

Geplantes Verhalten (unsere Umsetzung):
- **Karte**: Track als Linie, Start-/Ende-/Gipfel-Marker, Foto-Marker als kleine runde Vorschaubilder an der Fotoposition, bei Zoom-Out zu Gruppen zusammengefasst; Wegpunkt-Marker mit Icon.
- **Höhenprofil** (mit optional Herzfrequenz-Kurve): Foto-Marker an der Stelle `track_distance_m`; Wischen/Hover über das Profil bewegt einen Punkt auf der Karte und umgekehrt.
- **Foto-Ansicht**: Tippen auf einen Marker öffnet eine Vollbild-Galerie (Wischen zwischen Fotos, Beschriftung, Aufnahmezeit, Höhe); Sprung zur Position auf Karte/Profil. Reihenfolge der Galerie = Verlauf entlang des Tracks.
- **Fotoleiste** unter der Karte (horizontal scrollbar); Titelbild wählbar, erscheint in der Liste.
- **Position korrigieren**: Foto auf Karte oder Profil verschieben; Zeitversatz für alle Fotos einer Tour einstellbar.
- Weitere Abschnitte: Eckdaten, Track-Statistik, Ausrüstung mit Gewichtssumme, Essen mit Kalorien (gegessen/verbraucht, „geschätzt“ markiert), Wetter (Start/Gipfel/Ende), Partner, Fazit, Historie, Teilen.

### Weitere Screens
- Liste: Karten mit Titel, Datum, Gipfel, Titelfoto; Tabs „Meine“ / „Mit mir geteilt“.
- Editor: Formular in Abschnitten, Speichern als Entwurf; Track-Zeichenmodus; Start/Ende per Tippen auf der Karte.
- Ausrüstung: Liste mit Bild, Filter und Suche, Katalogsuche beim Anlegen.
- Essen: Scan-Button öffnet Kamera; Trefferkarte mit Nährwerten und Mengeneingabe.

## 10. Sicherheit und Datenschutz

- Passwörter mit argon2 oder bcrypt, JWT kurzlebig + Refresh-Token.
- Rate-Limit auf Login, Public Links und Barcode-Lookup; HTTPS Pflicht.
- Public-Link-Tokens: kryptografisch zufällig, widerrufbar, optional befristet, nie in Logs.
- Fotos: EXIF-GPS bei öffentlichen Links optional entfernen; Uploads auf Typ und Größe prüfen, Bilder serverseitig neu kodieren.
- Dateizugriff nur mit Berechtigungsprüfung oder kurzlebigen signierten URLs.
- Gesundheitsdaten (Herzfrequenz, Profil) sind sensibel: nur für Owner sichtbar, in Freigaben und Public Links standardmäßig ausgeblendet bzw. abschaltbar.
- Admin-Rolle nur für Katalogmoderation.
- Historie enthält Autoren; beim Entfernen eines Users werden Autoren anonymisiert.
- Keine Tracker, keine Analytics von Drittanbietern.
- Löschen entfernt auch Dateien im Speicher.

## 11. Betrieb auf dem vorhandenen Server

Ziel: Ubuntu 26.04, Domain `hiker.lacasa.internal`, läuft auf dem bereits genutzten Server neben anderen Diensten.

- Docker über das offizielle Docker-Repository installieren; Stack per Docker Compose: `api`, `db` (PostgreSQL), optional `minio`.
- **Keine festen Ports 80/443 im Stack.** Die API lauscht nur auf `127.0.0.1:<Port>`. Der bereits vorhandene Webserver bzw. Reverse Proxy (nginx, Apache oder Caddy) leitet `hiker.lacasa.internal` dorthin; TLS über Let's Encrypt (certbot oder Caddy). Beispielkonfigurationen für nginx und Caddy liegen in `deploy/`. Läuft auf dem Server noch kein Proxy, wird einer ergänzt.
- DNS: A-/AAAA-Eintrag für `hiker.lacasa.internal` auf den Server.
- Konfiguration in `.env` (nicht im Repository, Vorlage `.env.example`): Datenbankpasswort, `SECRET_KEY`, `PUBLIC_BASE_URL=https://hiker.lacasa.internal`, Speicherpfad, `ENABLED_MODULES`, `REGISTRATION_MODE`.
- Upload-Größen im Proxy erhöhen (Fotos, GPX).
- Backups: Nächtlicher `pg_dump` plus Sicherung des Foto-/GPX-Verzeichnisses nach `/var/backups/hiker`, 14 Tage Rotation, per systemd-Timer. Eine Kopie außerhalb des Servers ist empfohlen (Ziel noch offen). Wiederherstellung einmal testen.
- Datenbankmigrationen mit Alembic, Updates über neue Images.
- Health-Endpunkt `/healthz`; Logs über Docker/journald; Firewall (ufw) nur 22/80/443.
- Ressourcen schonen, da der Server geteilt ist: Container-Limits setzen, Bildverarbeitung in der Größe begrenzen.

## 12. Phasenplan

**Phase 1 – Protokolle, Ausrüstung, Essen (aktuell)**
1. Backend-Grundgerüst, Auth, Profil, Modulregistry, Alembic
2. Modul `gear`: Datenbank, CRUD, Bild-Upload, Katalog + Moderation
3. Modul `nutrition`: Lebensmittel-DB, Open-Food-Facts-Adapter, Barcode-Endpunkt, Katalog + Moderation
4. Modul `protocols`: Tour-CRUD, Untertabellen, Berechtigungen (`read`/`edit`-Grenzen)
5. Änderungshistorie und Konfliktschutz
6. Teilen, Public Links, Partner-Kontakte, JSON-Export
7. GPX-Auswertung (Garmin-Erweiterungen, tolerant), gezeichneter Track, Höhenergänzung
8. Fotos: Upload, EXIF, Zuordnung zum Track, Wegpunkte aus Fotos, Titelbild
9. Start-/Endpunkt und automatischer Wetterabruf
10. Kalorienschätzung
11. Flutter: Core inkl. `core/map` (Karte, Foto-Marker, Höhenprofil, Zeichnen), Auth, Ausrüstung, Essen mit Scanner, Protokolle (Liste, Detail, Editor, Historie, Teilen)
12. Offline-Sync
13. Tests, Docker Compose, Proxy-Beispiele, Backup-Skript, README

**Phase 2 – Planung**: Layer-Provider-Schnittstelle, Stile (Sommer/Winter/Satellit), Ebenen (Hangneigung, Wetter, Schnee, Lawinenlage), Routen planen und als GPX speichern, Verknüpfung zu Protokollen; vorher Lizenzen der Kartenquellen klären. Optional FIT-Import.

**Phase 3 – Berichte**: Backend-Dienst, der hikr.org-Berichte für Gipfel im Umkreis findet (Nutzungsbedingungen und robots.txt prüfen, Zwischenspeicherung, nur Verweise + kurze Auszüge, Quelle klar angeben).

## 13. Regeln für Claude Code

Stehen in der separaten Datei `CLAUDE.md` im Repository-Hauptverzeichnis.

## 14. Noch offen

1. Backup-Ziel außerhalb des Servers (z. B. zweiter Server, externer Speicher).
2. Welcher Webserver bzw. Reverse Proxy läuft auf dem Server bereits (nginx, Apache, Caddy)? Davon hängt die Beispielkonfiguration in `deploy/` ab.
3. Kartenquellen und Lizenzen (bis Phase 2).
4. Rate-Limit für Login (Abschnitt 10) ist noch nicht umgesetzt; im Proxy oder in der API, spätestens mit Schritt 13.
5. Genauer Wunsch zur Foto-Darstellung nach Sichtung der wanderer-Demo (Abschnitt 9), falls etwas anders sein soll.