# hiker – Projektregeln für Claude Code

Lies zuerst `DESIGN.md`. Sie ist die verbindliche Grundlage für Architektur, Datenmodell, API und Phasenplan.

## Projekt in Kürze
Android-App (Flutter, nur Android), Web-Frontend (Python Flask) und eigenes Backend (FastAPI + PostgreSQL), selbst gehostet unter `hiker.lacasa.internal` (vorläufig, wird später auf die endgültige Domain umgestellt) auf Ubuntu 26.04. Module: auth, gear, nutrition, protocols, sync, maps, planning (jetzt); reports (später). Phase 1 ist abgeschlossen; aktuell gilt Phase 2 aus `DESIGN.md` (Abschnitt 9b).

## Sprache
- UI-Texte und Dokumentation: Deutsch (App: ARB-Dateien; Web-Frontend: eine Übersetzungsdatei, keine Texte verstreut in den Vorlagen).
- Code, Bezeichner, Commit-Nachrichten, API-Felder: Englisch.

## Architektur
- Modulgrenzen einhalten: Core importiert keine Module. Ein Modul nutzt ein anderes nur über deklarierte `depends_on`-Einträge und dessen öffentliche Service-Schnittstelle oder über IDs. Keine Zyklen. `protocols` darf `gear` und `nutrition` nutzen, nie umgekehrt. `planning` darf `protocols` nutzen (Track-Auswertung, Höhen-Adapter, Tour anlegen), nie umgekehrt.
- Jedes Modul hat `register(app)` und `MODULE_INFO`; Aktivierung über `ENABLED_MODULES`.
- API-first, Version `/api/v1` beibehalten; Änderungen müssen in OpenAPI sichtbar sein.
- Local-first in der Android-App (Drift), Sync über `/sync/*`.
- Flutter wird nur für Android gebaut; keine Web-Plattform und kein web-spezifischer Code im Flutter-Projekt.
- Das Web-Frontend (Flask, `web/`) spricht ausschließlich mit der REST-API, nie direkt mit Datenbank oder Dateispeicher, und enthält keine eigene Fachlogik. Tokens bleiben serverseitig in der Sitzung; Formulare sind gegen CSRF geschützt. JavaScript-Bibliotheken werden vom eigenen Server ausgeliefert, nicht von einem CDN.
- Wegführung beim Planen nur über den Adapter `RoutingEngine`; Wegpunkte gehen ausschließlich an den eigenen BRouter, nie an fremde Dienste.
- Externe Dienste (Open-Meteo, Open-Meteo-Elevation, Open Food Facts, OpenStreetMap/Overpass, Kartenkacheln, Dateispeicher, später hikr.org) nur über Adapter-Interfaces ansprechen.
- Datenbankänderungen nur über Alembic-Migrationen.
- Konfiguration über Umgebungsvariablen; keine Geheimnisse oder feste Domains im Code (`PUBLIC_BASE_URL`).

## Verbotenes und Abhängigkeiten
- Keine Google-Dienste oder -SDKs: Firebase, Google Maps, FCM, Google Sign-In, ML Kit. Barcode-Scan mit ZXing (`flutter_zxing`); vor dem Einsatz Pflegezustand des Pakets prüfen.
- Neue Abhängigkeiten nur mit kurzer Begründung; Lizenz muss Open Source sein.
- wanderer (open-wanderer/wanderer, AGPLv3) ist nur UX-Vorbild für die Foto- und Wegpunktdarstellung. Keinen Code, keine Texte, keine Grafiken übernehmen.
- Open-Food-Facts- und OpenStreetMap-Daten stehen unter ODbL: Quelle in der App nennen.
- An OpenStreetMap (Overpass) geht nur der Kartenausschnitt einer Tour, nie der Track selbst.

## Fachliche Regeln
- Jede Änderung an einer Tour erzeugt eine `tour_revision`; Historie nie überschreiben oder verkürzen. Wiederherstellen erzeugt eine neue Revision.
- Konfliktschutz über `tour.version` (409 mit aktuellem Stand), im Client feldweise zusammenführen.
- Rechte zentral prüfen (eine Dependency), nie einzeln in Endpunkten:
  - Owner: alles.
  - `edit`: Textfelder, Listen (Ausrüstung, Essen, Partner, Gipfel, Wegpunkte) und Fotos. **Nicht** erlaubt: GPX/Track und Start-/Endpunkte ändern, Freigaben und Links verwalten, Tour löschen.
  - `read`: nur lesen.
- Public-Link-Tokens sind kryptografisch zufällige UUIDv4, nie ableitbar, nie in Logs. Öffentliche Ansicht ohne Login, `noindex`, ohne E-Mail-Adressen und interne IDs, Gesundheitsdaten standardmäßig ausgeblendet.
- Ausrüstungsgewicht und Kalorien in Touren als Momentaufnahme (Snapshot) speichern.
- Geplante Routen: Linie und Eckdaten berechnet der Server aus den Wegpunkten; die Gehzeit ist eine Schätzung (`estimated`), Formel in `DESIGN.md` 9b.
- Kalorienverbrauch: manuelle Eingabe hat immer Vorrang; sonst Schätzung, in API und UI klar als `estimated` gekennzeichnet; Formel und Parameter dokumentieren.
- GPX-Parser tolerant: fehlende Zeit, Höhe, Herzfrequenz führen nie zu Fehlern. Sensordaten aus der Garmin TrackPointExtension lesen.
- Fotos: EXIF lesen, dem Track zuordnen (GPS, sonst Zeit mit einstellbarem Versatz), Position korrigierbar halten; Uploads prüfen und neu kodieren; EXIF-GPS bei öffentlichen Links optional entfernen.
- Gemeinsame Kataloge (Ausrüstung, Lebensmittel): nur Produktdaten teilen, keine persönlichen Felder (Kaufpreis, Kaufdatum, Notizen); Freigabe durch `admin`; Kopie statt Verweis bei Übernahme.
- Gesundheitsdaten (Herzfrequenz, Profil) nur für Owner sichtbar, in Freigaben und Links abschaltbar.
- Anmeldung: Passwortregeln nach BSI (`auth/passwords.py`), zweiter Faktor (TOTP) Pflicht, optional SSO über OIDC. Ob eine Sitzung vollständig ist, prüft allein die Dependency `CurrentUser`; nur die Endpunkte zum Einrichten des zweiten Faktors und zum Passwortwechsel nutzen `SignedIn`.
- Ausrüstung: Preise immer in EUR; Favorit ist der feste Tag `favorite`; Zusatzfelder je Art der Kategorie stehen in `gear/attributes.py` und gespiegelt in der App (`gearKinds`).

## Qualität
- Backend: pytest-Tests für jede Änderung, vor allem Rechteprüfung, Historie, GPX-Auswertung, Foto-Zuordnung und Kalorienschätzung.
- Flutter: Unit-Tests für Repositories und Provider, Widget-Tests für zentrale Screens.
- Web-Frontend: pytest mit dem Flask-Testclient für Seiten, Formulare und Rechte; die API wird in den Tests ersetzt.
- Kleine, abgeschlossene Schritte entlang des Phasenplans; nach jedem Schritt muss alles starten und alle Tests laufen.
- Bei Unklarheiten oder wenn `DESIGN.md` widersprüchlich ist: kurz nachfragen, statt zu raten. Neue Entscheidungen in `DESIGN.md` nachtragen.

## Betrieb
- Der Stack läuft auf einem bereits genutzten Server und belegt von sich aus keine Ports 80/443; API und Web-Frontend nur auf `127.0.0.1`. Der mitgelieferte Reverse Proxy (Caddy mit eigener CA) ist ein abschaltbares Compose-Profil (`proxy`) mit einstellbarem Port. Proxy-Beispiele für einen vorhandenen Proxy und Backup-Skripte liegen in `deploy/`.
- BRouter (Compose-Profil `routing`) hat keinen Port nach außen; seine Wegdaten liegen unter `DATA_DIR/brouter/segments` und werden nur mit `deploy/brouter-segments.sh` geholt.
- Container-Ressourcen begrenzen.
- Kein Container läuft als root: Dienste laufen als `HIKER_UID`, ohne Capabilities, mit schreibgeschütztem Dateisystem.
- Daten liegen als normale Ordner unter `DATA_DIR` (Bind-Mounts), nicht in Docker-Volumes.
- Kartenkacheln kommen vom eigenen Server (Modul `maps`): beim ersten Ansehen geholt, als Datei gespeichert, frühestens nach 7 Tagen neu geprüft. Nie Kacheln auf Vorrat herunterladen (Nutzungsbedingungen von OpenStreetMap).