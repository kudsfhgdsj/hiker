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
