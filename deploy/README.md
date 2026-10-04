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

**Kein Container läuft als root.** Alle Dienste laufen als `HIKER_UID:HIKER_GID` (Standard
1000:1000, also der erste Benutzer des Systems), ohne Linux-Capabilities, ohne Möglichkeit, neue
Rechte zu erlangen, und mit schreibgeschütztem Dateisystem. Alle Dateien unter `DATA_DIR` gehören
diesem Benutzer. `DATA_DIR` muss vor dem ersten Start existieren und ihm gehören (`./data` ist im
Repository angelegt); die Unterordner legt der Dienst `init` an.

`db/` nie im laufenden Betrieb kopieren – für die Datenbank gibt es `backup.sh`.

Kartenkacheln holt der Server beim ersten Ansehen von OpenStreetMap und liefert sie danach
selbst aus. Nach `TILE_CACHE_DAYS` (14) fragt er nach, ob sich eine Kachel geändert hat. Der
Speicher ist auf `TILE_CACHE_MAX_MB` (2000) begrenzt und muss nicht gesichert werden.

Leere Instanz (z. B. nach Tests): `docker compose down`, dann `rm -rf data/db data/files
data/web-sessions`, dann `docker compose up -d`.

## Reverse Proxy

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
