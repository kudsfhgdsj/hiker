# hiker – App

Flutter-App für Android. Das Web-Frontend ist ein eigenes Projekt (Python Flask, siehe
`../DESIGN.md`). Grundlage: `../DESIGN.md`, Regeln: `../CLAUDE.md`.

## Einrichten

Flutter (stabil, ab 3.47) muss installiert sein. Dann:

```sh
cd app
flutter pub get
dart run build_runner build --delete-conflicting-outputs   # Drift-Code erzeugen
flutter test
flutter analyze
```

Die deutschen Texte liegen in `lib/l10n/app_de.arb`; `flutter gen-l10n` erzeugt daraus
`AppLocalizations` (läuft bei `flutter run`, `test` und `build` von selbst).

## Starten

```sh
flutter run                                 # angeschlossenes Android-Gerät
flutter build apk                           # braucht das Android-SDK
```

Die Server-Adresse wird beim Anmelden eingegeben und auf dem Gerät gespeichert. Ein Vorgabewert
lässt sich beim Bauen setzen: `--dart-define=API_BASE_URL=https://hiker.example.org`. Für den
Android-Emulator ist der Rechner unter
`http://10.0.2.2:<Port>` erreichbar.

## APK bauen

Dafür braucht es ein JDK (21) und das Android-SDK (Plattform 36, Build-Tools 36.0.0, NDK
28.2). Flutter muss beide kennen:

```sh
flutter config --android-sdk ~/Android/Sdk --jdk-dir ~/development/jdk
export JAVA_HOME=~/development/jdk   # falls kein java im PATH liegt
flutter build apk --debug      # build/app/outputs/flutter-apk/app-debug.apk
flutter build apk --release    # build/app/outputs/flutter-apk/app-release.apk
```

### Release signieren

Ein Release wird mit einem eigenen Schlüssel signiert, sobald `android/key.properties`
vorhanden ist (die Datei steht in `.gitignore`); ohne sie nimmt der Build den Debug-Schlüssel,
und die APK taugt nur zum Ausprobieren.

```sh
keytool -genkeypair -v -keystore /sicherer/ort/hiker-release.jks \
  -alias hiker -keyalg RSA -keysize 4096 -validity 10000
```

```properties
# android/key.properties
storeFile=/sicherer/ort/hiker-release.jks
storePassword=…
keyAlias=hiker
keyPassword=…
```

Schlüsseldatei und Passwort gehören nicht ins Repository und müssen gesichert werden: Android
installiert ein Update nur, wenn es mit demselben Schlüssel signiert ist. Geht er verloren,
muss die App deinstalliert werden (die lokalen, noch nicht abgeglichenen Daten gehen dabei
verloren). Die Signatur einer APK zeigt
`~/Android/Sdk/build-tools/36.0.0/apksigner verify --print-certs app-release.apk`.

Der erste Release-Build lädt Flutter-Bausteine von `storage.googleapis.com`; der Rechner muss
diesen Namen auflösen und erreichen können.

### App-Symbol und Berechtigungen

Das Symbol erzeugt `tool/make_icon.py` (braucht Pillow) in allen Auflösungen, als adaptives
Symbol und als einfaches Bild für ältere Geräte: `python3 tool/make_icon.py`.

Die App verlangt Internet, Kamera (Barcode-Scan) und Lesezugriff auf Dateien (Auswahl von
GPX-Dateien und Fotos). Berechtigungen, die Bibliotheken zusätzlich mitbringen (Standort von
der Karte, Mikrofon von der Kamera), entfernt das Manifest wieder (`tools:node="remove"`),
weil die App sie nicht nutzt. Was in einer fertigen APK steht, zeigt
`~/Android/Sdk/build-tools/36.0.0/aapt2 dump permissions app-release.apk`.

## Aufbau

```
lib/
├── main.dart, app.dart       # Start; app.dart verdrahtet die Features mit dem Core
├── core/                     # kennt keine Features
│   ├── config/               # Build-Konfiguration (keine Domains, keine Geheimnisse)
│   ├── storage/              # Schlüssel-Wert-Speicher (Plattform-Keystore)
│   ├── session/              # wer ist an welchem Server angemeldet
│   ├── network/              # dio, Token-Erneuerung, Fehler der API
│   ├── db/                   # Drift: lokale Kopie der Datensätze
│   ├── modules/              # FeatureModule und die Liste der aktiven Module
│   ├── router/               # go_router mit Weiterleitung je nach Anmeldung
│   ├── theme/, widgets/      # Design-Tokens, Rahmen mit Navigation
├── shared/                   # gemeinsame Modelle
├── features/<name>/          # data/ und presentation/ je Feature
└── l10n/                     # Texte (ARB)
```

Ein Feature registriert sich in `app.dart` als `FeatureModule` (Routen, Eintrag in der
Navigation). Angezeigt wird es nur, wenn der Server das gleichnamige Modul meldet
(`GET /api/v1/modules`); ohne Netz bleiben alle eingebauten Features erreichbar.

## Tests

Die Tests brauchen weder Server noch Netz: `test/helpers.dart` ersetzt den HTTP-Adapter durch
`FakeApi`, den Keystore durch einen Speicher im Arbeitsspeicher und die Datenbank durch SQLite
im Arbeitsspeicher.

## Karte

Die Kartenkacheln kommen vom eigenen Server (`/api/v1/maps/tiles/…`, Modul `maps`), der sie
zwischenspeichert. Hat der Server das Modul nicht, lädt die App direkt von OpenStreetMap. Eine
feste Quelle lässt sich beim Bauen setzen: `--dart-define=MAP_TILE_URL=https://…/{z}/{x}/{y}.png`.

## Eigene Karte und Offline-Karten

Hat der Server eine eigene Vektorkarte (`deploy/build-map.sh`), zeigt die App sie statt der
Rasterkacheln. Die Karte fragt dafür den Kartenserver in der App (`core/map/tile_proxy.dart`,
auf 127.0.0.1): Er antwortet aus einer Kartendatei auf dem Gerät, sonst vom eigenen Server,
und hebt auf, was er ausgeliefert hat. Kartengebiete lädt man unter Planung → „Offline-Daten“
(`core/map/map_regions.dart`).

## Planung

Unter „Planung“ liegen die Routenliste und der Planer: Punkte auf der Karte setzen und
versetzen, den Wegen folgen oder Luftlinie (für alle oder einzelne Abschnitte), Schwierigkeit
T1–T6, Klettersteige, Höhenprofil, als GPX speichern. Linie und Eckdaten kommen vom Server.

**Ohne Netz** rechnet die App selbst: Der Routing-Kern von BRouter ist eingebunden
(`android/app/libs/`, Herkunft und Prüfsumme in der README dort; Aufruf in `MainActivity.kt`,
Dart-Seite in `features/planning/data/offline_routing.dart`). Die Wegdaten eines Gebiets lädt
man unter Planung → „Offline-Wegdaten“ vom eigenen Server (je Kachel 100–300 MB). Das Profil
`assets/brouter/hiker-hiking.brf` ist eine Kopie von `deploy/brouter/profiles/`; ein Test
prüft, dass beide gleich sind. Luftlinien haben ohne Netz keine Höhen, und die Karte zeigt
nur schon angesehene Ausschnitte (der `TileProxy` hebt ausgelieferte Kacheln als Dateien auf). Beim Abgleich berechnet der Server die Linie neu.

## Anmeldung und Sicherheit

- Registrierung mit doppelter Passworteingabe; die Regeln (BSI) werden schon in der App geprüft.
- Zweiter Faktor: Nach dem ersten Login führt die App durch das Einrichten (Schlüssel für die
  Authenticator-App, Wiederherstellungscodes). Beim Anmelden fragt sie in einem zweiten Schritt
  nach dem Code, nachdem das Passwort gestimmt hat.
- SSO über OpenID Connect gibt es vorerst nur im Web-Frontend.

## Eigene oder selbst signierte Zertifikate

- **Selbst signiert** (auch der Caddy des Compose-Stacks): Scheitert die Verbindung am
  Zertifikat, zeigt die App dessen SHA-256-Fingerabdruck. Vergleichen mit
  `openssl x509 -in server.crt -noout -fingerprint -sha256` und bestätigen – die App akzeptiert
  danach genau dieses Zertifikat für diesen Server.
- Zeigt der Server später ein anderes Zertifikat (z. B. nach der Erneuerung), meldet die App das
  beim nächsten Start und bietet das neue zur Bestätigung an.
- Im Profil stehen die bestätigten Zertifikate; dort lässt sich das Vertrauen wieder entziehen.
- **Eigene Zertifizierungsstelle**: Das Wurzelzertifikat in Android installieren (Einstellungen →
  Sicherheit → Zertifikat installieren). Die App vertraut installierten Stellen.
- Die Karte lädt ihre Kacheln über eine native Bibliothek, die die Bestätigung in der App nicht
  kennt. Für einen von Hand bestätigten Server holt deshalb die App selbst die Kacheln und reicht
  sie der Karte über einen kleinen Server auf `127.0.0.1` weiter (`core/map/tile_proxy.dart`).
- Unverschlüsseltes HTTP ist nicht erlaubt.

## App testen

1. **Echtes Telefon über WLAN** (testet auch Kamera und Dateiauswahl): am Telefon „Debugging über
   WLAN“ einschalten, dann `adb pair <ip>:<port>`, `adb connect <ip>:<port>` und `flutter run`.
2. **APK von Hand installieren**: `flutter build apk --debug` und die Datei aufs Telefon kopieren.
3. **Emulator**: braucht Hardware-Virtualisierung. In einer VM muss dafür die verschachtelte
   Virtualisierung eingeschaltet sein und der Benutzer zur Gruppe `kvm` gehören
   (`sudo usermod -aG kvm $USER`, neu anmelden).

### Emulator einrichten und starten

```sh
export ANDROID_HOME=~/Android/Sdk JAVA_HOME=~/development/jdk
export ANDROID_AVD_HOME=/mnt/data/android-avd        # braucht einige GB Platz
SDK=$ANDROID_HOME/cmdline-tools/latest/bin
$SDK/sdkmanager "emulator" "system-images;android-35;default;x86_64"   # AOSP, ohne Google-Dienste
echo no | $SDK/avdmanager create avd -n hiker_test -d pixel_6 \
    -k "system-images;android-35;default;x86_64"
$ANDROID_HOME/emulator/emulator -avd hiker_test -no-snapshot \
    -gpu swiftshader_indirect -memory 2048      # ohne Bildschirm zusätzlich: -no-window -no-audio
$ANDROID_HOME/platform-tools/adb install -r build/app/outputs/flutter-apk/app-debug.apk
```

Im Emulator ist der Rechner unter `10.0.2.2` erreichbar. Die App erlaubt kein unverschlüsseltes
HTTP; für einen lokalen Stack den mitgelieferten Caddy einschalten (`COMPOSE_PROFILES=proxy`,
`CADDY_SITES=localhost, 10.0.2.2`, `CADDY_DEFAULT_SNI=10.0.2.2`, `HTTPS_PORT=8443` in der `.env`).
Als Server-Adresse dann `https://10.0.2.2:8443` eintragen und den Fingerabdruck bestätigen.

Am 04.10.2026 so geprüft (Android 15): Registrierung, Zertifikatsbestätigung, zweiten Faktor
einrichten, Ausrüstung mit Favorit und Zusatzfeldern, Tour anlegen und bearbeiten, GPX und Foto
über die Dateiauswahl hochladen, Karte mit Kacheln, Höhenprofil und Foto-Marker, Änderungen ohne
Verbindung und ihr Abgleich danach, Kamera-Berechtigung und Vorschau des Scanners, Sitzung nach
Neustart. Nicht geprüft: das Erkennen eines echten Barcodes (der Emulator zeigt nur eine
künstliche Szene), Konflikte beim Abgleich, Teilen und Verlauf in der App.

Die VM braucht dafür Luft: Emulator, Gradle-Build und `flutter test` nicht gleichzeitig laufen
lassen (bei 7 GB RAM ist der Emulator dabei einmal abgestürzt).
