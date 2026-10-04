# hiker – Designgrundlage

Stand: 03.10.2026 (v4) · Zweck: Grundlage zur Umsetzung mit Claude Code
Regeln für Claude Code stehen in der separaten Datei `CLAUDE.md`.

## 1. Ziele und Leitplanken

- Android-App (Flutter) und ein Web-Frontend im Browser (Python Flask, auf dem eigenen Server gehostet). Beide sind eigenständige Clients derselben REST-API; Flutter wird nur für Android gebaut.
- Module: **Protokolle**, **Ausrüstung** und **Ernährung** (jetzt), **Planung** und **Berichte** (später).
- **Strikt modular**: Jedes Modul ist in sich abgeschlossen und kann hinzugefügt/entfernt werden, ohne andere Module anzufassen.
- **Keine Google-Dienste**: kein Firebase, kein Google Maps, kein FCM, kein Google Sign-In, kein Google ML Kit.
- **Eigener Server** (Self-Hosting) als Zielplattform.
- Offline-fähig (in den Bergen oft kein Netz): lokal speichern, später synchronisieren.
- Datenhoheit beim Nutzer: Export als JSON, alles selbst hostbar.

Hinweis: Flutter/Dart stammen von Google, sind aber Open Source und benötigen keine Google-Dienste. Falls das später stört, ist die Alternative Kotlin Multiplatform; die Architektur (API-first) bleibt gleich.

## 2. Getroffene Entscheidungen

| Thema | Entscheidung | Auswirkung |
|---|---|---|
| Hosting | Eigener, bereits vorhandener Server, Ubuntu 26.04, Domain vorläufig `hiker.lacasa.internal` (endgültige Domain später, nur über `PUBLIC_BASE_URL`) | Läuft neben anderen Diensten, Reverse-Proxy-Konzept in Abschnitt 11 |
| Teilen mit Usern | `read` und `edit` | Edit = Textfelder, Listen und Fotos, **nicht** GPX/Punkte/Freigaben/Löschen |
| Historie | Jede Änderung wird als Revision gespeichert | Abschnitt 6.5 |
| Partner | Per Nutzerkonto verknüpfbar, sonst Platzhalter, später austauschbar | Kontakte (6.4) |
| Teilen per Link | Zufälliges UUID-Token, nur lesend, widerrufbar | Abschnitt 7 |
| Kartenlayer-Lizenzen | Werden in Phase 2, Schritt 6 je Quelle geklärt und dokumentiert | Tile-URL konfigurierbar |
| Wegführung beim Planen | BRouter, selbst gehostet; Luftlinie als Rückfall (entschieden am 04.10.2026) | Abschnitt 9b |
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
| Ausrüstungskategorien | Standardliste für alle (nur `admin` ändert sie) plus eigene Kategorien je Nutzer | Katalogeinträge verwenden nur Standardkategorien |
| Bilder | Upload JPEG/PNG/WebP, serverseitig als JPEG ohne Metadaten neu kodiert, längste Kante begrenzt | Abhängigkeit Pillow; Auslieferung nur über Endpunkte mit Rechteprüfung |
| `edit`-Grenze in Touren | `edit` ändert Titel, Fazit, Listen, Wegpunkte (und Fotos); Zeiten, Dauer, Startgewicht und Kalorienverbrauch ändert nur der Owner | Geänderte Owner-Felder von `edit` → 403 `owner_only_field` |
| Einträge in geteilten Touren | Jeder trägt Ausrüstung aus der eigenen Datenbank ein (Essen: eigenes oder Katalog); die Tour speichert Name, Gewicht und Kalorien als Momentaufnahme | Alle mit Zugriff lesen die Einträge, ohne die Datenbank der anderen zu sehen |
| Essen in Touren | `carried` (zählt ins Startgewicht) und `eaten` (zählt in die Kalorien) statt eines Felds `planned` | Auch Heimgetragenes und unterwegs Gekauftes erfassbar |
| App: Server-Adresse | Wird beim Anmelden eingegeben und auf dem Gerät gespeichert | Keine feste Domain in der App; optionaler Vorgabewert per `--dart-define=API_BASE_URL` |
| App: Tokens | Im Plattform-Keystore (`flutter_secure_storage`) | Abgelaufene Access-Tokens werden einmal automatisch erneuert; ein abgelehntes Refresh-Token meldet ab, fehlendes Netz nicht |
| App: lokale Daten | Drift speichert die gesehenen Datensätze als JSON-Dokumente je Sammlung (`cached_documents`), nicht als Abbild aller Server-Tabellen | Weniger doppelte Schemapflege; die Typisierung liegt in den Dart-Modellen. Beim Abmelden wird die lokale Kopie gelöscht |
| App: Lesen ohne Netz | Listen werden beim Laden lokal gespeichert; ist der Server nicht erreichbar, zeigt die App den gespeicherten Stand mit einem Hinweis und wendet Filter lokal an | Änderungen an Ausrüstung, Lebensmitteln und Touren sowie Datei-Uploads warten ohne Netz in einer Warteschlange (Offline-Sync) |
| App: Dateiauswahl | `file_picker` (MIT) für Bilder und GPX | Nutzt die Dateiauswahl des Systems, keine Google-Dienste |
| App: Barcode-Ablauf | Scan oder Eingabe → Server (eigene Produkte, Katalog, Open Food Facts); ohne Netz wird in den schon gesehenen Produkten auf dem Gerät gesucht. Unbekannt oder nicht erreichbar → Formular mit vorbelegtem Barcode | Alles, was die App gesehen hat (Suche, Scans), bleibt lokal gespeichert |
| App: Kennung | Android-Paketname `internal.lacasa.hiker` (vorläufig) | Vor einer Veröffentlichung auf die endgültige Domain umstellen |
| Clients | Flutter nur für Android; das Web-Frontend ist ein eigenes Projekt mit Python Flask (`web/`), entschieden am 03.10.2026 | Keine Web-Plattform im Flutter-Projekt; zwei Oberflächen, die getrennt gepflegt werden |
| Web-Frontend | Flask rendert die Seiten auf dem Server (Jinja2) und spricht ausschließlich mit der REST-API, nie direkt mit der Datenbank | API-first bleibt erhalten; Rechte, Historie und Konfliktschutz gelten wie in der App. Einzelheiten in Abschnitt 9a |
| Gipfel und Pässe am Track | Werden nach jedem Track-Upload automatisch gefunden: benannte Gipfel, Sättel und Pässe aus OpenStreetMap (Overpass-API), die höchstens 10 m neben der Tracklinie liegen, dazu die Wegpunkte aus der GPX-Datei und der höchste Punkt | Einträge sind änderbar und löschbar; Gipfel landen zusätzlich in der Gipfelliste. Toleranz über `PLACE_MAX_DISTANCE_M` einstellbar |
| Fehlerformat | `{"error": {"code", "message"}}` für fachliche Fehler | Client übersetzt anhand von `code` |

## 3. Technologie-Stack

| Bereich | Wahl | Begründung |
|---|---|---|
| Android-App | Flutter (nur Android) | Offline-fähig, Kamera-Scanner |
| Web-Frontend | Python Flask mit Jinja2-Vorlagen, HTTP-Client `httpx2` | Gleiche Sprache und Werkzeuge wie das Backend; läuft als eigener Dienst neben der API |
| State/DI | Riverpod | Testbar, modular |
| Routing (App) | go_router | Deep Links |
| Lokale DB (App) | Drift (SQLite) | Offline |
| HTTP | dio | Interceptors (Auth, Retry) |
| Karten | MapLibre (`maplibre_gl`) | Open Source; ab Phase 1 für Track, Fotos, Punktauswahl |
| Kartenkacheln | Modul `maps`: der eigene Server holt jede Kachel beim ersten Ansehen von OpenStreetMap, speichert sie als Datei und fragt erst nach `TILE_CACHE_DAYS` (Standard 14) mit dem ETag nach, ob sie sich geändert hat; entschieden am 04.10.2026 | Entlastet die OSM-Server und hält sich an deren Nutzungsbedingungen (Zwischenspeichern ja, Vorab-Download nein). Bekannte Gebiete funktionieren auch, wenn OSM nicht erreichbar ist. Für Phase 2 ist eine eigene Karte aus OSM-Rohdaten (Regionsauszug, alle x Tage neu gebaut) vorgesehen |
| Datenablage im Betrieb | Normale Ordner unter `DATA_DIR` (Bind-Mounts) statt Docker-Volumes, entschieden am 04.10.2026 | Daten sind direkt sichtbar und mit üblichen Werkzeugen zu sichern; alles gehört dem Benutzer `HIKER_UID` |
| Ausrüstung: Favoriten | Jeder Nutzer hat einen festen, nicht löschbaren Tag „Favorit“ (`system = favorite`); der Stern am Gegenstand setzt ihn. Entschieden am 04.10.2026 | Kein eigenes Feld: Filtern, Gruppieren und Offline-Sync laufen wie bei jedem anderen Tag |
| Ausrüstung: Währung | Kaufpreise immer in EUR; das Währungsfeld entfällt, entschieden am 04.10.2026 | Eine Summe statt je Währung getrennter Summen |
| Ausrüstung: Zusatzfelder | Eine Kategorie kann eine Art (`kind`) haben, die ihren Gegenständen Zusatzfelder gibt: `backpack` → Volumen in Litern, `shoes` → Schuhkategorie A, B, B/C, C, D. Werte liegen als JSON in `gear_item.attributes`; `GET /gear/meta` beschreibt die Felder. Entschieden am 04.10.2026 | Neue Arten und Felder kommen in `gear/attributes.py` (Server) und `gearKinds` (App) dazu, ohne Migration |
| Passwörter | Regeln nach den Empfehlungen des BSI: mindestens 20 Zeichen mit zwei Zeichenarten, oder mindestens 8 Zeichen mit allen vier Arten; solange der zweite Faktor Pflicht ist, genügen bei 8 Zeichen drei Arten. Nicht erlaubt: Name oder E-Mail im Passwort, sehr verbreitete Passwörter. Bei der Registrierung wird das Passwort zweimal eingegeben. Entschieden am 04.10.2026 | Geprüft wird auf dem Server (`auth/passwords.py`); die Clients prüfen vorab dasselbe |
| Zweiter Faktor | TOTP (RFC 6238) ist für die Anmeldung mit Passwort Pflicht (`MFA_REQUIRED=true`). Nach dem ersten Login erlaubt die Sitzung nur das Einrichten; danach braucht jede Anmeldung den Code. Zehn Wiederherstellungscodes, je einmal gültig. Entschieden am 04.10.2026 | Ohne zusätzliche Bibliothek umgesetzt; der QR-Code im Web kommt von `segno`. Das TOTP-Geheimnis liegt unverschlüsselt in der Datenbank (wie die Passwort-Hashes zu schützen) |
| SSO | Optional über OpenID Connect (Authorization-Code-Flow mit PKCE), zunächst nur im Web-Frontend. Ein Konto mit derselben vom Anbieter bestätigten E-Mail wird verknüpft, sonst angelegt – unabhängig von `REGISTRATION_MODE`. Bei SSO ist der Anbieter für den zweiten Faktor zuständig. Entschieden am 04.10.2026 | Die App meldet sich weiter mit Passwort und TOTP an; SSO in der App ist ein späterer Schritt |
| Nutzerverwaltung | Administratoren sehen alle Nutzer, können sie entfernen, Passwörter zurücksetzen (vorläufiges Passwort, einmal angezeigt, muss beim nächsten Login ersetzt werden) und den zweiten Faktor zurücksetzen. Entschieden am 04.10.2026 | Beim Entfernen gehen Touren, Ausrüstung, Lebensmittel und Dateien des Nutzers mit; freigegebene Katalogeinträge bleiben, Autoren in fremder Historie werden anonym |
| Selbst signierte Zertifikate (App) | Die App zeigt den SHA-256-Fingerabdruck eines unbekannten Zertifikats und akzeptiert nach Bestätigung genau dieses Zertifikat für diesen Server. Zusätzlich vertraut sie Zertifizierungsstellen, die der Nutzer in Android installiert hat. Entschieden am 04.10.2026 | Die Karte (native Bibliothek) kennt die Bestätigung in der App nicht: zeigt der Server später ein anderes Zertifikat, bietet die App es beim nächsten Start zur Bestätigung an, und im Profil lässt sich das Vertrauen entziehen. Für einen von Hand bestätigten Server holt die App die Kacheln selbst und reicht sie der Karte über einen kleinen Server auf `127.0.0.1` weiter (`TileProxy`); nur dorthin ist unverschlüsseltes HTTP erlaubt |
| Abgleich nach Funkloch | Die App versucht wartende Änderungen jede Minute erneut zu senden, solange sie im Vordergrund läuft (zusätzlich zu Start, Rückkehr in die App und dem Knopf im Profil). Entschieden am 04.10.2026 | Ohne zusätzliche Abhängigkeit für den Verbindungsstatus; liegt nichts an, wird der Server nicht gefragt |
| Hintergrund | Hinter allen Seiten und Screens steht dezent ein graues Gebirge im Stil des Matterhorns, flächig gezeichnet (eigene Zeichnung: `background.svg` im Web, `MountainBackground` in der App). Entschieden am 04.10.2026 | Schwarz/Weiß mit geringer Deckkraft, funktioniert hell und dunkel |
| App: Release und Berechtigungen | Release-APKs werden mit einem eigenen Schlüssel signiert, der außerhalb des Repositorys liegt (`android/key.properties`, nicht eingecheckt). Die App verlangt Internet, Kamera und Lesezugriff auf Dateien; Standort und Mikrofon, die Karten- und Kamera-Bibliothek mitbringen, werden im Manifest entfernt. Entschieden am 04.10.2026 | Updates lassen sich nur mit demselben Schlüssel installieren, er muss also gesichert werden. Die Karte zeigt deshalb keinen eigenen Standort; wird das später gewünscht, kommt die Berechtigung zurück |
| Reverse Proxy im Stack | Caddy als optionaler Dienst (Compose-Profil `proxy`), der sich das Zertifikat mit einer eigenen CA selbst ausstellt; Port über `HTTPS_PORT` einstellbar. Entschieden am 04.10.2026 | Ohne das Profil belegt der Stack weiterhin keine Ports nach außen (Server mit eigenem Proxy). Die CA liegt unter `DATA_DIR/caddy`; Zertifikate gelten ein Jahr, damit die App den bestätigten Fingerabdruck nicht ständig neu abfragen muss. Caddy braucht als einzige Capability `NET_BIND_SERVICE`, weil sein Programm dafür markiert ist |
| Anmeldung in zwei Schritten | Erst E-Mail und Passwort, dann – nur bei Konten mit zweitem Faktor – auf einer eigenen Seite der Code. Die API antwortet auf ein richtiges Passwort mit `mfa_required` und einem fünf Minuten gültigen `mfa_token`; `/auth/login/mfa` schließt ab. Nach fünf falschen Codes muss das Konto zehn Minuten warten. Entschieden am 04.10.2026 | Das Passwort wird zwischen den Schritten nirgends aufbewahrt. Der Zähler für Fehlversuche liegt wie das Rate-Limit im Arbeitsspeicher eines API-Prozesses |
| Container-Rechte | Kein Container läuft als root: alle Dienste (auch PostgreSQL) laufen als `HIKER_UID:HIKER_GID`, mit `cap_drop: ALL`, `no-new-privileges` und schreibgeschütztem Dateisystem; entschieden am 04.10.2026 | Ein Ausbruch aus einem Dienst hat auf dem geteilten Server nur die Rechte eines normalen Benutzers |
| Kartenquellen | Konfigurierbare Tile-URL (Standard: OpenStreetMap) | Lizenzfragen später |
| Diagramme | Eigenes Höhenprofil-Widget (Höhe, Herzfrequenz, Foto-Marker) | Foto-Marker und Kartenverknüpfung nötig |
| Barcode-Scan | `flutter_zxing` (ZXing, lokal) | Kein ML Kit. Paketstatus geprüft am 03.10.2026: Version 3.1.0 vom 25.09.2026, MIT, aktiv gepflegt. Im Web-Frontend wird der Barcode eingetippt |
| Lebensmitteldaten | Open Food Facts | Kostenlos, Barcode-Abfrage, ODbL (Quelle nennen) |
| Backend | FastAPI (Python) | OpenAPI-Doku automatisch |
| Datenbank | PostgreSQL (Dev und Tests: SQLite) | Relational, Historie, Teilen |
| Dateispeicher | Lokales Dateisystem oder MinIO hinter Interface | Austauschbar; für den Start reicht Dateisystem |
| GPX | Eigener, toleranter Leser und Schreiber auf Basis der Python-Standardbibliothek (kein gpxpy: es bricht bei einzelnen fehlerhaften Werten die ganze Datei ab); FIT später | Garmin-Daten |
| Höhendaten | Open-Meteo Elevation API (nur wenn der Track keine Höhe hat) | Für manuell gezeichnete Tracks |
| Auth | E-Mail + Passwort (argon2), JWT als Access-Token, Refresh-Token in der Datenbank | Kein Drittanbieter |
| Wetter | Open-Meteo (Forecast + Archive) | Kostenlos, kein Key |
| Gipfel und Pässe | OpenStreetMap über die Overpass-API | Kostenlos, kein Key, ODbL (Quelle nennen); öffentliche Instanz ist zeitweise überlastet, URL konfigurierbar |
| Deployment | Docker Compose, Anbindung an vorhandenen Reverse Proxy | Siehe Abschnitt 11 |

## 4. Gesamtarchitektur

```
┌────────────────────────────┐        ┌───────────────────────────────┐
│ Android-App (Flutter)      │  HTTPS │ FastAPI Backend               │
│  core/  features/*         │◄──────►│  core/  modules/*             │
│  Drift (lokal, offline)    │  JSON  │  PostgreSQL + Dateispeicher   │
└────────────────────────────┘        └───────────────────────────────┘
┌────────────────────────────┐  HTTP          ▲            │
│ Web-Frontend (Flask)       │────────────────┘            │
│  Seiten für den Browser    │  JSON (gleiche REST-API)    │
└────────────────────────────┘                             │
                          Open-Meteo, Open Food Facts, (später hikr.org)
```

Prinzipien:
1. **API-first**: App und Web-Frontend sprechen nur mit der REST-API. Das Web-Frontend greift nie direkt auf Datenbank oder Dateispeicher zu.
2. **Local-first** (Android-App): Änderungen landen zuerst in Drift, ein Sync-Dienst schickt sie an den Server. Das Web-Frontend arbeitet online.
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
├── backend/                  # FastAPI
├── app/                      # Flutter, nur Android
└── web/                      # Flask-Web-Frontend
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
Jedes Feature registriert sich über ein `FeatureModule` (Routen, Navigationseintrag, Provider); verdrahtet wird in `lib/app.dart`. Der Core importiert keine Features. Die Navigation zeigt nur Features, deren Modul der Server meldet. In `core/map` liegen die wiederverwendbaren Bausteine: Karte, Track zeichnen, Punkt setzen, Foto-Marker, Höhenprofil.

## 6. Datenmodell

Alle IDs sind UUIDs und clientseitig erzeugbar. Hauptdaten haben `created_at`, `updated_at`, `deleted_at` (Soft Delete für Sync).

### 6.1 Nutzer (Modul auth)
**user** (Tabelle `user_account`, da `user` in PostgreSQL reserviert ist): id, email (kleingeschrieben, eindeutig), display_name, password_hash, role (`user` | `admin`), created_at
**user_profile** (optional, für Kalorienschätzung): weight_kg, birth_year, sex (`female` | `male` | `trans` | `undisclosed` = keine Angabe, optional), max_heart_rate (optional), resting_heart_rate (optional)
**refresh_token**: id, user_id, token_hash (SHA-256), created_at, expires_at, revoked_at

### 6.2 Ausrüstung (Modul gear)
**gear_item** (persönliche Gegenstände)
- id, owner_id, catalog_id (optional, Verweis auf Katalog)
- name, brand, type_id (Verweis auf `gear_type`), weight_g
- purchase_date, purchase_price (Gleitkommazahl, 0 bis 1 000 000, höchstens zwei Nachkommastellen), currency (ISO 4217, Pflicht sobald ein Preis gesetzt ist)
- description, notes, website_url, image_file_id
- status (`active` | `retired`)
- optional: serial_number, size, color
- tags (beliebig viele, siehe `gear_tag`)

**gear_catalog_item** (gemeinsamer Katalog, nutzerübergreifend)
- id, created_by, name, brand, type_id (nur Standardkategorien), nominal_weight_g, website_url, image_file_id
- status (`pending` | `approved` | `rejected`), Moderation durch `admin`

Ablauf: Nutzer legt Gegenstand an → kann Katalogeintrag vorschlagen („Teilen im Katalog“, nur Produktdaten: Name, Marke, Kategorie, Gewicht, Website, Bild; keine persönlichen Felder wie Kaufpreis/-datum, Notizen, Beschreibung, Seriennummer) → Admin gibt frei oder lehnt ab und kann die Produktdaten dabei korrigieren. Ein Gegenstand kann erst nach einer Ablehnung erneut vorgeschlagen werden. Beim Anlegen eines eigenen Gegenstands lässt sich ein Katalogeintrag als Vorlage übernehmen (Kopie, spätere Katalogänderungen verändern persönliche Gegenstände nicht).

**gear_type**: id, owner_id (leer = Standardliste), name, sort_order. Die Standardliste wird per Migration angelegt; wird eine Kategorie gelöscht, verlieren ihre Gegenstände nur die Zuordnung.
**gear_tag** (frei definierbare Schlagworte je Nutzer, z. B. „Winter“, „Verleihbar“): id, owner_id, name (je Nutzer eindeutig), color (optional, `#RRGGBB`); Zuordnung über **gear_item_tag** (gear_item_id, tag_id). Wird ein Tag gelöscht, bleiben die Gegenstände erhalten.
**gear_list** (Packlisten-Vorlage): id, owner_id, name, description + **gear_list_item**: gear_item_id, quantity

Löschen eines Gegenstands oder einer Packliste ist ein Soft Delete (`deleted_at`); das Bild des Gegenstands wird dabei entfernt.

Auswertungen (abgeleitet): Touren und Gesamtstrecke je Gegenstand (mit Modul `protocols`); Summen über `/gear/summary`: Anzahl, Gesamtgewicht und Kaufwert (je Währung getrennt, keine Umrechnung), wahlweise gruppiert nach Kategorie, Tag, Status oder Marke und mit denselben Filtern wie die Liste. Bei Gruppierung nach Tag zählt ein Gegenstand in jedem seiner Tags.

### 6.3 Ernährung (Modul nutrition)
**food_item**
- id, owner_id (leer = gemeinsamer Katalog), barcode (EAN-8, UPC-A, EAN-13 oder GTIN-14, indexiert), name, brand
- kcal_per_100g (0–900, bei eigenen Produkten Pflicht), protein_g, carbs_g, fat_g, sugar_g, salt_g (je 100 g, 0–100)
- serving_size_g, image_url (Bild-Upload für eigene Produkte ist noch nicht vorgesehen)
- source (`openfoodfacts` | `custom`), source_synced_at
- visibility (`private` | `catalog_pending` | `catalog_rejected` | `catalog`)
- catalog_id (bei privaten Produkten: Katalogeintrag, von dem kopiert bzw. als der es vorgeschlagen wurde), proposed_by (wer den Katalogeintrag vorgeschlagen hat; wird nie ausgegeben)

Plausibilitätsprüfung bei der Eingabe: Zucker ≤ Kohlenhydrate; Eiweiß + Kohlenhydrate + Fett ≤ 100 g. Werte von Open Food Facts werden tolerant gelesen (unplausible Einzelwerte bleiben leer; kJ wird in kcal umgerechnet, wenn kcal fehlt).

Gemeinsamer Katalog = Open-Food-Facts-Cache plus von Nutzern vorgeschlagene eigene Produkte (nach Freigabe durch `admin`). Ein Vorschlag ist eine Kopie des privaten Produkts; sie gehört bis zur Freigabe dem Vorschlagenden und wird erst dann für alle sichtbar. Der Admin kann die Daten beim Freigeben korrigieren; je Barcode gibt es höchstens einen Katalogeintrag. Eigene Korrekturen an einem Katalogprodukt werden als private Kopie des Nutzers gespeichert; in Suche und Barcode-Abfrage ersetzt sie für diesen Nutzer den Katalogeintrag.

Open-Food-Facts-Einträge werden nach `OPENFOODFACTS_CACHE_DAYS` (Standard 30) beim nächsten Barcode-Abruf aktualisiert; ist der Dienst nicht erreichbar, wird der alte Stand geliefert.

### 6.4 Protokolle (Modul protocols)
**tour**
- id, owner_id, title, summary (Fazit)
- start_time, end_time, duration_minutes (berechnet, überschreibbar)
- start_point, end_point (lat, lon, optional Name), `points_source` (`gpx` | `manual`)
- pack_weight_start_g (aus Ausrüstung berechnet, überschreibbar)
- calories_burned, `calories_burned_source` (`manual` | `estimated`), calories_eaten (aus Einträgen)
- Überschreibbare Werte: Die Felder `duration_minutes` und `pack_weight_start_g` enthalten nur den manuellen Wert (leer = nicht überschrieben). Die berechneten Werte liefert die API getrennt im Block `computed` (`duration_minutes`, `pack_weight_start_g`, `calories_eaten`); so kann der Client die Tour unverändert zurückschicken, ohne berechnete Werte zu manuellen zu machen.
- gpx_file_id, `track_source` (`device` | `drawn` | `none`), track_stats (JSON)
- cover_photo_id
- version (Revisionszähler, Konflikterkennung)

**tour_gear**: id, tour_id, gear_item_id (bleibt leer, wenn der Gegenstand endgültig entfernt wird), added_by, name_snapshot, brand_snapshot, weight_g_snapshot, quantity, carried (zählt ins Startgewicht); je Tour jeder Gegenstand höchstens einmal
**tour_food_entry**: id, tour_id, food_item_id, added_by, name_snapshot, kcal_per_100g_snapshot, amount_g, kcal_snapshot (aus Menge und Momentaufnahme), carried, eaten, eaten_at (optional), sort_order

Momentaufnahmen entstehen beim Hinzufügen und ändern sich nicht, wenn Gegenstand oder Lebensmittel später geändert oder gelöscht werden. Startgewicht (berechnet) = mitgeführte Ausrüstung × Stückzahl + mitgeführtes Essen; gegessene Kalorien = Summe der Einträge mit `eaten`.
**contact**: id, owner_id, display_name, linked_user_id (leer = Platzhalter); Löschen ist ein Soft Delete, alte Touren zeigen den Namen weiter
**tour_partner**: tour_id, contact_id, added_by. Partner gehören zum Tourdokument (`partners`); neue Partner stammen aus den Kontakten dessen, der sie einträgt. Partner zu sein gibt keinen Zugriff auf die Tour – dafür ist die Freigabe da.

Platzhalter → echter User: `contact.linked_user_id` setzen; gilt sofort in allen Touren des Owners.

**tour_peak**: id, tour_id, name, elevation_m, lat, lon, reached_at, sort_order, source (`manual` | `osm` = automatisch am Track gefunden)

**tour_waypoint** (wie bei wanderer): id, tour_id, name, description, icon, lat, lon, track_distance_m, elevation_m, kind (`custom` | `photo` | `peak` | `saddle` | `waypoint` | `high_point`), source (`manual` | `photo` | `osm` | `gpx` | `track`), osm_id, reached_at (Zeitpunkt, zu dem der Track die Stelle erreicht)
**tour_photo**: id, tour_id, file_id, thumb_file_id (Vorschaubild, höchstens 400 px), added_by, caption, taken_at, exif_lat/exif_lon/exif_altitude (Position aus dem Bild, damit die automatische Zuordnung wiederherstellbar bleibt), lat, lon, `position_source` (`exif_gps` | `exif_time` | `manual` | `none`), track_distance_m (Position entlang des Tracks), elevation_m, waypoint_id (optional), sort_order. Die Tour speichert zusätzlich `photo_time_offset_seconds`.

**tour_weather**: id, tour_id, sample_point (`start` | `summit` | `end` | `manual`, je Tour einmal), lat, lon, elevation_m, time, Werte (temperature_c, apparent_temperature_c, wind_speed_kmh, wind_gusts_kmh, precipitation_mm, cloud_cover_pct, freezing_level_m, weather_code nach WMO), source (`open-meteo-archive` | `open-meteo-forecast`), fetched_at

**track_series**: tour_id, point_count, abgetastete Zeitreihe als Spalten gleicher Länge (Zeit, Distanz, Position, Höhe, Herzfrequenz, Kadenz, Temperatur; höchstens 2000 Punkte, gleichmäßig ausgedünnt); Original-GPX bleibt unverändert im Dateispeicher. Ältere GPX-Dateien bleiben beim Ersetzen erhalten, weil Revisionen auf sie verweisen.

### 6.5 Teilen und Historie
**tour_share**: tour_id, user_id, permission (`read` | `edit`)
**tour_public_link**: id, tour_id, token (zufälliges UUIDv4), created_by, created_at, expires_at, revoked_at, Optionen (`hide_exact_start`, `strip_photo_gps`, `show_health_data`; alle standardmäßig aus)
**tour_revision**: id, tour_id, version (je Tour eindeutig), author_user_id (wird beim Entfernen des Nutzers geleert), created_at, kind (`created` | `updated` | `restored` | `deleted`), change_summary (geänderte Felder bzw. wiederhergestellte Version), snapshot (JSON), diff (JSON)

### 6.6 Dateien (core)
**file_object**: id, owner_id, storage_key, mime, size, sha256, created_at

## 7. Wichtige Abläufe

**GPX von Garmin und anderen Quellen**
Upload → serverseitig parsen. Neben Position, Höhe und Zeit werden Sensor-Erweiterungen gelesen (Garmin TrackPointExtension: Herzfrequenz, Kadenz, Temperatur). Daraus entstehen `track_stats`: Distanz, Höhenmeter hoch/runter, tiefster/höchster Punkt, Gesamt- und Bewegungszeit, Herzfrequenz (Durchschnitt, Maximum, Zeit je Zone), Kadenz, Temperatur. Der Parser ist tolerant: Fehlende Felder (z. B. keine Zeitstempel, keine Höhe, kein Puls) führen nie zu einem Fehler, die jeweilige Auswertung bleibt leer. Spätere Erweiterung: FIT-Dateien direkt importieren.

Umsetzung der Auswertung (Formeln und Parameter stehen in `protocols/track.py`):
- Gelesen werden alle Trackpunkte (mehrere Tracks und Segmente hintereinander); gibt es keine, die Routenpunkte. Einzelne unlesbare Werte werden ignoriert, Punkte ohne gültige Position übersprungen. Dateien mit `DOCTYPE` oder ohne Punkte werden abgelehnt (422 `invalid_gpx`).
- Distanz: Summe der Großkreisabstände. Höhenmeter: Änderungen zählen erst ab 3 m seit dem letzten gezählten Punkt (filtert Sensorrauschen). Bewegungszeit: Abschnitte mit mindestens 0,3 m/s.
- Herzfrequenz: Durchschnitt zeitgewichtet, Minimum, Maximum und Zeit je Zone. Zonen: bis 60 %, 60–70 %, 70–80 %, 80–90 % und ab 90 % der Maximalherzfrequenz. Diese stammt aus dem Profil, sonst 220 minus Alter; ohne beides oder ohne Zeitstempel gibt es keine Zonen.
- Hat der Track gar keine Höhe, wird sie über Open-Meteo ergänzt (bei langen Tracks an höchstens 300 Stützpunkten, dazwischen interpoliert); `elevation_source` nennt die Herkunft (`track` | `open-meteo`). Ist der Dienst nicht erreichbar, bleibt die Höhenauswertung leer.
- Start- und Endpunkt der Tour folgen dem Track (`points_source = gpx`); hat der Track Zeitstempel, auch Start- und Endzeit der Tour.
- Herzfrequenz (Statistik und Zeitreihe) sieht nur der Owner; in Freigaben, Export für andere und Public Links fehlt sie, bei Links außer mit `show_health_data`. Das Original-GPX lädt nur der Owner herunter.
- Public Links mit `hide_exact_start` schneiden an beiden Enden des Tracks alles im Umkreis von 500 m um Start und Ende ab.
- Track-Änderungen stehen in der Historie; Wiederherstellen baut Statistik und Zeitreihe aus der damaligen GPX-Datei neu auf. Track und Punkte zählen dabei zu den Owner-Feldern.

**Gipfel, Pässe und markante Stellen am Track**
Nach jedem Speichern eines Tracks (Upload oder gezeichnet) sucht der Server die Stellen, an denen der Track vorbeiführt, und trägt sie in die Tour ein:
- Benannte Gipfel (`natural=peak`), Sättel (`natural=saddle`) und Pässe (`mountain_pass=yes`) aus OpenStreetMap, die höchstens `PLACE_MAX_DISTANCE_M` (Standard 10 m) neben der Tracklinie liegen. Gemessen wird zur Linie zwischen den Punkten, nicht nur zu den Punkten selbst.
- Die benannten Wegpunkte (`<wpt>`) aus der GPX-Datei.
- Der höchste Punkt des Tracks, wenn dort (±100 m entlang des Tracks) kein Gipfel gefunden wurde.
- Je Stelle: Art, Name, Höhe (vermessene Höhe aus OpenStreetMap, sonst Höhe des Tracks), Lage am Track und Uhrzeit des Erreichens.
- Die Stellen stehen als Wegpunkte in der Tour (mit `kind` und `source`); Gipfel kommen zusätzlich in die Gipfelliste, sofern dort kein gleichnamiger Eintrag steht. Alles lässt sich umbenennen und löschen.
- Bei einem neuen Track werden die automatisch gefundenen Einträge ersetzt; von Hand angelegte bleiben. Wird der Track entfernt, verschwinden die automatischen Einträge.
- An OpenStreetMap geht nur der umschließende Kartenausschnitt, nie der Track. Ist der Dienst nicht erreichbar, wird der Track trotzdem gespeichert; `POST /tours/{id}/track/places` holt die Erkennung nach.
- OpenStreetMap-Daten stehen unter der ODbL: Wo Stellen mit `source = osm` gezeigt werden, wird die Quelle genannt (`attribution` in der Übersicht).

Die **Übersicht** (`GET /tours/{id}/overview`) orientiert sich am Kopf eines Tourenberichts auf hikr.org (Wegpunkte, Zeitbedarf, Aufstieg, Abstieg, Strecke): Kennzahlen der Tour und darunter der Wegverlauf von Start bis Ende mit allen Stellen in Track-Reihenfolge, je mit Höhe und Uhrzeit. Von hikr.org wurden weder Inhalte noch Gestaltung übernommen.

**Einfache, manuell erstellte Tracks**
Wer kein Gerät dabei hatte, zeichnet den Track in der App auf der Karte (Punkte setzen, verschieben, löschen). Daraus erzeugt die App ein GPX (`track_source = drawn`). Fehlen Höhen, werden sie über die Open-Meteo-Elevation-API ergänzt. Zeiten gibt der Nutzer manuell an; Dauer und Tempo sind dann Schätzwerte oder manuell. Auch ein einfaches, extern erstelltes GPX ohne Zeit und Puls lässt sich hochladen.

**Start-/Endpunkt und Wetter**
1. Track vorhanden → Start und Ende daraus (`points_source = gpx`), Zeitfenster aus den Zeitstempeln (sonst manuelle Zeiten).
2. Kein Track → Nutzer setzt Start und Ende auf der Karte, dazu Datum und Uhrzeit (`manual`).
3. Wetter wird nach dem Speichern automatisch abgerufen: Open-Meteo (Archive für Vergangenheit, Forecast für Zukunft) für Start, Gipfel (höchster Punkt) und Ende, jeweils für die passende Stunde und die Höhe der Position.
4. Ergebnis wird gespeichert (`tour_weather`). Neuabruf manuell; ändern sich Punkte oder Zeiten, wird er angeboten.

Umsetzung:
- `PUT /tours/{id}/points` setzt Start und Ende manuell (nur Owner). Mit Track folgen die Positionen dem Track (abweichende Positionen → 409 `points_from_track`); die Ortsnamen lassen sich weiterhin setzen.
- Automatischer Abruf genau einmal: sobald die Tour nach einem Speichern (Punkte, Track, Tourdokument) mindestens einen Messpunkt mit Zeit hat und noch kein Wetter. Schlägt er fehl, wird trotzdem gespeichert.
- Spätere Änderungen an Punkten oder Zeiten rufen nicht erneut ab; die Tour meldet dann `weather_outdated = true`, und der Client bietet den Neuabruf an (`POST /tours/{id}/weather/fetch`, nur Owner; optional mit einem zusätzlichen manuellen Messpunkt).
- Gipfel: höchster Punkt des Tracks zu dessen Zeitstempel; ohne Track der erste Gipfel der Tour mit Koordinaten (Zeit: `reached_at`, sonst Mitte zwischen Start und Ende).
- Die Höhe des Messpunkts wird an Open-Meteo übergeben, damit die Temperatur zur Höhe passt. Daten älter als fünf Tage kommen aus dem Archiv, alles andere aus der Vorhersage; die Nullgradgrenze liefert nur die Vorhersage.
- Wetter ist abgeleitet und kein Teil der Historie. Es steht in Tour, Export und öffentlicher Ansicht; bei Links mit `hide_exact_start` fehlt es, weil es die genauen Koordinaten des Starts trägt.

**Kalorienverbrauch**
Manuell eingegebene Werte haben immer Vorrang (`manual`). Fehlt ein Wert, schätzt der Server (`estimated`, in der UI klar als Schätzung markiert):
- Mit Herzfrequenzdaten und Nutzerprofil (Gewicht, Alter, Geschlecht): pulsbasierte Formel. Bei `trans`, `undisclosed` oder fehlender Angabe wird der Mittelwert der Formeln für `female` und `male` verwendet.
- Ohne Puls: Berechnung aus Körper- plus Rucksackgewicht, Distanz, Höhenmetern und Dauer mit einer anerkannten Geh-/Wanderformel.
- Ohne Profil oder Track: keine Schätzung, Hinweis zur Eingabe.
Die verwendete Formel und Parameter werden im Code dokumentiert und als Tooltip erklärt. Änderungen an Track, Gewicht oder Profil lösen eine Neuberechnung aus, solange der Wert nicht manuell ist.

Umsetzung (Formeln und Quellen stehen in `protocols/calories.py`):
- Die Schätzung wird nicht gespeichert, sondern bei jedem Lesen aus Track-Statistik, Startgewicht und dem aktuellen Profil des Owners berechnet. Änderungen wirken dadurch sofort und erzeugen keine Revision. Folge: Ändert der Owner später sein Gewicht, ändern sich auch die Schätzungen älterer Touren; wer einen Wert festhalten will, trägt ihn manuell ein.
- Pulsbasiert (`heart_rate`): Keytel et al. 2005 mit durchschnittlicher Herzfrequenz, Körpergewicht, Alter im Jahr der Tour und Dauer des Tracks. Braucht Puls im Track, Gewicht und Geburtsjahr.
- Ohne Puls (`acsm_walking`): ACSM-Gehformel, über die Tour summiert: Sauerstoff [ml/kg] = 0,1 · Distanz + 1,8 · Höhenmeter aufwärts + 3,5 · Minuten; kcal = Sauerstoff · (Körper- + Rucksackgewicht) / 1000 · 5. Braucht Track, Gewicht und eine Dauer (aus dem Track, sonst aus der Tour). Grenzen: Abstieg zählt nicht, der Rucksack zählt wie Körpergewicht, schwieriges Gelände kostet mehr.
- Keine Schätzung: ohne Gewicht im Profil (`no_profile`), ohne Track (`no_track`) oder ohne Dauer (`no_duration`).
- API: `calories_burned` enthält nur den manuellen Wert, `computed.calories_burned` die Schätzung, `calories_burned_source` sagt, welcher gilt (`manual` | `estimated`). `calories_estimate` (Verfahren, Parameter oder Grund) sieht nur der Owner, weil es Gewicht und Alter enthält. `POST /tours/{id}/calories/estimate` verwirft den manuellen Wert zugunsten der Schätzung.

**Fotos und Track**
1. Upload der Fotos (mehrere gleichzeitig). EXIF wird gelesen: Aufnahmezeit und, falls vorhanden, GPS.
2. Zuordnung zum Track: mit EXIF-GPS → nächster Punkt des Tracks; ohne GPS → über die Aufnahmezeit zum Zeitstempel im Track (mit einstellbarem Zeitversatz, z. B. wegen Kamera-/Uhrzeit-Abweichung); sonst bleibt das Foto ohne Position und kann per Hand auf der Karte oder im Höhenprofil gesetzt werden.
3. Ergebnis: `track_distance_m`, Koordinate und Höhe pro Foto.
4. Funktion „Aus Fotos“: Aus Fotos mit GPS lassen sich Wegpunkte automatisch anlegen.
5. Ein Foto lässt sich als Titelbild (`cover_photo_id`) festlegen.

Umsetzung (Regeln und Parameter stehen in `protocols/photos.py`):
- Upload von bis zu 20 Fotos je Anfrage (JPEG, PNG, WebP), höchstens 500 je Tour. Ein ungültiges Bild lehnt den ganzen Upload ab. Gespeichert werden ein neu kodiertes Bild und ein Vorschaubild, beide ohne EXIF-Daten.
- EXIF-GPS: nächster Punkt des Tracks, sofern er höchstens 1 km entfernt ist; sonst behält das Foto seine GPS-Position ohne Lage am Track.
- Aufnahmezeit: Position wird auf dem Track interpoliert, wenn die Zeit im Zeitraum des Tracks liegt (Toleranz 10 Minuten an beiden Enden). Zeiten ohne Zeitzone gelten als UTC; der Zeitversatz der Tour (`photo_time_offset_seconds`, z. B. −7200 für eine Kamera auf Sommerzeit) wird vorher addiert und gilt für alle Fotos.
- Manuell: Position auf der Karte (`lat`/`lon`) oder im Höhenprofil (`track_distance_m`); `auto_position` stellt die automatische Zuordnung wieder her. Manuelle Positionen bleiben bei neuem Track oder geändertem Zeitversatz erhalten.
- Wird der Track ersetzt oder entfernt, werden alle nicht manuell gesetzten Fotos und die Wegpunkte neu zugeordnet.
- Reihenfolge der Galerie: entlang des Tracks, Fotos ohne Position am Ende.
- „Aus Fotos“ legt Wegpunkte aus Fotos mit EXIF-GPS an, die noch keinem Wegpunkt zugeordnet sind; Fotos im Umkreis von 30 m teilen sich einen Wegpunkt.
- Historie: Foto-Metadaten (Beschriftung, Position, Wegpunkt, Titelbild, Zeitversatz) stehen in den Revisionen. Das Löschen eines Fotos entfernt seine Dateien endgültig; Wiederherstellen stellt deshalb nur Metadaten noch vorhandener Fotos wieder her und löscht nie Fotos.
- Öffentliche Links zeigen die Fotos ohne IDs (Adresse über die Position in der Galerie). `strip_photo_gps` blendet die Positionen aus; `hide_exact_start` blendet sie bei Fotos im Umkreis von 500 m um Start und Ende aus.
- Wird eine Tour gelöscht, werden ihre Fotos und GPX-Dateien endgültig aus dem Speicher entfernt.

**Ausrüstung in Touren**
Auswahl aus der Datenbank oder per Packlisten-Vorlage. Startgewicht = Summe der mitgeführten Gegenstände (plus geplantes Essen), überschreibbar.

**Barcode-Scan und Essen**
Scanner liest EAN lokal → lokale Datenbank → Backend `GET /nutrition/barcode/{ean}` (eigene Produkte, dann gemeinsamer Katalog, dann Open Food Facts, mit Cache; 404 `product_not_found` = unbekannt, 502 `source_unavailable` = Open Food Facts nicht erreichbar) → sonst Formular für ein eigenes Produkt (Barcode wird mitgespeichert) → Menge eingeben → Kalorien als Momentaufnahme in der Tour.

**Änderungshistorie**
Jede Änderung erzeugt eine `tour_revision` (Autor, Zeit, Diff, Snapshot). Zeitleiste, Vergleich zweier Stände, Wiederherstellen (erzeugt neue Revision). Konfliktschutz über `version`: veralteter Stand → 409 mit aktuellem Stand; Client führt feldweise zusammen und fragt bei Überschneidung.

Umsetzung:
- Alle Änderungen an einer Tour (Dokument, Wegpunkte, Löschen, Wiederherstellen) laufen durch `history.record_change`. Revisionen werden nur eingefügt, nie geändert oder gelöscht.
- Der Snapshot enthält den vollständigen bearbeitbaren Stand: Textfelder, Zeiten, manuelle Werte sowie die Listen Ausrüstung, Essen, Gipfel und Wegpunkte (mit ihren Momentaufnahmen). Spätere Schritte (Track, Punkte, Fotos, Partner) erweitern ihn.
- Der Diff nennt bei einfachen Feldern `{old, new}`, bei Listen `{added, removed, changed, reordered}`; Einträge werden über ihre `id` verglichen.
- Ein `PUT`, das nichts ändert, erzeugt keine Revision und erhöht die Version nicht.
- `PUT /tours/{id}` verlangt im Body die `version`, auf der die Änderung beruht. Weicht sie ab: 409 `version_conflict`, der Body enthält unter `current` die aktuelle Tour. Zusätzlich sichert die Datenbank gleichzeitige Schreibzugriffe ab (Update nur, wenn die Version noch stimmt). Wegpunkt-Endpunkte, Löschen und Wiederherstellen verlangen keine Basisversion.
- Wiederherstellen setzt den Stand einer Revision vollständig zurück. Verweise auf inzwischen entfernte Gegenstände oder Lebensmittel werden geleert, die Momentaufnahme bleibt. Mit `edit` ist es nur möglich, wenn sich dabei keine Owner-Felder ändern (sonst 403).

**Offline-Sync**
Lokale Änderungen mit `updated_at`/`deleted_at` und Basis-`version`; Konfliktregel wie bei der Historie. Fotos und GPX laufen über eine getrennte Upload-Warteschlange.

Umsetzung auf dem Server:
- Eigenes Modul `sync` mit den beiden Endpunkten. Die Sammlungen liefern die Fachmodule: Jedes Modul meldet seine Quellen beim Core an (`core/sync.py`); das `sync`-Modul kennt die Fachmodule nicht und umgekehrt.
- `GET /sync/changes?since=` liefert je Sammlung `changed` (geänderte Datensätze), `deleted` (IDs gelöschter Datensätze) und `server_time` für den nächsten Abruf. Ohne `since` kommt alles.
- Sammlungen: `gear_items`, `foods` (eigene Lebensmittel) und `tours` mit Änderungen seit `since`; `gear_types`, `gear_tags` und `gear_lists` sind klein und kommen immer vollständig (`full = true`).
- Bei `tours` nennt `ids` zusätzlich alle noch sichtbaren Touren: Wird eine Freigabe entfernt, fehlt die Tour dort, und der Client löscht seine Kopie. Geteilte Touren kommen mit denselben Einschränkungen wie sonst (keine Gesundheitsdaten).
- `POST /sync/push` nimmt bis zu 500 Operationen (`upsert` oder `delete` mit `id`) und wendet sie der Reihe nach über dieselben Dienste an wie die normalen Endpunkte – Rechte, Prüfungen und Historie gelten unverändert. Jede Operation bekommt ein eigenes Ergebnis: `ok` mit dem gespeicherten Datensatz, `conflict` mit dem aktuellen Stand des Servers oder `error` mit Code; ein Fehler hält die übrigen nicht auf.
- Konflikte: Touren über `base_version` (wie bei `PUT`); Ausrüstung und Lebensmittel über `base_updated_at`. Schreibbar per Push sind `gear_items`, `foods` und `tours`.
- Fotos und GPX-Dateien gehören nicht zum Push; die App lädt sie aus ihrer eigenen Warteschlange über die normalen Endpunkte hoch.

Umsetzung in der Android-App (`core/sync`):
- Ist der Server beim Speichern nicht erreichbar, wird die Änderung in die lokale Kopie geschrieben und in eine Warteschlange gelegt. Das gilt für Ausrüstungsgegenstände, eigene Lebensmittel und Touren (anlegen, ändern, löschen). Mehrere Änderungen am selben Datensatz werden zu einer zusammengefasst; offline Angelegtes und wieder Gelöschtes erreicht den Server nie.
- GPX-Dateien und Fotos warten in einer eigenen Upload-Warteschlange.
- Abgleich: beim Start, nach dem Anmelden, wenn die App in den Vordergrund kommt, und auf Knopfdruck im Profil. Reihenfolge: Änderungen senden, Dateien hochladen, Änderungen des Servers holen.
- Konflikte bei Touren führt die App feldweise zusammen und sendet erneut; nur wenn beide dasselbe Feld geändert haben, wartet die Änderung auf eine Entscheidung. Bei Ausrüstung und Lebensmitteln wartet jeder Konflikt auf eine Entscheidung. Im Profil lässt sich je Konflikt wählen: eigene Änderung behalten oder Stand des Servers übernehmen. Vom Server abgelehnte Änderungen lassen sich verwerfen.
- Datensätze, deren Änderung noch wartet, überschreibt der Abgleich nicht.
- Beim Abmelden wird die lokale Kopie samt Warteschlange gelöscht; warten noch Änderungen, fragt die App vorher nach.
- Nur online möglich bleiben: Tags, Kategorien und Packlisten ändern, Bilder von Gegenständen, Katalogvorschläge, Wegpunkte, Foto-Änderungen, Start und Ende, Freigaben und Links, Wiederherstellen aus dem Verlauf.

**Teilen mit Usern**
- Owner: alles.
- `edit`: Textfelder (Titel, Fazit, Beschreibungen), Listen (Ausrüstung, Essen, Partner, Gipfel, Wegpunkte) und **Fotos** (hinzufügen, entfernen, Beschriftung, Titelbild, Position).
- `edit` darf **nicht**: GPX/Track und Start-/Endpunkte ändern, Freigaben und Links verwalten, Tour löschen.
- `read`: nur lesen.
Empfänger sehen die Tour im Tab „Mit mir geteilt“ und können die Freigabe selbst wieder ablegen. Freigaben und Links sind kein Teil der Tour-Historie. Entfernen des Teilens wirkt sofort serverseitig; die lokale Kopie wird beim nächsten Sync gelöscht.

**Teilen per Link**
`https://hiker.lacasa.internal/p/<token>`, Token = zufälliges UUIDv4. Nur lesend, widerrufbar, optional befristet, ohne Login, `noindex`, Rate-Limit, ohne E-Mail-Adressen oder interne IDs. Optional: genauen Start verbergen, Foto-GPS entfernen. Die Basis-URL kommt aus der Konfiguration (`PUBLIC_BASE_URL`).

Umsetzung:
- Je Tour sind mehrere Links möglich (z. B. mit unterschiedlichen Optionen); nur der Owner legt sie an, listet und widerruft sie.
- Die öffentliche Ansicht enthält Titel, Fazit, Anzeigename des Owners, Zeiten, Dauer, Startgewicht, gegessene Kalorien, Partner (nur Namen), Gipfel, Wegpunkte, Ausrüstung und Essen – ohne IDs und E-Mail-Adressen. Der Kalorienverbrauch zählt zu den Gesundheitsdaten und erscheint nur mit `show_health_data`.
- `hide_exact_start` rundet Start- und Endpunkt auf zwei Nachkommastellen (rund 1 km) und lässt deren Namen weg. Sobald es einen Track gibt (Schritt 7), muss er dort ebenfalls gekürzt werden.
- Ungültige, abgelaufene und widerrufene Tokens sowie gelöschte Touren antworten gleich mit 404.
- Antwort-Header: `X-Robots-Tag: noindex, nofollow`, `Cache-Control: no-store`, `Referrer-Policy: no-referrer`.
- Das Token steht im Zugriffslog der API nur als `[redacted]` (Filter auf dem uvicorn-Access-Log für `/public/tours/` und `/p/`). Das Web-Frontend und der vorgeschaltete Reverse Proxy brauchen dieselbe Regel in ihrer Log-Konfiguration (Schritte 13 und 14).

**Export JSON**
Versioniertes Schema (`schema_version`): Tour, Ausrüstung (Snapshots), Essen, Partner (Anzeigenamen), Wetter, Track-Statistik, Wegpunkte, Foto-Metadaten (inkl. Position) und Verweise auf Dateien oder ZIP mit den Dateien.

Stand `schema_version` 1: Tour (mit effektiven Werten für Dauer und Startgewicht), Partner, Gipfel, Wegpunkte, Ausrüstung, Essen, Track-Statistik und Foto-Metadaten und Wetter. Ein ZIP mit GPX und Bildern gibt es noch nicht. Exportieren darf jeder mit Lesezugriff; die Antwort kommt als Download (`Content-Disposition`).

## 8. API (Version `/api/v1`)

### Auth und Profil
| Methode | Pfad | Zweck |
|---|---|---|
| POST | /auth/register, /auth/login, /auth/refresh | Konto/Tokens (Refresh rotiert das Token) |
| POST | /auth/logout | Refresh-Token widerrufen |
| POST | /auth/login/mfa | Zweiter Schritt der Anmeldung: `mfa_token` aus der Antwort `mfa_required` und Code |
| POST | /auth/password | Passwort ändern (bisheriges + neues); alle anderen Sitzungen enden |
| POST | /auth/mfa/setup, /auth/mfa/enable | Zweiten Faktor einrichten: Geheimnis holen, mit erstem Code bestätigen; liefert neue Tokens und Wiederherstellungscodes |
| POST | /auth/mfa/recovery-codes, /auth/mfa/disable | Neue Wiederherstellungscodes; Abschalten nur, wenn `MFA_REQUIRED=false` |
| GET/POST | /auth/oidc, /auth/oidc/start, /auth/oidc/callback | SSO: ob angeboten, Anmeldung beginnen, mit `state` und `code` abschließen |
| GET | /me/session | Was der Sitzung noch fehlt (`mfa_setup_required`, `password_change_required`) |
| GET/DELETE/POST | /admin/users, /admin/users/{id}, …/reset-password, …/reset-mfa | Nutzerverwaltung (nur `admin`) |
| GET | /users/lookup?email= | Nutzer für Freigabe/Partner finden (exakte Adresse; liefert nur ID und Anzeigename) |
| GET | /me | Eigenes Konto |
| GET/PUT | /me/profile | Profil für Kalorienschätzung |
| GET | /modules | Aktive Module (ohne Login), damit der Client nur vorhandene Funktionen zeigt |

### Protokolle
| Methode | Pfad | Zweck |
|---|---|---|
| GET, POST | /tours | Eigene + geteilte listen (`scope` = `all`/`mine`/`shared`, `q`, `start_from`, `start_to`, Paging) / erstellen |
| GET, PUT, DELETE | /tours/{id} | Lesen, Editieren, Löschen (nur Owner, Soft Delete) |
| GET | /tours/{id}/revisions, /revisions/{rev} | Historie (Liste mit Paging, neueste zuerst / eine Revision mit Snapshot und Diff; `rev` = Versionsnummer) |
| GET | /tours/{id}/revisions/{rev}/compare/{other} | Diff zwischen zwei Versionen |
| POST | /tours/{id}/revisions/{rev}/restore | Wiederherstellen |
| GET, POST | /tours/{id}/shares | Freigaben listen / teilen (`read`/`edit`, Nutzer per `/users/lookup` gefunden); nur Owner |
| PATCH, DELETE | /tours/{id}/shares/{user_id} | Recht ändern (Owner) / entfernen (Owner oder der betroffene Nutzer selbst) |
| GET, POST | /tours/{id}/public-link | Links listen / erzeugen (nur Owner) |
| DELETE | /tours/{id}/public-link/{link_id} | Link widerrufen (nur Owner) |
| GET | /public/tours/{token} | Öffentliche Ansicht (ohne Login) |
| PUT, GET | /tours/{id}/gpx | GPX hochladen und auswerten (multipart, Feld `file`) / Original herunterladen; nur Owner |
| POST | /tours/{id}/track/drawn | Gezeichneten Track speichern, GPX erzeugen (nur Owner) |
| GET, DELETE | /tours/{id}/track | Statistik und Zeitreihen für Karte und Diagramme / Track entfernen (nur Owner) |
| GET | /public/tours/{token}/track | Track einer öffentlich verlinkten Tour |
| GET | /tours/{id}/overview | Übersicht: Kennzahlen und Wegverlauf mit Gipfeln, Pässen und Wegpunkten in Track-Reihenfolge |
| POST | /tours/{id}/track/places | Stellen am Track neu erkennen (nur Owner) |
| PUT | /tours/{id}/points | Start/Ende manuell setzen bzw. benennen (nur Owner) |
| GET, POST | /tours/{id}/photos | Fotos listen / hochladen (multipart, Feld `files`; EXIF-Auswertung, Track-Zuordnung) |
| PATCH, DELETE | /tours/{id}/photos/{photo_id} | Beschriftung, Position, Wegpunkt, Titelbild / löschen |
| GET | /tours/{id}/photos/{photo_id}/image?size= | Bild (`full`) oder Vorschaubild (`thumb`) |
| PUT | /tours/{id}/photos/time-offset | Zeitversatz für alle Fotos setzen und neu zuordnen |
| GET | /public/tours/{token}/photos/{index}?size= | Bild einer öffentlich verlinkten Tour |
| POST | /tours/{id}/waypoints/from-photos | Wegpunkte aus Foto-GPS erzeugen |
| GET, POST, PATCH, DELETE | /tours/{id}/waypoints | Wegpunkte |
| POST | /tours/{id}/weather/fetch | Wetter neu abrufen (nur Owner) |
| POST | /tours/{id}/calories/estimate | Manuellen Wert durch die Schätzung ersetzen (nur Owner) |
| GET | /tours/{id}/export | JSON-Export |
| GET, POST | /contacts | Partner-Kontakte listen / anlegen |
| PATCH, DELETE | /contacts/{id} | Umbenennen, mit Nutzer verknüpfen (`linked_user_id`, `null` löst) / löschen |
| GET | /sync/changes?since=, POST /sync/push | Offline-Sync |
| GET | /maps/tiles/{z}/{x}/{y}.png | Kartenkachel aus dem Speicher des Servers; ohne Anmeldung (öffentliche Linkseiten), Rate-Limit 1500/Minute je Client |
| GET | /gear/meta | Währung, erlaubte Bildformate, Upload-Grenze, Zusatzfelder je Art |
| PUT/DELETE | /gear/items/{id}/favorite | Favorit setzen bzw. entfernen (setzt den Tag „Favorit“) |
| GET | /maps/info | Kachel-Adresse, höchste Zoomstufe, Quellenangabe, Prüfintervall |

### Ausrüstung
| Methode | Pfad | Zweck |
|---|---|---|
| GET, POST | /gear/items | Liste (`q`, `type_id`, `status`, `tag_id` mehrfach, `limit`, `offset`) / Anlegen (optional mit `catalog_id` als Vorlage) |
| GET | /gear/summary?group_by= | Summen (Anzahl, Gewicht, Kaufwert), optional gruppiert nach `type`, `tag`, `status`, `brand`; Filter wie Liste |
| GET, POST | /gear/tags | Eigene Tags / anlegen |
| PUT, DELETE | /gear/tags/{id} | Tag ändern / löschen |
| GET, PUT, DELETE | /gear/items/{id} | CRUD |
| POST, GET, DELETE | /gear/items/{id}/image | Bild hochladen (multipart, Feld `file`) / abrufen / entfernen |
| GET | /gear/catalog?q= | Freigegebene Katalogeinträge durchsuchen |
| GET | /gear/catalog/{id}/image | Bild eines Katalogeintrags |
| POST | /gear/items/{id}/propose-to-catalog | Katalogvorschlag |
| GET | /gear/catalog/mine | Eigene Vorschläge mit Status (`pending`, `approved`, `rejected`) |
| GET | /gear/catalog/pending | Offene Vorschläge (admin) |
| PATCH | /gear/catalog/{id} | Freigeben, ablehnen, Produktdaten korrigieren (admin) |
| GET, POST | /gear/types | Kategorien (Standard + eigene) / anlegen |
| PUT, DELETE | /gear/types/{id} | Kategorie ändern / löschen |
| GET, POST | /gear/lists | Packlisten (mit Gesamtgewicht) / anlegen |
| GET, PUT, DELETE | /gear/lists/{id} | Packliste lesen / ersetzen / löschen |

Listen mit Paging antworten mit `{items, total, limit, offset}`. Beim Anlegen darf der Client die `id` (UUID) mitgeben.

### Ernährung
| Methode | Pfad | Zweck |
|---|---|---|
| GET | /nutrition/barcode/{ean} | Produkt per Barcode |
| GET | /nutrition/search?q= | Produktsuche (privat + Katalog; Name, Marke oder exakter Barcode) |
| GET, POST | /nutrition/foods | Eigene Lebensmittel / anlegen (optional mit `catalog_id` als private Kopie eines Katalogprodukts) |
| GET | /nutrition/foods/{id} | Eigenes Lebensmittel, eigener Vorschlag oder Katalogeintrag |
| PUT, DELETE | /nutrition/foods/{id} | Eigenes Lebensmittel ändern / löschen (Soft Delete) |
| POST | /nutrition/foods/{id}/propose-to-catalog | Katalogvorschlag |
| GET | /nutrition/catalog/mine | Eigene Vorschläge mit Status |
| GET | /nutrition/catalog/pending | Offene Vorschläge (admin) |
| PATCH | /nutrition/catalog/{id} | Freigeben, ablehnen, Daten korrigieren (admin) |

`PUT /tours/{id}` ersetzt das Tourdokument samt den Listen `gear`, `food` und `peaks`; Einträge werden über ihre `id` wiedererkannt, fehlende Einträge entfernt. Wegpunkte haben eigene Endpunkte (`PATCH`/`DELETE` unter `/tours/{id}/waypoints/{waypoint_id}`). Jede Änderung erhöht `tour.version`.

Berechtigungen werden zentral in einer Dependency geprüft, nicht in jedem Endpunkt (`protocols/sharing.py`: `ReadableTour`, `EditableTour`, `OwnedTour`). Ohne Zugriff antwortet die API mit 404, bei zu geringem Recht mit 403. Die Admin-Rolle gibt keinen Zugriff auf fremde Touren.

## 9. UI-Grundlage

- Material 3, helles und dunkles Theme, Design-Tokens zentral in `core/theme`.
- Farbidee: Tannengrün, Fels-Grau, Schnee-Weiß, Akzent Orange.
- Navigation: untere Leiste mit aktiven Modulen (Touren | Ausrüstung | Essen | später Planung, Berichte); auf großen Bildschirmen (Tablets) Navigation Rail.
- Responsiv von Beginn an, Deutsch zuerst, Texte über ARB-Dateien.
- Diese Grundlage gilt für die Android-App und, sinngemäß mit denselben Farben, Begriffen und Abläufen, für das Web-Frontend (Abschnitt 9a).

### Tourdetail (orientiert an wanderer)
wanderer (open-wanderer/wanderer, AGPLv3) dient als **UX-Vorbild, nicht als Code- oder Asset-Quelle**. Aus der Dokumentation entnommen: Fotos hängen an der Tour und erscheinen in der Detailansicht, eines ist als Vorschaubild wählbar, Wegpunkte haben Name, Beschreibung, Icon und Fotos, und „Aus Fotos“ erzeugt Wegpunkte aus GPS-Daten der Bilder. Wie genau Karte und Höhenprofil die Fotos zeigen, steht dort nicht; das Verhalten bitte am Demo-System (demo.wanderer.to) ansehen und hier festhalten, bevor die Detailansicht gebaut wird.

Geplantes Verhalten (unsere Umsetzung):
- **Karte**: Track als Linie, Start-/Ende-/Gipfel-Marker, Foto-Marker als kleine runde Vorschaubilder an der Fotoposition, bei Zoom-Out zu Gruppen zusammengefasst; Wegpunkt-Marker mit Icon.
- **Höhenprofil** (mit optional Herzfrequenz-Kurve): Foto-Marker an der Stelle `track_distance_m`; Wischen/Hover über das Profil bewegt einen Punkt auf der Karte und umgekehrt. Das Profil ist ein Flächendiagramm mit beschrifteten Achsen (Höhe in runden Schritten, Strecke in km) und Gitterlinien. An der gewählten Stelle zeigt es eine Linie, einen Punkt auf der Kurve und ein Infofeld mit Strecke, Höhe und Steigung (über rund 100 m gemittelt), im Web zusätzlich Uhrzeit und Herzfrequenz. Auf der Karte ist die Stelle deutlich hervorgehoben (roter Punkt mit Hof), sodass sich die Route „ablaufen“ lässt. Im Web wird außerdem der bis dorthin zurückgelegte Teil des Tracks eingefärbt, die Karte folgt, wenn die Stelle außerhalb des Ausschnitts liegt, und das Profil lässt sich auch mit den Pfeiltasten bedienen. Entschieden am 04.10.2026; die Darstellung ist an wanderer angelehnt, aber selbst gezeichnet (im Web SVG, in der App `CustomPainter`), ohne Diagramm-Bibliothek.
- **Foto-Ansicht**: Tippen auf einen Marker öffnet eine Vollbild-Galerie (Wischen zwischen Fotos, Beschriftung, Aufnahmezeit, Höhe); Sprung zur Position auf Karte/Profil. Reihenfolge der Galerie = Verlauf entlang des Tracks.
- **Fotoleiste** unter der Karte (horizontal scrollbar); Titelbild wählbar, erscheint in der Liste.
- **Position korrigieren**: Foto auf Karte oder Profil verschieben; Zeitversatz für alle Fotos einer Tour einstellbar.
- Weitere Abschnitte: Eckdaten, Track-Statistik, Ausrüstung mit Gewichtssumme, Essen mit Kalorien (gegessen/verbraucht, „geschätzt“ markiert), Wetter (Start/Gipfel/Ende), Partner, Fazit, Historie, Teilen.

### Weitere Screens
- Liste: Karten mit Titel, Datum, Gipfel, Titelfoto; Tabs „Meine“ / „Mit mir geteilt“.
- Editor: Formular in Abschnitten, Speichern als Entwurf; Track-Zeichenmodus; Start/Ende per Tippen auf der Karte.
- Ausrüstung: Liste mit Bild, Filter und Suche, Katalogsuche beim Anlegen.
- Essen: Scan-Button öffnet Kamera; Trefferkarte mit Nährwerten und Mengeneingabe.

## 9a. Web-Frontend (Flask)

Das Web-Frontend ist ein eigenes Projekt in `web/` und ersetzt die früher geplante Web-Version der Flutter-App.

- **Aufbau**: Flask-Anwendung mit Jinja2-Vorlagen, je Modul ein Blueprint (`auth`, `gear`, `nutrition`, `protocols`). Angezeigt werden nur Module, die die API unter `/modules` meldet.
- **Daten**: ausschließlich über die REST-API (`API_BASE_URL`, im Compose-Netz direkt zum `api`-Dienst). Kein eigener Datenbestand, keine eigene Fachlogik: Rechte, Historie, Konfliktschutz und Schätzungen kommen von der API.
- **Anmeldung**: Das Frontend meldet den Nutzer an der API an und hält Access- und Refresh-Token serverseitig in der Sitzung; der Browser bekommt nur ein Sitzungs-Cookie (`HttpOnly`, `Secure`, `SameSite=Lax`). Formulare sind gegen CSRF geschützt. Abgelaufene Access-Tokens werden wie in der App einmal erneuert.
- **Konflikte**: Formulare schicken die `version` mit; bei 409 zeigt die Seite den neuen Stand und die eigenen Eingaben nebeneinander.
- **Karte und Höhenprofil**: MapLibre GL JS, als statische Datei vom eigenen Server ausgeliefert (kein CDN); Verhalten wie in Abschnitt 9 beschrieben.
- **Öffentliche Links**: Die Seite `/p/<token>` gehört zum Web-Frontend. Sie braucht keine Anmeldung, liest `/public/tours/<token>` der API und setzt `noindex`.
- **Bilder und Dateien**: Das Frontend reicht sie von der API durch (mit dem Token des Nutzers); Uploads gehen den umgekehrten Weg.
- **Barcode**: Eingabe von Hand; der Kamera-Scanner bleibt der Android-App vorbehalten.
- **Kein Offline-Betrieb**: Das Web-Frontend braucht eine Verbindung zum Server.
- **Sprache**: Deutsch; die Texte liegen in einer Übersetzungsdatei, nicht in den Vorlagen verstreut.
- **Betrieb**: eigener Dienst `web` im Compose-Stack, nur auf `127.0.0.1:<Port>`. Der Reverse Proxy leitet `/api/` an die API und alles andere an das Web-Frontend. Die Regel „Tokens öffentlicher Links nie in Logs“ gilt auch hier und im Proxy.
- **Tests**: pytest mit dem Flask-Testclient; die API wird in den Tests durch eine Attrappe ersetzt.

**Umsetzung (Schritt 13)**

- Projekt `web/`, Paket `hiker_web`, Blueprints `auth`, `gear` (`/gear`), `nutrition` (`/food`), `protocols` (`/tours`) und `public` (`/p`). Start im Container mit gunicorn (`hiker_web.wsgi:app`), Port nur auf `127.0.0.1:${WEB_PORT}`.
- **Sitzungen**: je Sitzung eine JSON-Datei in `WEB_SESSION_DIR` (Rechte 600) mit Tokens, Nutzer und aktiven Modulen; das Cookie enthält nur die zufällige Sitzungs-ID und das CSRF-Token. Ungenutzte Sitzungen werden nach `WEB_SESSION_DAYS` gelöscht. Weil ein Refresh-Token nur einmal gilt und eine Seite ihre Bilder parallel lädt, erneuert je Sitzung nur eine Anfrage die Tokens (Dateisperre); die anderen übernehmen das Ergebnis.
- **Konflikte**: Das Bearbeiten-Formular schickt neben der `version` die Werte mit, mit denen es geladen wurde. Bei 409 führt das Frontend feldweise zusammen: unveränderte Felder übernehmen den neuen Stand, eigene Änderungen bleiben eingetragen; als Abweichung angezeigt werden nur Felder, die beide Seiten geändert haben. Bei den Listen gilt der neue Stand, eigene Änderungen an vorhandenen Zeilen sind eingetragen. Gespeichert wird erst nach erneutem Absenden, dann auf Basis der neuen Version.
- **Rechte**: Die Oberfläche blendet aus, was die API ohnehin ablehnt (Track, Freigaben, Löschen nur für den Besitzer; Zeiten und Zahlenwerte bei `edit` als unveränderte versteckte Felder). Entscheidend bleibt die Prüfung der API.
- **Karte**: MapLibre GL JS 5.24.0 in der CSP-Variante unter `static/vendor/maplibre-gl/`; Kacheln standardmäßig vom eigenen Server: `/tiles/{z}/{x}/{y}.png` reicht die Kacheln des Moduls `maps` durch (`MAP_TILE_URL` leer); eine fremde Quelle lässt sich weiterhin eintragen. Höhenprofil als SVG ohne weitere Bibliothek, mit der Karte gekoppelt (Position unter dem Zeiger, Foto-Marker).
- **Sicherheits-Header**: `Content-Security-Policy` (Skripte und Stile nur vom eigenen Server, Kacheln nur von der Kachelquelle), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin` – auch auf der öffentlichen Seite: fremde Server erfahren nur die Herkunft, nie den Pfad mit dem Token. `no-referrer` scheidet aus, weil der Kachelserver von OpenStreetMap Anfragen ohne Referer blockiert.
- **Öffentliche Seite**: `/p/<token>`, `/p/<token>/track.json`, `/p/<token>/photos/<index>`; Token mit falscher Form erreichen die API nicht. gunicorn schreibt kein Zugriffs-Log.
- **Auf der Karte bearbeiten** (`/tours/<id>/map`, ergänzt am 04.10.2026): Wegpunkte von Hand, Fotoposition korrigieren oder wieder automatisch setzen, Start und Ende, Track zeichnen, Wetter für einen eigenen Punkt. Jede Position lässt sich eintippen oder per Klick in die Karte übernehmen; ohne JavaScript bleibt das Eintippen. Wegpunkte und Fotos stehen auch mit `edit` offen, der Rest nur dem Besitzer.
- **Packlisten** (`/gear/lists`): anlegen, bearbeiten, löschen. Beim Bearbeiten einer Tour lässt sich eine Liste komplett übernehmen; Gegenstände, die schon in der Tour sind, kommen nicht doppelt hinzu.
- Zeiten lassen sich nur mit JavaScript bearbeiten (Umrechnung der Ortszeit im Browser); alles andere funktioniert auch ohne.

## 9b. Planung (Modul `planning`, Phase 2)

Entschieden am 04.10.2026: Phase 2 beginnt mit der Routenplanung; Kartenstile und Ebenen folgen danach.

**Abhängigkeiten**: `planning` hängt von `auth` und `protocols` ab und nutzt von `protocols` nur die Track-Auswertung (`track.py`: Punkte, Eckdaten, Reihen, GPX) und den Höhen-Adapter (`elevation.py`) sowie später dessen Service zum Anlegen einer Tour. `protocols` kennt `planning` nicht; eine Tour merkt sich höchstens die ID der Route.

**Wegführung**: hinter dem Adapter `RoutingEngine` (`planning/routing.py`).
- **BRouter** (MIT-Lizenz), selbst gehostet als eigener Container; die API erreicht ihn über `BROUTER_URL`. Die Wegpunkte gehen nur an den eigenen Server, nie an einen fremden Dienst. BRouter rechnet auf OSM-Wegdaten (ODbL, Quelle wird genannt), die je Region als Dateien unter `DATA_DIR` liegen, und liefert die Höhen mit.
- **Luftlinie** (`direct`): gerade Verbindung, immer verfügbar; für wegloses Gelände, Skitouren und als Rückfall, wenn BRouter nicht eingerichtet ist. Die Höhen kommen dann vom Höhen-Adapter (Open-Meteo).
- Jeder Wegpunkt kann festlegen, dass der Abschnitt zu ihm hin als Luftlinie verläuft (`direct`), auch wenn der Rest dem Wegenetz folgt.
- Profile: `hiking` (Wandern, BRouter-Profil einstellbar über `BROUTER_PROFILE_HIKING`) und `direct`; weitere (Rad, Skitour) später. Das Profil gilt für alle Abschnitte; einzelne Abschnitte lassen sich davon abweichend als Luftlinie festlegen.
- **Schwierigkeit** (Vorgabe vom 04.10.2026): Für die Wegführung wird die höchste erlaubte Stufe der SAC-Wanderskala gewählt (`max_difficulty` 1–6 = T1 Wanderung, T2 anspruchsvolle Bergwanderung, T3 Bergtour, T4 schwere Bergtour, T5 sehr schwere Bergtour, T6 äußerst schwierige Bergtour; Standard T3). Leichtere Stufen sind eingeschlossen, schwerere Wege werden nicht benutzt; wo möglich bevorzugt die Wegführung anspruchsvolle Wege bis zur gewählten Stufe. **Klettersteige** sind eine eigene Kategorie (`via_ferrata`) und werden nur benutzt, wenn sie zusätzlich angekreuzt sind. Grundlage sind die OSM-Angaben `sac_scale` und `highway=via_ferrata`; Wege ohne Angabe gelten als T1. Umgesetzt ist das im eigenen BRouter-Profil `deploy/brouter/profiles/hiker-hiking.brf` (abgeleitet von BRouters `hiking-mountain`, MIT): Die API übergibt je Anfrage die Grenze (`SAC_scale_limit`), dieselbe Stufe als bevorzugte (`SAC_scale_preferred`) und `allow_via_ferrata`. Gibt es bis zur gewählten Stufe keinen Weg, antwortet die API mit `no_route`, statt einen schwereren Weg zu nehmen.
- **Betrieb**: BRouter 1.7.10 als Dienst `brouter` im Compose-Profil `routing`, ohne Port nach außen, nicht als root, mit schreibgeschütztem Dateisystem. Die Wegdaten (Kacheln von 5° × 5°, je 100–300 MB, wöchentlich von brouter.de neu erzeugt) holt `deploy/brouter-segments.sh` nach `DATA_DIR/brouter/segments`; Standard ist der Alpenraum (E5_N45, E10_N45, E15_N45, E5_N40, E10_N40). Punkte außerhalb der geladenen Kacheln ergeben `no_route`.
- Fehler: kein Weg gefunden → 422 `no_route`; BRouter nicht erreichbar oder nicht eingerichtet → 502 `routing_unavailable`.

**Datenmodell** `planned_route`: id, owner_id, title, description, planned_date, profile, max_difficulty, via_ferrata, waypoints (JSON: `lat`, `lon`, `name`, `direct`), series (JSON wie bei Tracks: `distance_m`, `lat`, `lon`, `elevation_m`), engine, distance_m, ascent_m, descent_m, min_elevation_m, max_elevation_m, duration_s (geschätzt), version, created_at, updated_at, deleted_at. Der Server berechnet Linie und Eckdaten beim Speichern selbst aus den Wegpunkten; der Client schickt keine Geometrie. Konfliktschutz über `version` wie bei Touren (409).

**Gehzeit** (immer als `estimated` gekennzeichnet), nach DIN 33466: waagrecht 4 km/h, Aufstieg 300 Hm/h, Abstieg 500 Hm/h. Aus der Zeit für die Strecke und der Zeit für die Höhenmeter zählt der größere Wert ganz, der kleinere zur Hälfte. Pausen sind nicht enthalten. Ohne Höhen zählt nur die Strecke.

**Rechte**: Routen gehören ihrem Owner; fremde Routen antworten mit 404. Teilen von Routen ist nicht vorgesehen, bis es gewünscht wird.

**API** (`/api/v1/planning`):
- `GET /planning/info` – verfügbare Profile, Schwierigkeitsstufen, ob die Wegführung eingerichtet ist, Quellenangabe
- `POST /planning/preview` – Wegpunkte und Profil → Linie, Eckdaten, Gehzeit (nichts wird gespeichert)
- `GET /planning/routes`, `POST /planning/routes`, `GET|PUT|DELETE /planning/routes/{id}`
- `GET /planning/routes/{id}/gpx` – Route als GPX-Datei (Track)
- `GET /planning/segments`, `GET /planning/segments/{name}` – Wegdaten für das Planen ohne Netz in der App

**Planer im Web-Frontend** (`/routes`, Blueprint `planning`, `static/plan.js`): Ein Klick auf die Karte setzt den nächsten Wegpunkt, Punkte lassen sich verschieben, benennen, entfernen; die Richtung lässt sich umkehren. Über der Karte stehen die Verbindung (den Wegen folgen oder Luftlinie, für alle Abschnitte), die Schwierigkeit (T1–T6) und „Klettersteige benutzen“; in der Liste der Wegpunkte lässt sich je Abschnitt „Luftlinie hierher“ ankreuzen. Nach jeder Änderung fragt die Seite `POST /routes/preview` (reicht an `/planning/preview` weiter, mit CSRF-Token) und zeigt Linie, Strecke, Auf- und Abstieg, geschätzte Gehzeit und das Höhenprofil, das wie bei Touren mit der Karte verknüpft ist (`static/profile.js`, von beiden Seiten genutzt). Gespeichert wird über ein normales Formular; die Wegpunkte stehen als JSON in einem versteckten Feld. Der Planer braucht JavaScript; Liste, Löschen und GPX-Download nicht.

**Planer in der App** (`features/planning`): Liste der Routen und derselbe Planer wie im Web. Ein Tipp auf die Karte setzt den nächsten Punkt; ein Tipp auf einen Punkt wählt ihn, der nächste Tipp auf die Karte versetzt ihn. Über das Menü eines Wegpunkts: benennen, versetzen, „Luftlinie hierher“, entfernen. Verbindung (den Wegen folgen oder Luftlinie), Schwierigkeit und Klettersteige stehen unter der Karte; nach jeder Änderung holt die App Linie, Eckdaten und Höhenprofil vom Server.

**Planen ohne Netz in der App** (entschieden am 04.10.2026: Die Tourenplanung soll in der App offline gehen):
- **Wegführung auf dem Gerät**: Der Routing-Kern von BRouter (`brouter-1.7.10-ro.jar`, 345 KB, MIT) ist in die Android-App eingebunden (`android/app/libs`, Aufruf über den Kanal `hiker/routing` in `MainActivity.kt`). Er rechnet mit demselben Profil `hiker-hiking.brf` und denselben Parametern wie der Server; die App trägt eine Kopie des Profils (`assets/brouter/`), ein Test prüft, dass sie mit `deploy/brouter/profiles/` übereinstimmt.
- **Wegdaten**: Die App lädt die Kacheln (5° × 5°, je 100–300 MB) vom eigenen Server, nicht von brouter.de: `GET /planning/segments` (Liste) und `GET /planning/segments/{name}` (Datei, mit Anmeldung, Range-Anfragen möglich). Der Server liefert, was unter `DATA_DIR/brouter/segments` liegt (`BROUTER_SEGMENTS_PATH`). In der App unter Planung → „Offline-Wegdaten“: laden, neu laden, entfernen.
- **Ablauf**: Die App fragt immer zuerst den Server. Ist er nicht erreichbar, berechnet sie Linie, Eckdaten und Gehzeit selbst (`offline_routing.dart`, dieselbe Rechnung wie `planning/service.py`). Fehlen die Wegdaten für das Gebiet eines Wegpunkts, sagt sie das (`offline_no_data`); Luftlinien gehen immer.
- **Grenzen**: Luftlinien haben ohne Netz keine Höhen (der Höhen-Adapter braucht den Server); Auf- und Abstieg zählen dann nur die Abschnitte entlang von Wegen. Die Karte zeigt ohne Netz nur Ausschnitte, die vorher schon angesehen wurden; Kartenkacheln werden nicht auf Vorrat geladen (Nutzungsbedingungen von OpenStreetMap). Bei einem von Hand bestätigten Zertifikat hebt der `TileProxy` der App jede ausgelieferte Kachel als Datei auf (Cache-Ordner der App, höchstens 300 MB, zuletzt Benutztes bleibt), liefert sie sieben Tage lang ohne Nachfrage und ohne Netz auch danach; sonst übernimmt das der Zwischenspeicher der Kartenbibliothek. Karten zum Mitnehmen sind erst mit der eigenen Karte aus OSM-Daten möglich (Schritt 8).
- **Abgleich** (Sammlung `routes`): Eine ohne Netz gespeicherte Route liegt mit ihrer auf dem Gerät berechneten Linie auf dem Gerät und wartet auf den Abgleich. Der Server ist maßgeblich und berechnet die Linie dabei neu. Findet er keinen Weg, bleibt die Route mit einer verständlichen Meldung in der Liste der wartenden Änderungen. Ändert sich offline der Verlauf einer gespeicherten Route, ersetzt die auf dem Gerät berechnete Linie die alte; bleibt der Verlauf gleich (nur Titel, Beschreibung, Datum), bleibt die Linie des Servers. Konflikte (auf dem Server inzwischen geändert) entscheidet der Nutzer: eigene Fassung behalten oder die des Servers nehmen.
- **GPX**: Die App schreibt die angezeigte Linie selbst als GPX-Datei (Menü des Planers), auch ohne Netz.

**Karte beim Planen** (Vorgaben vom 04.10.2026):
- Grundlage ist OpenStreetMap.
- **Darstellung wählbar**: Stile Sommer, Winter, Satellit und eine topografische Karte; Ebenen Hangneigung, Wetter, Schnee, Lawinenlage (Schritte 6 und 7).
- **Gewünschte Karten von Bergfex, Kompass, Outdooractive und Alpenverein**: Das sind kommerzielle Karten. Ihre Kacheln dürfen nur mit einem Vertrag oder Schlüssel des jeweiligen Anbieters eingebunden werden; ohne diesen bindet hiker sie nicht ein. Die Layer-Provider-Schnittstelle sieht deshalb Quellen vor, die der Betreiber mit eigener Adresse und eigenem Schlüssel in der Konfiguration einträgt. Welche dieser Anbieter eine solche Nutzung überhaupt anbieten und zu welchen Bedingungen, wird in Schritt 6 je Anbieter geklärt und hier festgehalten. **Entschieden am 04.10.2026: Diese externen Anbieter bleiben vorerst weg**; Schritt 6 beschränkt sich auf freie Quellen. Als freie topografische Karten kommen OpenTopoMap sowie swisstopo, basemap.at und die Karten der Bayerischen Vermessungsverwaltung in Frage.
- **2D und 3D** umschaltbar: Geländedarstellung mit MapLibre (Höhenkacheln aus offenen Daten, vom eigenen Server zwischengespeichert), Schritt 6.
- **Schnelle Karte**: Verschieben und Drehen müssen flüssig sein. Dafür bleibt es bei MapLibre (GPU-Darstellung) in Web und App; Drehen wird in der App freigegeben; die eigene Karte aus OSM-Daten (Schritt 8) liefert Vektorkacheln, die schneller und in jeder Drehung scharf sind. Kacheln kommen weiterhin vom eigenen Server mit langer Cache-Dauer.

**Eigene Karte aus OSM-Rohdaten** (Schritt 8, vorgezogen am 04.10.2026, damit die App Karten mitnehmen kann):
- **Warum**: Kacheln der OpenStreetMap-Server dürfen nicht auf Vorrat geladen werden. Eine Karte, die der eigene Server aus den Rohdaten (ODbL) baut, darf als Ganzes heruntergeladen werden.
- **Bau**: `deploy/build-map.sh <gebiet>` startet Planetiler 0.10.2 (Apache-2.0, Compose-Dienst `mapbuild`, Profil `mapbuild`, läuft nur auf Zuruf, nicht als root) und schreibt `DATA_DIR/maps/<gebiet>.mbtiles`: Vektorkacheln im OpenMapTiles-Schema, Zoom 0–14. Gebietsnamen wie bei Geofabrik (`switzerland`, `austria`, `alps` …). Gemessen: Schweiz 349 MB in gut 5 Minuten bei 3 GB RAM. Die Hilfsdaten (Küstenlinien, Natural Earth, rund 1,5 GB) bleiben unter `maps/build/sources`.
- **Ausliefern** (Modul `maps`, `maps/vector.py`): `GET /maps/vector/{z}/{x}/{y}.pbf` (ohne Anmeldung; 204, wo die Karte nichts hat), `GET /maps/style.json`, `GET /maps/fonts/{fontstack}/{range}.pbf`, `GET /maps/regions` und `GET /maps/regions/{name}` (mit Anmeldung, Download der Datei, Range-Anfragen). Mehrere Gebietsdateien ergänzen sich: die größte antwortet zuerst. `GET /maps/info` nennt `style_url`, sobald eine Karte vorhanden ist; ohne Karte bleiben die zwischengespeicherten Rasterkacheln.
- **Stil** (`maps/style.py`): eigene Wanderkarte, ohne Symbolbilder: Wege rot gestrichelt und hervorgehoben, Fahrwege braun, Wald/Fels/Eis/Wiese unterschieden, Gipfel mit Name und Höhe, Hütten, Gewässer, Orte. Schrift: Noto Sans (OFL), Glyphen für lateinische Schrift liegen im Modul. Farben nie achtstellig hexadezimal und Namen über `to-string(coalesce(…))`, weil die Kartenbibliothek der App sonst nichts zeichnet.
- **Web**: Die Seiten benutzen die Vektorkarte, sobald die API eine hat (`hiker_web/maps.py`); Stil, Kacheln und Schriften reicht das Web-Frontend unter `/map/…` durch.
- **App**: Der Kartenserver in der App (`TileProxy`, auf 127.0.0.1) beantwortet alles, was die Karte braucht: zuerst aus einer Kartendatei auf dem Gerät (`core/map/map_regions.dart`), sonst vom eigenen Server; was vom Server kam, bleibt als Datei (höchstens 300 MB). Unter Planung → „Offline-Daten“ lädt man Kartengebiete und Wegdaten. Die Karte lässt sich drehen.
- **Noch offen**: Höhenlinien und Schummerung fehlen (Schritte 6 und 7, zusammen mit 2D/3D). Die Schwierigkeit der Wege (`sac_scale`) steht nicht im OpenMapTiles-Schema; dafür braucht der Bau eine eigene Ebene. Auf dem Emulator zeichnet die App die Beschriftungen der Vektorkarte nicht, obwohl Stil und Schriften richtig ankommen (auch ein fester Testtext fehlt); im Web sind sie da. Das muss auf einem echten Gerät geprüft werden.

**Kartenebenen** (Schritte 6 und 7, erster Teil umgesetzt am 04.10.2026):
- **Layer-Provider-Schnittstelle** (`maps/layers.py`): Jede Ebene, die nicht aus der eigenen Vektorkarte kommt, ist dort mit Adresse, Quellenangabe und Lizenz beschrieben. Die Kacheln holt immer der eigene Server und speichert sie wie die OSM-Kacheln (`TILE_CACHE_PATH/_layers/<ebene>`); Clients sprechen nie selbst mit einer Quelle. Kommerzielle Anbieter stehen bewusst nicht in der Liste.
- **Höhendaten** (`terrain`): Mapzen Terrain Tiles auf AWS Open Data (Terrarium-Kodierung; offene Daten, Quellen sind zu nennen), abschaltbar über `TERRAIN_ENABLED`. Daraus entstehen die **Schummerung** der Karte, das **3D-Gelände** und die Hangneigung.
- **Hangneigung** (`slope`): berechnet der Server selbst aus den Höhenkacheln (`GET /maps/slope/{z}/{x}/{y}.png`, Zoom 9–14) und speichert das Ergebnis. Eingefärbt wie auf Lawinenkarten: gelb ab 30°, orange ab 35°, rot ab 40°, violett ab 45°; flacheres Gelände bleibt durchsichtig. Die Genauigkeit folgt den Höhendaten (im Alpenraum rund 30 m Raster): Die Ebene zeigt die Größenordnung, ersetzt aber keine Beurteilung im Gelände.
- **Luftbild** (`satellite`): je Kachel die erste Quelle, die das Gebiet abdeckt und ein Bild hat: swisstopo SWISSIMAGE (Schweiz, offene Behördendaten), basemap.at Orthofoto (Österreich, CC BY 4.0), sonst Sentinel-2 cloudless 2016 von EOX (weltweit, CC BY 4.0, 10 m Auflösung). Abschaltbar über `SATELLITE_ENABLED`. Das Luftbild ersetzt nur den gezeichneten Untergrund; Wege, Gewässerlinien und Namen bleiben darüber.
- **Auswahl**: Der Kartenstil des Servers trägt in `metadata.hiker`, was sich umschalten lässt (Grundkarten mit `show`/`hide`, Überlagerungen mit ihren Ebenen und der Legende, die Quelle für 3D). Web (`static/map_layers.js`, Knopf „Ebenen“ auf der Karte) und App (Knopf auf der Karte, `MapLayerSheet`) bieten deshalb dasselbe an und merken sich die Wahl.
- **2D/3D**: im Web über die Ebenen-Auswahl („3D-Gelände“: Karte wird nach den Höhendaten angehoben und geneigt). Die Kartenbibliothek der App (MapLibre Native) kann noch kein 3D-Gelände; dort gibt es Schummerung, Drehen und Neigen, aber kein angehobenes Gelände.
- **Offline**: Höhendaten, Hangneigung und Luftbild hebt die App nur für angesehene Ausschnitte auf; als Gebietspaket gibt es bisher nur die Vektorkarte.
- **Höhenlinien** (`maps/contours.py`): Der Server zeichnet sie selbst aus den Höhenkacheln (Marching Squares) und liefert sie als Vektorkacheln (`GET /maps/contours/{z}/{x}/{y}.pbf`, Zoom 9–13, Ebene `contour` mit `ele` und `index`); das Format schreibt er ohne weitere Abhängigkeit. Abstand der Linien: 200 m bis Zoom 10, 100 m bei 11, 50 m bei 12, 20 m ab 13; jede fünfte ist stärker und beschriftet. Eine Kachel braucht rund 0,1 s und wird gespeichert.
- **Winter**: als Grundkarte wählbar. Ein weißer Schleier liegt über dem gezeichneten Land, darüber die Schummerung; Gewässer, Wege, Höhenlinien und Namen bleiben. Pisten und Skirouten stehen nicht im Kartenschema und fehlen deshalb.
- **Lawinengefahr** (`maps/avalanche.py`, `GET /maps/avalanche.geojson`): höchste Gefahrenstufe des Tages (1–5) je Warnregion in den Farben der europäischen Skala, für Schweiz, Liechtenstein, Österreich, Bayern, Norditalien und Slowenien. Die Stufen aller europäischen Warndienste (EAWS) kommen als eine Datei je Tag von avalanche.report (CC BY 4.0), die Umrisse der Regionen von regions.avalanches.org (CC0); der Server fügt beides zusammen, vereinfacht die Umrisse auf rund 150 m und hält die Stufen 30 Minuten, die Umrisse 30 Tage. Regionen ohne Bulletin am Tag fehlen; außerhalb der Saison ist die Ebene leer. Sie ist eine Übersicht: maßgeblich ist das Bulletin des Warndienstes, darauf weisen Web und App hin. Die Nutzungsbedingungen der einzelnen Warndienste hinter der Sammeldatei sind nicht einzeln geprüft. Abschaltbar über `AVALANCHE_ENABLED`.
- **Schneebedeckung und Niederschlag** (`snow`, `precipitation`): Satellitenprodukte über den offenen Kacheldienst GIBS der NASA (frei nutzbar, Quellenangabe erbeten): MODIS/Terra-Schneebedeckung des Vortags (bis Zoom 8, rund 500 m; Wolken verdecken den Boden) und GPM-IMERG-Niederschlag (bis Zoom 6, einige Stunden alt). Beides ist grob und zeigt die Lage im Großen, keine Schneehöhen und kein Regenradar. Abschaltbar über `WEATHER_LAYERS_ENABLED`.
- **Noch offen**: Wettervorhersage und Schneehöhen in der Karte (bisher nur die Satellitenprodukte), Pisten und Skirouten, die Schwierigkeit der Wege in der Karte, Höhendaten und Ebenen als Gebietspaket für die App.

**Regionen** (entschieden am 04.10.2026): Schweiz, Österreich, Deutschland (Alpen/Bayern), Italien und der übrige Alpenraum. Daraus folgt für die Schritte 6 und 7: länderspezifische Quellen, wo sie frei sind (swisstopo, basemap.at, Bayerische Vermessungsverwaltung), sonst weltweite (OpenStreetMap, OpenTopoMap, Sentinel-2); jede Quelle nur über die Layer-Provider-Schnittstelle und mit dokumentierter Lizenz. Die Wegdaten für BRouter decken diese Länder ab.

## 10. Sicherheit und Datenschutz

- Passwörter mit argon2, JWT kurzlebig + Refresh-Token. Passwortregeln nach BSI, zweiter Faktor (TOTP) Pflicht, optional SSO über OIDC (siehe Entscheidungen in Abschnitt 2).
- **Unvollständige Anmeldung**: Access-Tokens tragen, wie angemeldet wurde (`pwd`, `mfa`, `sso`). Solange der zweite Faktor fehlt oder ein neues Passwort fällig ist, antwortet die API auf alles außer den Endpunkten dafür mit 403 (`mfa_setup_required` bzw. `password_change_required`); die Prüfung sitzt in der zentralen Dependency `CurrentUser`.
- TOTP-Codes gelten einmal (Zähler des letzten Codes wird gespeichert), Wiederherstellungscodes liegen nur als Hash vor. Ein neues Passwort und ein zurückgesetzter Faktor beenden alle Sitzungen.
- OIDC: Der Server tauscht den Code selbst ein (Client-Secret bleibt auf dem Server), prüft Aussteller, Empfänger, Ablauf und Nonce des ID-Tokens und verlässt sich für dessen Echtheit auf die TLS-Verbindung zum Token-Endpunkt. `state` gilt einmal und zehn Minuten; das Web-Frontend bindet ihn zusätzlich an den Browser.
- Rate-Limit auf Login, Public Links und Barcode-Lookup; HTTPS Pflicht. Umsetzung: je Client-Adresse und Minute 20 Anfragen an Registrierung/Login/Refresh, 60 an Barcode-Lookup und öffentliche Ansicht; darüber 429 mit `Retry-After`. Die Client-Adresse kommt aus den Proxy-Headern. Abschaltbar über `RATE_LIMIT_ENABLED=false`.
- Public-Link-Tokens: kryptografisch zufällig, widerrufbar, optional befristet, nie in Logs.
- Fotos: EXIF-GPS bei öffentlichen Links optional entfernen; Uploads auf Typ und Größe prüfen, Bilder serverseitig neu kodieren.
- Dateizugriff nur mit Berechtigungsprüfung oder kurzlebigen signierten URLs.
- Gesundheitsdaten (Herzfrequenz, Profil) sind sensibel: nur für Owner sichtbar, in Freigaben und Public Links standardmäßig ausgeblendet bzw. abschaltbar.
- Admin-Rolle für Katalogmoderation und Nutzerverwaltung; der erste registrierte Nutzer wird Admin.
- Historie enthält Autoren; beim Entfernen eines Users werden Autoren anonymisiert.
- Keine Tracker, keine Analytics von Drittanbietern.
- Löschen entfernt auch Dateien im Speicher.

## 11. Betrieb auf dem vorhandenen Server

Ziel: Ubuntu 26.04, Domain `hiker.lacasa.internal`, läuft auf dem bereits genutzten Server neben anderen Diensten.

- Docker über das offizielle Docker-Repository installieren; Stack per Docker Compose: `api`, `db` (PostgreSQL), `web` (Flask-Web-Frontend, ab Schritt 13), optional `minio`.
- **Keine festen Ports 80/443 im Stack.** API und Web-Frontend lauschen nur auf `127.0.0.1:<Port>` (`API_PORT`, `WEB_PORT`). Der bereits vorhandene Webserver bzw. Reverse Proxy (nginx, Apache oder Caddy) leitet `hiker.lacasa.internal` dorthin; TLS über Let's Encrypt (certbot oder Caddy). Beispielkonfigurationen für nginx und Caddy liegen in `deploy/`. Läuft auf dem Server noch kein Proxy, wird einer ergänzt.
- DNS: A-/AAAA-Eintrag für `hiker.lacasa.internal` auf den Server.
- Konfiguration in `.env` (nicht im Repository, Vorlage `.env.example`): Datenbankpasswort, `SECRET_KEY`, `PUBLIC_BASE_URL=https://hiker.lacasa.internal`, Speicherpfad, `ENABLED_MODULES`, `REGISTRATION_MODE`, für das Web-Frontend `WEB_SECRET_KEY` und `WEB_PORT`.
- Upload-Größen im Proxy erhöhen (Fotos, GPX).
- Backups: Nächtlicher `pg_dump` plus Sicherung des Foto-/GPX-Verzeichnisses nach `/var/backups/hiker`, 14 Tage Rotation, per systemd-Timer. Eine Kopie außerhalb des Servers ist empfohlen (Ziel noch offen). Wiederherstellung einmal testen.
- **Umsetzung (Schritt 14)**: `deploy/` enthält `install-docker.sh`, Proxy-Beispiele für nginx und Caddy (beide halten Link-Tokens und Referer aus dem Log), `backup.sh`/`restore.sh` mit systemd-Units und `smoke_test.py`, der einen laufenden Stack von der Registrierung bis zum öffentlichen Link prüft. Am 04.10.2026 lief der Stack erstmals in Docker mit PostgreSQL; Smoke-Test, Sicherung und Wiederherstellung sowie die nginx-Konfiguration wurden dabei praktisch geprüft, die Caddy-Konfiguration nur mit `caddy validate`. Anleitung: `deploy/README.md`.
- **Datenordner**: `DATA_DIR` (Standard `./data`) enthält `db/`, `files/`, `tiles/` und `web-sessions/`. Der Dienst `init` legt die Unterordner an; alle Dienste laufen als `HIKER_UID:HIKER_GID`, `DATA_DIR` muss diesem Benutzer gehören. Der Kachelspeicher ist auf `TILE_CACHE_MAX_MB` (Standard 2000) begrenzt, die ältesten Kacheln fallen zuerst weg; er wird nicht gesichert.
- Zertifikat: Für eine interne Domain (`*.internal`) stellt Let's Encrypt nichts aus; bis zur Umstellung auf die endgültige Domain braucht es eine eigene Zertifizierungsstelle, deren Wurzelzertifikat auch auf dem Android-Gerät installiert ist.
- Datenbankmigrationen mit Alembic, Updates über neue Images.
- Health-Endpunkt `/healthz`; Logs über Docker/journald; Firewall (ufw) nur 22/80/443.
- Ressourcen schonen, da der Server geteilt ist: Container-Limits setzen, Bildverarbeitung in der Größe begrenzen.

## 12. Phasenplan

**Phase 1 – Protokolle, Ausrüstung, Essen (abgeschlossen am 04.10.2026)**
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
11. Flutter (nur Android): Core inkl. `core/map` (Karte, Foto-Marker, Höhenprofil, Zeichnen), Auth, Ausrüstung, Essen mit Scanner, Protokolle (Liste, Detail, Editor, Historie, Teilen)
12. Offline-Sync (Android-App)
13. Web-Frontend mit Flask (Abschnitt 9a): Anmeldung, Ausrüstung, Essen, Protokolle, öffentliche Linkseite
14. Tests, Docker Compose, Proxy-Beispiele, Backup-Skript, README

**Phase 2 – Planung (aktuell)**; Einzelheiten in Abschnitt 9b
1. Backend-Modul `planning`: geplante Routen (CRUD, Vorschau, Eckdaten, Gehzeit-Schätzung, GPX-Export), Wegführung hinter einem Adapter, Luftlinie als Rückfall
2. BRouter als eigener Container (Compose-Profil `routing`), Skript für die Wegdaten der Regionen, eigenes Profil für Schwierigkeit (T1–T6) und Klettersteige
3. Web-Frontend: Routenliste und Planer (Punkte setzen, verschieben, Höhenprofil, speichern, GPX)
4. App: Routenliste, Detail, Planer, Offline-Abgleich
5. Verknüpfung zu Protokollen: aus einer Route eine Tour anlegen, Plan und tatsächlichen Track vergleichen; GPX-Import als Route
6. Layer-Provider-Schnittstelle im Modul `maps`; Kartenstile je Region (Sommer, Winter, Luftbild, Topo), vom Betreiber eintragbare lizenzierte Quellen, Umschaltung 2D/3D, Lizenzen je Quelle dokumentiert
7. Ebenen: Hangneigung, Wetter, Schnee, Lawinenlage
8. Eigene Karte aus OSM-Rohdaten (Regionsauszug, regelmäßig neu gebaut) – vorgezogen und umgesetzt am 04.10.2026 (ohne Höhenlinien und Schummerung)
9. Optional: FIT-Import

**Phase 3 – Berichte**: Backend-Dienst, der hikr.org-Berichte für Gipfel im Umkreis findet (Nutzungsbedingungen und robots.txt prüfen, Zwischenspeicherung, nur Verweise + kurze Auszüge, Quelle klar angeben).

## 13. Regeln für Claude Code

Stehen in der separaten Datei `CLAUDE.md` im Repository-Hauptverzeichnis.

## 14. Noch offen

1. Backup-Ziel außerhalb des Servers (z. B. zweiter Server, externer Speicher).
2. Welcher Webserver bzw. Reverse Proxy läuft auf dem Server bereits? Beispiele für nginx und Caddy liegen in `deploy/`; für Apache gibt es noch keines.
3. Kartenquellen und Lizenzen (bis Phase 2). Die Android-App holt ihre Kacheln vom eigenen Server (Modul `maps`); nur ein Server ohne dieses Modul schickt sie direkt zur Kachelquelle. `--dart-define=MAP_TILE_URL=…` legt eine feste Quelle fest.
4. Das Rate-Limit liegt im Arbeitsspeicher eines API-Prozesses. Läuft die API später in mehreren Prozessen, muss es in den Proxy oder einen gemeinsamen Speicher wandern.
5. Genauer Wunsch zur Foto-Darstellung nach Sichtung der wanderer-Demo (Abschnitt 9), falls etwas anders sein soll.