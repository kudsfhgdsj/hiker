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
flutter build apk --debug      # build/app/outputs/flutter-apk/app-debug.apk
flutter build apk              # Release; bisher mit dem Debug-Schlüssel signiert
```

Für eine Veröffentlichung fehlt noch ein eigener Signaturschlüssel.

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

## Anmeldung und Sicherheit

- Registrierung mit doppelter Passworteingabe; die Regeln (BSI) werden schon in der App geprüft.
- Zweiter Faktor: Nach dem ersten Login führt die App durch das Einrichten (Schlüssel für die
  Authenticator-App, Wiederherstellungscodes). Beim Anmelden fragt sie nach dem Code.
- SSO über OpenID Connect gibt es vorerst nur im Web-Frontend.

## Eigene oder selbst signierte Zertifikate

- **Selbst signiert**: Scheitert die Verbindung am Zertifikat, zeigt die App dessen
  SHA-256-Fingerabdruck. Vergleichen mit
  `openssl x509 -in server.crt -noout -fingerprint -sha256` und bestätigen – die App akzeptiert
  danach genau dieses Zertifikat für diesen Server.
- **Eigene Zertifizierungsstelle**: Das Wurzelzertifikat in Android installieren (Einstellungen →
  Sicherheit → Zertifikat installieren). Die App vertraut installierten Stellen.
- Die Karte lädt ihre Kacheln über eine native Bibliothek, die die Bestätigung in der App nicht
  kennt. Damit die Karte funktioniert, muss das Zertifikat bzw. die CA in Android installiert sein.
- Unverschlüsseltes HTTP ist nicht erlaubt.

## App testen ohne Telefon am Rechner

Der Android-Emulator braucht Hardware-Virtualisierung (KVM). In einer VM ohne verschachtelte
Virtualisierung läuft er nicht brauchbar. Wege, die funktionieren:

1. **Echtes Telefon über WLAN** (empfohlen, testet auch Kamera und Karte): am Telefon
   „Debugging über WLAN“ einschalten, dann `adb pair <ip>:<port>`, `adb connect <ip>:<port>` und
   `flutter run`. Telefon und Rechner müssen sich im Netz erreichen.
2. **APK von Hand installieren**: `flutter build apk --debug` und die Datei aufs Telefon kopieren.
3. **Verschachtelte Virtualisierung** im Hypervisor der VM einschalten; danach funktioniert der
   normale Emulator aus Android Studio bzw. `sdkmanager`/`avdmanager`.
4. **Waydroid** (Android als Container, braucht kein KVM): möglich, aber mit Software-Grafik; ob
   die Karte (OpenGL) darin läuft, ist offen.

