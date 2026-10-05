# hiker – Betrieb

Der Stack läuft per Docker Compose neben anderen Diensten auf einem Server. Er belegt keine Ports
80/443: API und Web-Frontend lauschen nur auf `127.0.0.1`, nach außen bringt sie der vorhandene
Reverse Proxy.

| Datei | Zweck |
|---|---|
| `install-docker.sh` | Docker Engine und Compose aus dem offiziellen apt-Repository installieren |
| `nginx-hiker.conf` | Beispiel für nginx |
| `Caddyfile` | Beispiel für Caddy |
| `backup.sh`, `restore.sh` | Sicherung und Wiederherstellung von Datenbank und Dateien |
| `hiker-backup.service`, `hiker-backup.timer` | nächtliche Sicherung per systemd |
| `smoke_test.py` | prüft einen laufenden Stack |
| `caddy/Caddyfile` | Konfiguration des Caddy im Compose-Stack (Profil `proxy`) |
| `reset-data.sh` | leert eine Testinstanz (löscht alle Daten) |

## Installation

```sh
sudo deploy/install-docker.sh            # optional mit Benutzername: Docker ohne sudo
cp .env.example .env && chmod 600 .env   # Werte ausfüllen, siehe Kommentare in der Datei
docker compose up -d --build
deploy/smoke_test.py
```

Wichtige Werte in `.env`:

- `SECRET_KEY`, `WEB_SECRET_KEY`, `POSTGRES_PASSWORD`: je ein eigener, zufälliger Wert.
- `PUBLIC_BASE_URL`: die Adresse, unter der Nutzer die Seite erreichen (`https://…`). Sie steht in
  den öffentlichen Links.
- `WEB_COOKIE_SECURE`: nur für einen Test ohne HTTPS auf `false`; im Betrieb weglassen.
- `REGISTRATION_MODE`: nach dem Anlegen des ersten Kontos (wird Administrator) auf `closed`.
- `MFA_REQUIRED`: der zweite Faktor (TOTP) ist Pflicht; `false` macht ihn freiwillig.
- `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`: Anmeldung über einen OpenID-Connect-Anbieter
  (optional). Redirect-URI beim Anbieter: `<PUBLIC_BASE_URL>/login/sso/callback`.

Der Smoke-Test legt ein Wegwerf-Konto an und richtet dafür den zweiten Faktor ein. Für ein
vorhandenes Konto mit zweitem Faktor braucht er zusätzlich `SMOKE_TOTP_SECRET`. Auf einer frischen Instanz würde dieses Konto zum
Administrator – dort erst das eigene Konto anlegen oder den Test mit `SMOKE_EMAIL` und
`SMOKE_PASSWORD` eines vorhandenen Kontos starten.

## Daten

Alle Daten liegen als normale Dateien unter `DATA_DIR` (Standard `./data` im Repository), nicht
in Docker-Volumes:

| Ordner | Inhalt |
|---|---|
| `db/` | PostgreSQL |
| `files/` | Fotos und GPX |
| `tiles/` | Kartenkacheln (Zwischenspeicher) |
| `web-sessions/` | Anmeldungen des Web-Frontends |
| `caddy/` | Zertifizierungsstelle und Zertifikate des Proxys im Stack |
| `brouter/segments/` | Wegdaten für die Routenplanung (neu ladbar) |
| `maps/` | Eigene Karte je Gebiet (`*.mbtiles`, neu baubar) und Hilfsdaten für den Bau |

**Kein Container läuft als root.** Alle Dienste laufen als `HIKER_UID:HIKER_GID` (Standard
1000:1000, also der erste Benutzer des Systems), ohne Linux-Capabilities, ohne Möglichkeit, neue
Rechte zu erlangen, und mit schreibgeschütztem Dateisystem. Alle Dateien unter `DATA_DIR` gehören
diesem Benutzer. `DATA_DIR` muss vor dem ersten Start existieren und ihm gehören (`./data` ist im
Repository angelegt); die Unterordner legt der Dienst `init` an.

`db/` nie im laufenden Betrieb kopieren – für die Datenbank gibt es `backup.sh`.

Kartenkacheln holt der Server beim ersten Ansehen von OpenStreetMap und liefert sie danach
selbst aus. Nach `TILE_CACHE_DAYS` (14) fragt er nach, ob sich eine Kachel geändert hat. Der
Speicher ist auf `TILE_CACHE_MAX_MB` (2000) begrenzt und muss nicht gesichert werden.

### Testinstanz leeren

```sh
deploy/reset-data.sh
```

Das löscht nach einer Rückfrage **alle** Konten, Touren, Ausrüstung, Lebensmittel, Fotos und
GPX-Dateien der Instanz und startet sie leer neu. Kartenkacheln und die Zertifikate von Caddy
bleiben. Das erste Konto, das sich danach registriert, wird Administrator.

## Reverse Proxy

Zwei Wege: der mitgelieferte Caddy im Stack oder ein Proxy, der auf dem Server schon läuft.

### Caddy im Stack (stellt sich das Zertifikat selbst aus)

In der `.env`:

```sh
COMPOSE_PROFILES=proxy
CADDY_SITES=hiker.lacasa.internal
CADDY_DEFAULT_SNI=hiker.lacasa.internal
HTTPS_PORT=443
PUBLIC_BASE_URL=https://hiker.lacasa.internal
```

Danach `docker compose up -d`. Caddy legt beim ersten Start eine eigene Zertifizierungsstelle an
(`DATA_DIR/caddy`) und stellt für jede Adresse aus `CADDY_SITES` ein Zertifikat aus, das ein Jahr
gilt und rechtzeitig erneuert wird. Damit Browser und Geräte nicht warnen, das Wurzelzertifikat
einmal installieren:

```
DATA_DIR/caddy/caddy/pki/authorities/local/root.crt
```

- Browser/Betriebssystem: als vertrauenswürdige Zertifizierungsstelle importieren.
- Android-App: Es genügt, in der App den angezeigten Fingerabdruck zu bestätigen
  (vergleichen mit `openssl s_client -connect <host>:<port> </dev/null | openssl x509 -noout
  -fingerprint -sha256`). Nach einer Erneuerung des Zertifikats fragt die App erneut.
- Smoke-Test: `deploy/smoke_test.py --api https://<host> --web https://<host> --ca <root.crt>`.

Ohne `COMPOSE_PROFILES=proxy` startet Caddy nicht und der Stack belegt keinen Port nach außen.
Caddy läuft wie alle Dienste ohne root; als einzige Capability hat er `NET_BIND_SERVICE`.

### Vorhandener Proxy auf dem Server

`/api/` geht an die API (`API_PORT`, Standard 8010), alles andere an das Web-Frontend (`WEB_PORT`,
Standard 8011). Beide Beispiele

- leiten genau eine Client-Adresse weiter (`X-Forwarded-For`), nach der das Rate-Limit zählt,
- erlauben Uploads bis 320 MB (mehrere Fotos auf einmal),
- **halten die Tokens öffentlicher Links aus dem Log**: `/p/<token>` und
  `/api/v1/public/tours/<token>` erscheinen als `[redacted]`, der Referer wird nicht protokolliert
  (die Unterseiten eines Links tragen das Token im Referer).

nginx: `nginx-hiker.conf` nach `/etc/nginx/conf.d/hiker.conf` kopieren, Domain und Zertifikat
anpassen, `nginx -t && systemctl reload nginx`.

Caddy: den Block aus `Caddyfile` in die eigene Caddy-Konfiguration übernehmen.

Zertifikat: Für eine öffentliche Domain stellt Let's Encrypt eines aus (certbot bzw. Caddy von
selbst). Für eine interne Domain wie `hiker.lacasa.internal` geht das nicht; dort braucht es eine
eigene Zertifizierungsstelle (bei Caddy `tls internal`), deren Wurzelzertifikat auf den Geräten
installiert ist – auch auf dem Android-Telefon, sonst verbindet sich die App nicht.

Firewall: nur 22, 80 und 443 öffnen (`ufw`). Die Ports 8010 und 8011 sind von außen nicht
erreichbar und sollen es nicht sein.

## Eigene Karte

Ohne eigene Karte zeigt hiker zwischengespeicherte Kacheln von OpenStreetMap. Mit ihr zeigen
Web und App eine eigene Wanderkarte, und die App kann Kartengebiete herunterladen und ohne
Netz zeigen.

```sh
deploy/build-map.sh switzerland          # ein Gebiet, Name wie bei download.geofabrik.de
deploy/build-map.sh alps                 # der Alpenbogen; MAP_BUILD_MEMORY=6g in der .env
```

Der Bau läuft als einmaliger Container (Planetiler), lädt den OSM-Auszug des Gebiets und
beim ersten Mal rund 1,5 GB Hilfsdaten und legt `DATA_DIR/maps/<gebiet>.mbtiles` ab. Die API
liefert die Karte sofort aus, ein Neustart ist nicht nötig. Schweiz: rund 350 MB, gut fünf
Minuten bei 3 GB RAM. `deploy/update-maps.sh` hält alle Karten aktuell (siehe unten). Mehrere Gebiete
ergänzen sich; an ihren Grenzen kann eine Kachel nur aus einem der Gebiete stammen, deshalb
ist ein zusammenhängendes Gebiet (z. B. `alps`) besser als viele kleine.

Die Karte lässt sich jederzeit neu bauen und gehört nicht in die Sicherung.

## Routenplanung mit BRouter

Damit geplante Routen den Wanderwegen folgen, läuft BRouter als eigener Dienst im Stack. Ohne
ihn lassen sich nur Luftlinien planen.

1. Wegdaten holen (Standard: Alpenraum, rund 1 GB; einzelne Kacheln als Argument):

   ```sh
   deploy/brouter-segments.sh            # Alpenraum und alles, was die gebauten Karten abdecken
   deploy/brouter-segments.sh E5_N45     # nur Schweiz, Westösterreich, Süddeutschland
   ```

   Eine Kachel umfasst 5° × 5° und heißt nach ihrer südwestlichen Ecke. Die Dateien liegen
   unter `DATA_DIR/brouter/segments`. Ein erneuter Aufruf lädt nur Geändertes; die Daten
   werden etwa wöchentlich neu erzeugt, ein monatlicher Aufruf (cron) genügt.

2. In der `.env` das Profil einschalten und der API den Dienst nennen:

   ```sh
   COMPOSE_PROFILES=proxy,routing     # oder nur "routing" ohne den Caddy des Stacks
   BROUTER_URL=http://brouter:17777
   ```

3. `docker compose up -d --build`

Die App lädt dieselben Wegdaten über die API (`/api/v1/planning/segments`) auf das Gerät, um
ohne Netz zu planen; der Proxy muss dafür Downloads von einigen hundert MB durchlassen
(nginx: `proxy_buffering off` oder genug Platz für Zwischendateien).

BRouter hat keinen Port nach außen; nur die API spricht mit ihm. Die Wegdaten stammen aus
OpenStreetMap (ODbL) und lassen sich jederzeit neu holen, gehören also nicht in die Sicherung.
Punkte außerhalb der geladenen Kacheln ergeben beim Planen „kein Weg gefunden“.

## Sicherung

```sh
sudo mkdir -p /var/backups/hiker
sudo cp deploy/hiker-backup.service deploy/hiker-backup.timer /etc/systemd/system/
sudoedit /etc/systemd/system/hiker-backup.service    # Pfad zum Repository anpassen
sudo systemctl daemon-reload && sudo systemctl enable --now hiker-backup.timer
sudo systemctl start hiker-backup.service             # einmal sofort; Ergebnis: journalctl -u hiker-backup
```

`backup.sh` schreibt je Lauf zwei Dateien nach `BACKUP_DIR` (Standard `/var/backups/hiker`):
`hiker-<Zeit>.dump` (Datenbank, `pg_dump` im Custom-Format) und `hiker-<Zeit>.files.tar.gz`
(Fotos und GPX). Sicherungen, die älter als `KEEP_DAYS` (14) Tage sind, werden gelöscht. Die
Sitzungen des Web-Frontends werden nicht gesichert; nach einer Wiederherstellung melden sich die
Nutzer neu an.

**Die Sicherung liegt auf demselben Server.** Eine Kopie außerhalb (zweiter Server, externer
Speicher) ist noch einzurichten, z. B. mit `rsync` oder `restic` auf `BACKUP_DIR`. Die `.env`
gehört ebenfalls gesichert – ohne `SECRET_KEY` sind alle Anmeldungen ungültig.

## Wiederherstellung

```sh
deploy/restore.sh /var/backups/hiker/hiker-<Zeit>.dump /var/backups/hiker/hiker-<Zeit>.files.tar.gz
```

Das ersetzt Datenbank und Dateien vollständig und fragt vorher nach. Geprüft am 04.10.2026:
Instanz mit Tour, Track und Foto gesichert, alle Volumes gelöscht, Sicherung eingespielt, Daten
und Dateien waren wieder da.

## Aktualisieren

```sh
git pull
docker compose up -d --build     # Datenbankmigrationen laufen beim Start der API
deploy/smoke_test.py
```

## Nutzer verwalten

Administratoren finden im Web-Frontend unter „Verwaltung“ alle Nutzer und können sie entfernen,
Passwörter zurücksetzen (vorläufiges Passwort, wird einmal angezeigt) und einen verlorenen zweiten
Faktor zurücksetzen. Hat der einzige Administrator selbst den zweiten Faktor und alle
Wiederherstellungscodes verloren, hilft nur die Datenbank:

```sh
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "UPDATE user_account SET totp_secret = NULL, totp_enabled_at = NULL, totp_last_counter = NULL WHERE email = '"'"'admin@example.org'"'"'"'
```

Beim nächsten Login richtet er den Faktor neu ein.

## Betrieb im Blick

- Zustand: `docker compose ps`, `curl http://127.0.0.1:8010/healthz`, `…:8011/healthz`
- Logs: `docker compose logs -f api web`
- Grenzen je Container: `db` und `api` 1 CPU / 512 MB, `web` 0,5 CPU / 256 MB (im Leerlauf
  brauchen sie zusammen etwa 200 MB).

## Karten und Wegdaten aktuell halten

`deploy/update-maps.sh` baut jedes vorhandene Kartengebiet neu (Karte, Suchindex,
Ebenen-Paket) und holt geänderte Wegdaten; danach startet es BRouter neu. Die alte Karte
bleibt in Betrieb, bis die neue fertig ist. Scheitert ein Gebiet, bleibt seine alte Karte,
die übrigen werden trotzdem gebaut, und das Skript endet mit Fehlercode. Zwei Läufe zugleich
verhindert eine Sperre (`DATA_DIR/maps/.update.lock`).

Monatlich per cron, als der Benutzer, dem der Stack gehört (`crontab -e`):

```
15 2 1 * *  /opt/hiker/deploy/update-maps.sh >> /var/log/hiker-maps.log 2>&1
```

Je Gebiet dauert es 15 bis 30 Minuten und braucht rund 3 GB freien Arbeitsspeicher;
`MAP_LAYERS=0` lässt die Ebenen-Pakete aus (Höhendaten ändern sich kaum). Die App bietet
ein Gebiet erneut zum Laden an, wenn die Datei auf dem Server neuer ist.

## Flüssige Karte: Ebenen vorab bauen, mehrere Prozesse

Zwei Dinge machen die Karte beim ersten Ansehen eines Ausschnitts langsam: Höhendaten kommen
erst aus dem Internet, und Hangneigung und Höhenlinien werden daraus berechnet (eine
Höhenlinien-Kachel rund 0,4 s). Beides lässt sich vorab erledigen:

```sh
deploy/prebuild-layers.sh                 # alle Gebiete, bis Zoom 13
MAP_PREBUILD_ZOOM=14 deploy/prebuild-layers.sh switzerland
```

Das schreibt je Gebiet `DATA_DIR/maps/<gebiet>.server.sqlite`; die API antwortet daraus,
ohne zu holen oder zu rechnen (ebenso aus dem Ebenen-Paket für die App). Ein abgebrochener
Lauf macht beim nächsten Aufruf weiter. Tiefere Stufen, als gebaut wurden, entstehen wie
bisher beim Ansehen und bleiben danach im Kachel-Zwischenspeicher.

Dazu der API mehr als einen Prozess und Kern geben (`.env`): `API_WORKERS=3`, `API_CPUS=3`,
`API_MEMORY=1g`. Die Zugriffsbegrenzung zählt je Prozess (siehe `.env.example`).

## Feinere Höhendaten für ein Gebiet

```sh
deploy/build-terrain.sh austria      # BEV-Geländemodell 5 m, CC BY 4.0
```

Lädt das Geländemodell (Österreich: eine Datei mit knapp 19 GB nach
`DATA_DIR/maps/build/sources`), schneidet es in Höhenkacheln bis Zoom 14 und rechnet
Hangneigung und Höhenlinien daraus (`DATA_DIR/maps/austria.hires.sqlite`, 5 bis 7 GB). Die
API nimmt diese Kacheln vor den groben weltweiten und nennt die Quelle in der Karte. Die
heruntergeladene Datei wird danach nicht mehr gebraucht. Weitere Gebiete brauchen einen
Eintrag mit Quelle und Lizenz im Skript; geprüfte Quellen stehen in `DESIGN.md`.

